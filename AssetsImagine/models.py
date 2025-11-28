from django.db import models, transaction
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
import os
import uuid
import shutil


class ImagineAssetBatch(models.Model):
    """Main model for batch upload of assets"""
    main_category = models.CharField(max_length=100, db_index=True, verbose_name="Main Category")
    sub_category = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Sub Category")
    
    position = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Position/Index of the main category (0-based)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Create Category"
        verbose_name_plural = "Create Category"
        ordering = ['position', 'main_category', 'sub_category']
        indexes = [
            models.Index(fields=['position']),
            models.Index(fields=['main_category', 'sub_category']),
        ]
    
    def __str__(self):
        if self.sub_category:
            return f"{self.main_category}/{self.sub_category}"
        return f"{self.main_category}"
    
    def get_next_image_number(self):
        """Get the next available image number for this batch"""
        last_image = self.images.order_by('-image_number').first()
        if last_image:
            return last_image.image_number + 1
        return 0
    
    def get_category_path(self):
        """Get the relative path for this category"""
        if self.sub_category:
            return os.path.join(self.main_category, self.sub_category)
        return self.main_category
    
    @staticmethod
    def normalize_category_name(name):
        """Normalize category name for comparison (case-insensitive)"""
        if not name:
            return None
        return name.strip().lower()
    
    def save(self, *args, **kwargs):
        """Override save to auto-assign position for main categories only"""
        if self.pk is None:  # Only for new instances
            # Check if main category already exists (case-insensitive)
            existing_main = ImagineAssetBatch.objects.filter(
                main_category__iexact=self.main_category
            ).first()
            
            if existing_main:
                # Use the same position and exact capitalization as existing main category
                self.position = existing_main.position
                self.main_category = existing_main.main_category  # Keep original capitalization
                
                # Check if same subcategory exists (case-insensitive)
                if self.sub_category:
                    existing_sub = ImagineAssetBatch.objects.filter(
                        main_category__iexact=self.main_category,
                        sub_category__iexact=self.sub_category
                    ).first()
                    if existing_sub:
                        # Use existing subcategory capitalization
                        self.sub_category = existing_sub.sub_category
            else:
                # New main category - assign next position (SQLite compatible)
                seen_categories = set()
                max_pos = -1
                
                for batch in ImagineAssetBatch.objects.all():
                    cat_lower = batch.main_category.lower()
                    if cat_lower not in seen_categories:
                        seen_categories.add(cat_lower)
                        if batch.position > max_pos:
                            max_pos = batch.position
                
                self.position = max_pos + 1
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to reindex remaining batches if it's the last subcategory"""
        main_cat = self.main_category
        super().delete(*args, **kwargs)
        
        # Check if there are any other batches with same main category
        remaining = ImagineAssetBatch.objects.filter(main_category__iexact=main_cat).exists()
        
        # If no more batches with this main category, reindex all
        if not remaining:
            ImagineAssetBatch.reindex_all()
    
    @classmethod
    def reindex_all(cls):
        """Reindex all main categories from 0 onwards (SQLite compatible)"""
        # Get all batches
        all_batches = list(cls.objects.all().order_by('position', 'main_category'))
        
        # Group by main category (case-insensitive)
        seen_categories = {}
        main_cats_order = []
        
        for batch in all_batches:
            cat_lower = batch.main_category.lower()
            if cat_lower not in seen_categories:
                seen_categories[cat_lower] = {
                    'main_category': batch.main_category,
                    'position': batch.position
                }
                main_cats_order.append(cat_lower)
        
        # Sort by position
        main_cats_order.sort(key=lambda x: seen_categories[x]['position'])
        
        # Update positions for all batches
        for index, cat_lower in enumerate(main_cats_order):
            main_cat = seen_categories[cat_lower]['main_category']
            cls.objects.filter(main_category__iexact=main_cat).update(position=index)
    
    @classmethod
    @transaction.atomic
    def move_to_position(cls, batch_id, new_position):
        """Move a main category to a specific position (SQLite compatible)"""
        try:
            batch = cls.objects.select_for_update().get(pk=batch_id)
            main_category = batch.main_category
            old_position = batch.position
            
            # Get unique main categories (SQLite compatible)
            all_batches = list(cls.objects.all().order_by('position', 'main_category'))
            seen_categories = {}
            main_cats = []
            
            for b in all_batches:
                cat_lower = b.main_category.lower()
                if cat_lower not in seen_categories:
                    seen_categories[cat_lower] = {
                        'main_category': b.main_category,
                        'lower_main': cat_lower,
                        'position': b.position
                    }
                    main_cats.append(seen_categories[cat_lower])
            
            # Sort by position
            main_cats.sort(key=lambda x: x['position'])
            
            max_position = len(main_cats) - 1
            
            if new_position < 0 or new_position > max_position:
                raise ValidationError(f"Position must be between 0 and {max_position}")
            
            if old_position == new_position:
                return True
            
            # Find current category in the list (case-insensitive)
            current_idx = None
            for idx, cat in enumerate(main_cats):
                if cat['lower_main'] == main_category.lower():
                    current_idx = idx
                    break
            
            if current_idx is None:
                return False
            
            # Reorder the list
            cat_to_move = main_cats.pop(current_idx)
            main_cats.insert(new_position, cat_to_move)
            
            # Update positions for all main categories
            for idx, cat in enumerate(main_cats):
                cls.objects.filter(main_category__iexact=cat['main_category']).update(
                    position=idx,
                    updated_at=timezone.now()
                )
            
            return True
        except cls.DoesNotExist:
            return False


