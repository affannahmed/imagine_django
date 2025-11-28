from django.core.management.base import BaseCommand
from django.core.cache import cache
from pixverse.models import Effect, EffectCategory


class Command(BaseCommand):
    help = 'Fix database video paths for renamed categories'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting path fixes...'))
        
        # Define the path fixes: (old_folder_name, new_folder_name, category_name)
        fixes = [
            ('dance_zone', 'dance_world', 'Dance World'),
            ('the_banana_lab', 'banana_lab', 'Banana Lab'),
            ('imagine_halloween', 'after_dark', 'After Dark'),
        ]
        
        total_updated = 0
        
        for old_folder, new_folder, category_name in fixes:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Processing: {category_name}")
            self.stdout.write(f"Old folder: {old_folder}")
            self.stdout.write(f"New folder: {new_folder}")
            self.stdout.write('='*60)
            
            try:
                # Get the category
                category = EffectCategory.objects.get(name=category_name)
                self.stdout.write(self.style.SUCCESS(f"✓ Found category: {category.name}"))
                
                # Get all effects in this category
                effects = Effect.objects.filter(category=category)
                self.stdout.write(f"Found {effects.count()} effects in this category")
                
                old_prefix = f'pixverse_effects_imagine/{old_folder}/'
                new_prefix = f'pixverse_effects_imagine/{new_folder}/'
                
                category_updates = 0
                
                for effect in effects:
                    video_updated = False
                    thumbnail_updated = False
                    
                    # Check and update video path
                    if effect.video:
                        old_path = str(effect.video.name)
                        if old_prefix in old_path:
                            new_path = old_path.replace(old_prefix, new_prefix)
                            effect.video.name = new_path
                            video_updated = True
                            self.stdout.write(f"  Video: {old_path}")
                            self.stdout.write(f"      → {new_path}")
                    
                    # Check and update thumbnail path
                    if effect.thumbnailVideoUrl:
                        old_path = str(effect.thumbnailVideoUrl.name)
                        if old_prefix in old_path:
                            new_path = old_path.replace(old_prefix, new_prefix)
                            effect.thumbnailVideoUrl.name = new_path
                            thumbnail_updated = True
                            self.stdout.write(f"  Thumbnail: {old_path}")
                            self.stdout.write(f"          → {new_path}")
                    
                    # Save if updated
                    if video_updated or thumbnail_updated:
                        effect.save()
                        category_updates += 1
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Updated: {effect.display_name}"))
                
                self.stdout.write(self.style.SUCCESS(f"\n✓ Category '{category_name}': {category_updates} effects updated"))
                total_updated += category_updates
                
            except EffectCategory.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"✗ Category not found: {category_name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error processing {category_name}: {str(e)}"))
        
        # Clear cache
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Clearing cache...")
        cache.clear()
        self.stdout.write(self.style.SUCCESS("✓ Cache cleared"))
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(f"✓ DONE! Total effects updated: {total_updated}"))
        self.stdout.write('='*60)