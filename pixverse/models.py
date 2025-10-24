import os
import shutil
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver


def effect_video_upload_path(instance, filename):
    """
    Generate upload path for effect videos organized by category
    Videos will be saved in media/pixverse_effects_imagine/{category_name}/{effect_name}.{ext}
    """
    ext = filename.split('.')[-1]
    filename = f"{instance.name}.{ext}"
    category_name = instance.category.name.replace(' ', '_').lower()
    return os.path.join('pixverse_effects_imagine', category_name, filename)


def effect_thumbnail_video_upload_path(instance, filename):
    """
    Generate upload path for effect thumbnail videos organized by category
    Thumbnail videos will be saved in media/pixverse_effects_imagine/{category_name}/{effect_name}_thumbnail.mp4
    """
    category_name = instance.category.name.replace(' ', '_').lower()
    thumbnail_filename = f"{instance.name}_thumbnail.mp4"
    return os.path.join('pixverse_effects_imagine', category_name, thumbnail_filename)


class EffectCategory(models.Model):
    """
    Category model to group effects
    Each category has a position (0-based indexing)
    """
    name = models.CharField(
        max_length=150,
        unique=True,
        help_text="Unique category name (e.g., 'Transitions', 'Overlays')"
    )
    
    position = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Position/Index of the category (0-based)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Effect Category"
        verbose_name_plural = "Effect Categories"
        ordering = ["position"]
        indexes = [
            models.Index(fields=['position']),
        ]

    def __str__(self):
        return f"[{self.position}] {self.name}"

    def save(self, *args, **kwargs):
        """Override save to auto-assign position if new and clear cache"""
        is_new = self.pk is None
        old_name = None
        field_changed = False
        
        if is_new:
            max_position = EffectCategory.objects.aggregate(
                max_pos=models.Max('position')
            )['max_pos']
            
            if max_position is not None:
                self.position = max_position + 1
            else:
                self.position = 0
        else:
            # Get old instance to check for name change
            try:
                existing = EffectCategory.objects.get(pk=self.pk)
                if existing.name != self.name:
                    old_name = existing.name
                    field_changed = True
            except EffectCategory.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Handle folder rename if category name changed
        if old_name and field_changed:
            self._rename_category_folder(old_name, self.name)
        
        self.clear_cache()
        
        # Increment version on creation OR field update
        if is_new or field_changed:
            self.increment_version()

    def _rename_category_folder(self, old_name, new_name):
        """Rename the category folder in media directory"""
        try:
            old_folder_name = old_name.replace(' ', '_').lower()
            new_folder_name = new_name.replace(' ', '_').lower()
            
            old_path = os.path.join(settings.MEDIA_ROOT, 'pixverse_effects_imagine', old_folder_name)
            new_path = os.path.join(settings.MEDIA_ROOT, 'pixverse_effects_imagine', new_folder_name)
            
            # Only rename if old folder exists and new folder doesn't
            if os.path.exists(old_path) and not os.path.exists(new_path):
                shutil.move(old_path, new_path)
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error renaming category folder: {str(e)}")

    def delete(self, *args, **kwargs):
        """Override delete to reindex remaining categories and clear cache"""
        position_to_delete = self.position
        super().delete(*args, **kwargs)
        
        # Reindex all categories after deletion
        EffectCategory.objects.filter(position__gt=position_to_delete).update(
            position=models.F('position') - 1
        )
        
        self.increment_version()
        self.clear_cache()

    @classmethod
    def clear_cache(cls):
        """Clear all category-related cache"""
        cache.delete('effect_categories_meta')
        cache.delete('all_categories')
        cache.delete('pixverse_version_meta')
        cache.delete('pixverse_all_categories')
        for i in range(1000):
            cache.delete(f'category_position_{i}')
            cache.delete(f'pixverse_effects_index_{i}')

    @classmethod
    def reindex_all(cls):
        """Reindex all categories from 0 onwards"""
        with transaction.atomic():
            categories = cls.objects.select_for_update().order_by('position', 'created_at')
            for index, category in enumerate(categories):
                if category.position != index:
                    cls.objects.filter(pk=category.pk).update(position=index)
            
            transaction.on_commit(lambda: cls.increment_version())
            transaction.on_commit(lambda: cls.clear_cache())

    @classmethod
    def swap_positions(cls, category_id_1, category_id_2):
        """Swap positions between two categories"""
        with transaction.atomic():
            try:
                cat1 = cls.objects.select_for_update().get(pk=category_id_1)
                cat2 = cls.objects.select_for_update().get(pk=category_id_2)
                
                pos1 = cat1.position
                pos2 = cat2.position
                
                # Use a temporary position that's guaranteed not to conflict
                max_pos = cls.objects.aggregate(m=models.Max('position'))['m'] or 0
                temp_position = max_pos + 10000
                
                cls.objects.filter(pk=cat1.pk).update(position=temp_position)
                cls.objects.filter(pk=cat2.pk).update(position=pos1)
                cls.objects.filter(pk=cat1.pk).update(position=pos2)
                
                transaction.on_commit(lambda: cls.increment_version())
                transaction.on_commit(lambda: cls.clear_cache())
                
                return True
            except cls.DoesNotExist:
                return False

    @classmethod
    def move_to_position(cls, category_id, new_position):
        """Move a category to a specific position"""
        with transaction.atomic():
            try:
                category = cls.objects.select_for_update().get(pk=category_id)
                old_position = category.position
                
                max_position = cls.objects.count() - 1
                if new_position < 0 or new_position > max_position:
                    raise ValidationError(f"Position must be between 0 and {max_position}")
                
                if old_position == new_position:
                    return True
                
                # Step 1: Move target category to a safe temporary position
                max_pos = cls.objects.aggregate(m=models.Max('position'))['m'] or 0
                temp_position = max_pos + 10000
                cls.objects.filter(pk=category_id).update(position=temp_position)
                
                # Step 2: Shift other categories
                if new_position < old_position:
                    # Moving up: shift affected categories down (increase position)
                    cls.objects.filter(
                        position__gte=new_position,
                        position__lt=old_position
                    ).exclude(pk=category_id).update(
                        position=models.F('position') + 1
                    )
                else:
                    # Moving down: shift affected categories up (decrease position)
                    cls.objects.filter(
                        position__gt=old_position,
                        position__lte=new_position
                    ).exclude(pk=category_id).update(
                        position=models.F('position') - 1
                    )
                
                # Step 3: Move target category to final position
                cls.objects.filter(pk=category_id).update(position=new_position)
                
                transaction.on_commit(lambda: cls.increment_version())
                transaction.on_commit(lambda: cls.clear_cache())
                return True
            except cls.DoesNotExist:
                return False

    @classmethod
    def increment_version(cls):
        """Increment the meta version"""
        meta_obj, created = EffectMeta.objects.get_or_create(id=1)
        meta_obj.current_version += 1
        meta_obj.save()