def get_upload_path(instance, filename):
    """Generate a safe upload path with a short unique filename"""
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = '.jpg'
    
    # Use UUID for unique short filename
    unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
    return os.path.join('temp', unique_name)


class ImagineAsset(models.Model):
    """Individual asset/image model"""
    batch = models.ForeignKey(
        ImagineAssetBatch, 
        on_delete=models.CASCADE, 
        related_name='images',
        verbose_name="Category"
    )
    image = models.ImageField(
        upload_to=get_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        max_length=500
    )
    image_number = models.IntegerField(db_index=True)
    is_premium = models.BooleanField(default=False, verbose_name="Premium")
    tags = models.JSONField(default=list, blank=True, help_text="List of object tags", verbose_name="Objects")
    
    # Track if image has been finalized
    is_finalized = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Create Assets"
        verbose_name_plural = "Create Assets"
        ordering = ['batch__position', 'batch__main_category', 'image_number']
        indexes = [
            models.Index(fields=['batch', 'image_number']),
        ]
    
    def __str__(self):
        return f"{self.batch} - Image {self.image_number}"
    
    def get_final_image_path(self):
        """Generate the correct final path for the image"""
        category_path = self.batch.get_category_path()
        filename = f"{self.image_number}.jpg"
        return os.path.join('assets', 'Imagine-New', category_path, filename)
    
    def get_physical_file_path(self):
        """Get the absolute file system path of the image"""
        from django.conf import settings
        return os.path.join(settings.MEDIA_ROOT, self.image.name)
    
    def finalize_image(self):
        """Move image from temp to final location and convert to JPG"""
        if self.is_finalized or not self.image:
            return
        
        from PIL import Image
        from django.conf import settings
        
        try:
            old_path = self.image.path
            new_relative_path = self.get_final_image_path()
            new_full_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
            
            # Open and convert image
            img = Image.open(old_path)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as JPG
            img.save(new_full_path, 'JPEG', quality=95)
            img.close()
            
            # Remove old temp file
            if os.path.exists(old_path) and old_path != new_full_path:
                try:
                    os.remove(old_path)
                except Exception as e:
                    print(f"Could not remove temp file: {e}")
            
            # Update image field to new path
            self.image.name = new_relative_path
            self.is_finalized = True
            
            # Save without triggering save again
            ImagineAsset.objects.filter(pk=self.pk).update(
                image=new_relative_path, 
                is_finalized=True,
                updated_at=timezone.now()
            )
            
        except Exception as e:
            print(f"Error finalizing image: {e}")
            raise
    
    def rename_image_file(self, new_number):
        """Rename the physical image file to match new image_number"""
        from django.conf import settings
        
        if not self.is_finalized or not self.image:
            return False
        
        try:
            old_path = self.get_physical_file_path()
            
            # Generate new path
            category_path = self.batch.get_category_path()
            new_filename = f"{new_number}.jpg"
            new_relative_path = os.path.join('assets', 'Imagine-New', category_path, new_filename)
            new_full_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
            
            # Rename/move the file
            if os.path.exists(old_path):
                shutil.move(old_path, new_full_path)
                
                # Update database
                self.image.name = new_relative_path
                ImagineAsset.objects.filter(pk=self.pk).update(
                    image=new_relative_path,
                    updated_at=timezone.now()
                )
                
                return True
            else:
                print(f"Warning: Old file not found: {old_path}")
                return False
                
        except Exception as e:
            print(f"Error renaming image file: {e}")
            return False
    
    def delete(self, *args, **kwargs):
        """Override delete to remove physical file and reindex remaining images"""
        # Delete physical file
        try:
            if self.image and os.path.exists(self.get_physical_file_path()):
                os.remove(self.get_physical_file_path())
        except Exception as e:
            print(f"Error deleting physical file: {e}")
        
        batch = self.batch
        super().delete(*args, **kwargs)
        ImagineAsset.reindex_batch(batch.id)
    
    @classmethod
    def reindex_batch(cls, batch_id):
        """Reindex all images in a specific batch from 0 onwards"""
        images = cls.objects.filter(batch_id=batch_id).order_by('image_number')
        
        for index, image in enumerate(images):
            if image.image_number != index:
                # Rename the physical file
                old_number = image.image_number
                image.image_number = index
                
                if image.is_finalized:
                    from django.conf import settings
                    category_path = image.batch.get_category_path()
                    old_filename = f"{old_number}.jpg"
                    new_filename = f"{index}.jpg"
                    
                    old_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                                 category_path, old_filename)
                    new_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                                 category_path, new_filename)
                    
                    try:
                        if os.path.exists(old_full_path):
                            shutil.move(old_full_path, new_full_path)
                            
                            new_relative_path = os.path.join('assets', 'Imagine-New', 
                                                            category_path, new_filename)
                            cls.objects.filter(pk=image.pk).update(
                                image_number=index,
                                image=new_relative_path,
                                updated_at=timezone.now()
                            )
                    except Exception as e:
                        print(f"Error reindexing image file: {e}")
                        cls.objects.filter(pk=image.pk).update(
                            image_number=index,
                            updated_at=timezone.now()
                        )
                else:
                    cls.objects.filter(pk=image.pk).update(
                        image_number=index,
                        updated_at=timezone.now()
                    )
    
    @classmethod
    @transaction.atomic
    def swap_positions(cls, image_id_1, image_id_2):
        """Swap TWO images completely - including file names, metadata, and positions"""
        from django.conf import settings
        
        try:
            image1 = cls.objects.select_for_update().get(pk=image_id_1)
            image2 = cls.objects.select_for_update().get(pk=image_id_2)
            
            if image1.batch_id != image2.batch_id:
                raise ValidationError("Can only swap images within the same category/subcategory")
            
            # Store all data from both images
            img1_number = image1.image_number
            img2_number = image2.image_number
            
            img1_premium = image1.is_premium
            img2_premium = image2.is_premium
            
            img1_tags = list(image1.tags) if image1.tags else []
            img2_tags = list(image2.tags) if image2.tags else []
            
            # Swap physical files if finalized
            if image1.is_finalized and image2.is_finalized:
                category_path = image1.batch.get_category_path()
                
                img1_filename = f"{img1_number}.jpg"
                img2_filename = f"{img2_number}.jpg"
                
                img1_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                             category_path, img1_filename)
                img2_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                             category_path, img2_filename)
                
                # Use temporary file to avoid conflicts
                temp_path = img1_full_path + '.swaptmp'
                
                try:
                    if os.path.exists(img1_full_path) and os.path.exists(img2_full_path):
                        # Move img1 to temp
                        shutil.move(img1_full_path, temp_path)
                        # Move img2 to img1 position
                        shutil.move(img2_full_path, img1_full_path)
                        # Move temp (original img1) to img2 position
                        shutil.move(temp_path, img2_full_path)
                except Exception as e:
                    print(f"Error swapping physical files: {e}")
                    # Try to restore if something went wrong
                    if os.path.exists(temp_path):
                        shutil.move(temp_path, img1_full_path)
                    raise
            
            # Now swap ALL data including metadata (NOT image_number which stays with position)
            # Image 1 gets Image 2's metadata
            image1.is_premium = img2_premium
            image1.tags = img2_tags
            image1.updated_at = timezone.now()
            image1.save(update_fields=['is_premium', 'tags', 'updated_at'])
            
            # Image 2 gets Image 1's metadata
            image2.is_premium = img1_premium
            image2.tags = img1_tags
            image2.updated_at = timezone.now()
            image2.save(update_fields=['is_premium', 'tags', 'updated_at'])
            
            # Refresh from database to get updated data
            image1.refresh_from_db()
            image2.refresh_from_db()
            
            return True
            
        except cls.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error in swap_positions: {e}")
            raise
    
    @classmethod
    @transaction.atomic
    def move_to_position(cls, image_id, new_image_number):
        """Move an image to a specific position within its batch"""
        from django.conf import settings
        
        try:
            image = cls.objects.select_for_update().get(pk=image_id)
            old_number = image.image_number
            batch = image.batch
            
            max_number = cls.objects.filter(batch=batch).count() - 1
            if new_image_number < 0 or new_image_number > max_number:
                raise ValidationError(f"Image number must be between 0 and {max_number}")
            
            if old_number == new_image_number:
                return True
            
            category_path = batch.get_category_path()
            
            # Get all images in correct order
            all_images = list(cls.objects.filter(batch=batch).order_by('image_number'))
            
            # Remove the image we're moving from its current position
            moving_image = None
            for i, img in enumerate(all_images):
                if img.pk == image.pk:
                    moving_image = all_images.pop(i)
                    break
            
            # Insert it at the new position
            all_images.insert(new_image_number, moving_image)
            
            # Now rename all files using temp names first
            temp_mappings = []
            for idx, img in enumerate(all_images):
                if img.is_finalized:
                    old_filename = f"{img.image_number}.jpg"
                    old_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                                category_path, old_filename)
                    
                    if os.path.exists(old_full_path):
                        temp_name = f"temp_{uuid.uuid4().hex[:8]}_{idx}.jpg"
                        temp_full_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New', 
                                                     category_path, temp_name)
                        shutil.move(old_full_path, temp_full_path)
                        temp_mappings.append({
                            'pk': img.pk,
                            'temp_path': temp_full_path,
                            'new_number': idx
                        })
            
            # Now move temp files to final positions and update database
            for mapping in temp_mappings:
                new_filename = f"{mapping['new_number']}.jpg"
                new_relative_path = os.path.join('assets', 'Imagine-New', category_path, new_filename)
                new_full_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)
                
                shutil.move(mapping['temp_path'], new_full_path)
                
                # Update database
                cls.objects.filter(pk=mapping['pk']).update(
                    image_number=mapping['new_number'],
                    image=new_relative_path,
                    updated_at=timezone.now()
                )
            
            # Update any non-finalized images
            for idx, img in enumerate(all_images):
                if not img.is_finalized:
                    cls.objects.filter(pk=img.pk).update(
                        image_number=idx,
                        updated_at=timezone.now()
                    )
            
            return True
            
        except cls.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error in move_to_position: {e}")
            raise
    
    def to_json_format(self):
        """Convert to the original JSON format"""
        return {
            f"Image{self.image_number}": {
                "Name": str(self.image_number),
                "Prem": self.is_premium,
                "main_category": self.batch.main_category,
                "sub_category": self.batch.sub_category or "",
                "objects": self.tags if isinstance(self.tags, list) else []
            }
        }