class Effect(models.Model):
    """
    Effect model - associated with a category
    Position is relative within the category (0, 1, 2, ...)
    Each effect has both a video and an optional thumbnail video preview
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique internal name for the effect (e.g., 'fire_transition')"
    )
    
    display_name = models.CharField(
        max_length=150,
        help_text="Display name in App (e.g., 'Fire Transition')"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description about the effect"
    )
    
    category = models.ForeignKey(
        EffectCategory,
        on_delete=models.CASCADE,
        related_name='effects',
        help_text="Category this effect belongs to"
    )
    
    template_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Pixverse Template ID"
    )
    
    cost = models.CharField(
        max_length=50,
        default="",
        blank=True,
        help_text="Cost of the effect (e.g., '0', '99', '199'). Leave empty for free effects."
    )
    
    Prem = models.BooleanField(default=False, help_text="Whether this effect is premium")
    
    position = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Position/Index of the effect within its category (0-based)"
    )

    video = models.FileField(
        upload_to=effect_video_upload_path,
        help_text="Upload a sample video showing the effect"
    )
    
    thumbnailVideoUrl = models.FileField(
        upload_to=effect_thumbnail_video_upload_path,
        blank=True,
        null=True,
        help_text="Upload a thumbnail video preview of the effect (optional)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Effect"
        verbose_name_plural = "Video Effects"
        ordering = ["category__position", "position"]
        indexes = [
            models.Index(fields=['category', 'position']),
        ]
        unique_together = [['category', 'position']]

    def __str__(self):
        return f"[{self.category.name}] {self.display_name}"

    @property
    def video_url(self):
        """Get the full URL of the video"""
        if self.video:
            return self.video.url
        return None

    @property
    def thumbnail_video_url(self):
        """Get the full URL of the thumbnail video"""
        if self.thumbnailVideoUrl:
            return self.thumbnailVideoUrl.url
        return None

    def save(self, *args, **kwargs):
        """Override save to auto-assign position within category if new"""
        is_new = self.pk is None
        old_instance = None
        field_changed = False
        
        if is_new:
            max_position = Effect.objects.filter(
                category=self.category
            ).aggregate(max_pos=models.Max('position'))['max_pos']
            
            if max_position is not None:
                self.position = max_position + 1
            else:
                self.position = 0
        else:
            # Get old instance to check for changes
            try:
                old_instance = Effect.objects.get(pk=self.pk)
                if (old_instance.name != self.name or 
                    old_instance.display_name != self.display_name or
                    old_instance.description != self.description or
                    old_instance.Prem != self.Prem or
                    old_instance.template_id != self.template_id or
                    old_instance.cost != self.cost or
                    old_instance.video != self.video or
                    old_instance.thumbnailVideoUrl != self.thumbnailVideoUrl):
                    field_changed = True
            except Effect.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Handle video file management if video was updated
        if old_instance and old_instance.video and old_instance.video != self.video:
            self._handle_video_update(old_instance)
        
        # Handle thumbnail video file management if thumbnail was updated
        if old_instance and old_instance.thumbnailVideoUrl and old_instance.thumbnailVideoUrl != self.thumbnailVideoUrl:
            self._handle_thumbnail_video_update(old_instance)
        
        self.clear_cache()
        
        # Increment version on creation OR field update
        if is_new or field_changed:
            self.increment_version()

    def _handle_video_update(self, old_instance):
        """Delete old video file and ensure new one is in correct location"""
        try:
            # Delete old video file if it exists
            if old_instance.video:
                old_video_path = os.path.join(settings.MEDIA_ROOT, old_instance.video.name)
                if os.path.exists(old_video_path):
                    os.remove(old_video_path)
        except Exception as e:
            print(f"Error handling video update: {str(e)}")

    def _handle_thumbnail_video_update(self, old_instance):
        """Delete old thumbnail video file and ensure new one is in correct location"""
        try:
            # Delete old thumbnail video file if it exists
            if old_instance.thumbnailVideoUrl:
                old_thumbnail_path = os.path.join(settings.MEDIA_ROOT, old_instance.thumbnailVideoUrl.name)
                if os.path.exists(old_thumbnail_path):
                    os.remove(old_thumbnail_path)
        except Exception as e:
            print(f"Error handling thumbnail video update: {str(e)}")

    def delete(self, *args, **kwargs):
        """Override delete to reindex effects in category and delete video/thumbnail"""
        # Delete video file
        if self.video:
            try:
                video_path = os.path.join(settings.MEDIA_ROOT, self.video.name)
                if os.path.exists(video_path):
                    os.remove(video_path)
            except Exception as e:
                print(f"Error deleting video file: {str(e)}")
        
        # Delete thumbnail video file
        if self.thumbnailVideoUrl:
            try:
                thumbnail_path = os.path.join(settings.MEDIA_ROOT, self.thumbnailVideoUrl.name)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            except Exception as e:
                print(f"Error deleting thumbnail video file: {str(e)}")
        
        category = self.category
        position_to_delete = self.position
        super().delete(*args, **kwargs)
        
        # Reindex all effects after deletion in this category
        Effect.objects.filter(
            category=category,
            position__gt=position_to_delete
        ).update(position=models.F('position') - 1)
        
        self.increment_version()
        self.clear_cache()

    @classmethod
    def clear_cache(cls):
        """Clear all effect-related cache"""
        cache.delete('effect_meta')
        cache.delete('all_effects')
        cache.delete('pixverse_version_meta')
        cache.delete('pixverse_all_categories')
        cache.delete('pixverse_trending_effects')
        for i in range(10000):
            cache.delete(f'effect_position_{i}')
            cache.delete(f'pixverse_effects_index_{i}')

    @classmethod
    def reindex_category(cls, category_id):
        """Reindex all effects within a specific category from 0 onwards"""
        with transaction.atomic():
            effects = cls.objects.filter(
                category_id=category_id
            ).select_for_update().order_by('position', 'created_at')
            
            for index, effect in enumerate(effects):
                if effect.position != index:
                    cls.objects.filter(pk=effect.pk).update(position=index)
            
            transaction.on_commit(lambda: cls.increment_version())
            transaction.on_commit(lambda: cls.clear_cache())

    @classmethod
    def swap_positions(cls, effect_id_1, effect_id_2):
        """Swap positions between two effects (must be in same category)"""
        with transaction.atomic():
            try:
                effect1 = cls.objects.select_for_update().get(pk=effect_id_1)
                effect2 = cls.objects.select_for_update().get(pk=effect_id_2)
                
                if effect1.category_id != effect2.category_id:
                    raise ValidationError("Can only swap effects in the same category")
                
                pos1 = effect1.position
                pos2 = effect2.position
                
                # Use high temp position to avoid conflicts
                max_pos = cls.objects.filter(
                    category=effect1.category
                ).aggregate(m=models.Max('position'))['m'] or 0
                temp_position = max_pos + 10000
                
                cls.objects.filter(pk=effect1.pk).update(position=temp_position)
                cls.objects.filter(pk=effect2.pk).update(position=pos1)
                cls.objects.filter(pk=effect1.pk).update(position=pos2)
                
                transaction.on_commit(lambda: cls.increment_version())
                transaction.on_commit(lambda: cls.clear_cache())
                
                return True
            except cls.DoesNotExist:
                return False

    @classmethod
    def move_to_position(cls, effect_id, new_position):
        """Move an effect to a new position within its category"""
        with transaction.atomic():
            try:
                effect = cls.objects.select_for_update().get(pk=effect_id)
                old_position = effect.position
                category = effect.category
                
                max_position = cls.objects.filter(category=category).count() - 1
                if new_position < 0 or new_position > max_position:
                    raise ValidationError(f"Position must be between 0 and {max_position}")
                
                if old_position == new_position:
                    return True
                
                # Step 1: Move target effect to a safe temporary position
                max_pos = cls.objects.filter(
                    category=category
                ).aggregate(m=models.Max('position'))['m'] or 0
                temp_position = max_pos + 10000
                cls.objects.filter(pk=effect_id).update(position=temp_position)
                
                # Step 2: Shift other effects
                if new_position < old_position:
                    # Moving up: shift affected effects down (increase position)
                    cls.objects.filter(
                        category=category,
                        position__gte=new_position,
                        position__lt=old_position
                    ).exclude(pk=effect_id).update(
                        position=models.F('position') + 1
                    )
                else:
                    # Moving down: shift affected effects up (decrease position)
                    cls.objects.filter(
                        category=category,
                        position__gt=old_position,
                        position__lte=new_position
                    ).exclude(pk=effect_id).update(
                        position=models.F('position') - 1
                    )
                
                # Step 3: Move target effect to final position
                cls.objects.filter(pk=effect_id).update(position=new_position)
                
                transaction.on_commit(lambda: cls.increment_version())
                transaction.on_commit(lambda: cls.clear_cache())
                return True
            except cls.DoesNotExist:
                return False

    @classmethod
    def increment_version(cls):
        """Increment the meta version"""
        meta_obj, created = EffectMeta.objects.get_or_create(id=1)
        meta_obj.current_version += 1
        meta_obj.save()


class EffectMeta(models.Model):
    """Metadata model for versioning"""
    current_version = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Check Version"
        verbose_name_plural = "Check Version"

    def __str__(self):
        return f"Version {self.current_version}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('effect_meta')
        cache.delete('pixverse_version_meta')