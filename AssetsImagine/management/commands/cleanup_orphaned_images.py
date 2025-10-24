"""
Management command to clean up orphaned images
Place this file in: AssetsImagine/management/commands/cleanup_orphaned_images.py

Usage: python manage.py cleanup_orphaned_images
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from AssetsImagine.models import ImagineAsset, ImagineAssetBatch
import os


class Command(BaseCommand):
    help = 'Clean up orphaned images and sync database with filesystem'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('Starting cleanup process...\n'))
        
        # 1. Find images in filesystem that don't exist in database
        imagine_path = os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New')
        
        if not os.path.exists(imagine_path):
            self.stdout.write(self.style.WARNING(f'Path does not exist: {imagine_path}'))
            return
        
        orphaned_files = []
        missing_files = []
        
        # Walk through filesystem
        for root, dirs, files in os.walk(imagine_path):
            for filename in files:
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    continue
                
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, settings.MEDIA_ROOT)
                
                # Check if this file exists in database
                exists = ImagineAsset.objects.filter(image=relative_path).exists()
                
                if not exists:
                    orphaned_files.append(full_path)
        
        # 2. Find database entries that don't have physical files
        for asset in ImagineAsset.objects.all():
            if asset.image:
                full_path = os.path.join(settings.MEDIA_ROOT, asset.image.name)
                if not os.path.exists(full_path):
                    missing_files.append({
                        'id': asset.id,
                        'path': full_path,
                        'asset': asset
                    })
        
        # Report findings
        self.stdout.write(self.style.WARNING(f'\nFound {len(orphaned_files)} orphaned files in filesystem'))
        self.stdout.write(self.style.WARNING(f'Found {len(missing_files)} database entries with missing files\n'))
        
        if orphaned_files:
            self.stdout.write(self.style.WARNING('Orphaned files:'))
            for f in orphaned_files[:10]:  # Show first 10
                self.stdout.write(f'  - {f}')
            if len(orphaned_files) > 10:
                self.stdout.write(f'  ... and {len(orphaned_files) - 10} more')
        
        if missing_files:
            self.stdout.write(self.style.WARNING('\nDatabase entries with missing files:'))
            for item in missing_files[:10]:  # Show first 10
                self.stdout.write(f'  - ID {item["id"]}: {item["path"]}')
            if len(missing_files) > 10:
                self.stdout.write(f'  ... and {len(missing_files) - 10} more')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('\n✓ Dry run complete. No changes made.'))
            return
        
        # Perform cleanup
        if orphaned_files or missing_files:
            confirm = input('\nDo you want to proceed with cleanup? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cleanup cancelled.'))
                return
        
        # Delete orphaned files
        deleted_count = 0
        for file_path in orphaned_files:
            try:
                os.remove(file_path)
                deleted_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting {file_path}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {deleted_count} orphaned files'))
        
        # Delete database entries with missing files
        db_deleted = 0
        for item in missing_files:
            try:
                item['asset'].delete()
                db_deleted += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting DB entry {item["id"]}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {db_deleted} database entries with missing files'))
        
        # 3. Verify image numbering consistency
        self.stdout.write(self.style.SUCCESS('\nVerifying image numbering...'))
        
        for batch in ImagineAssetBatch.objects.all():
            images = ImagineAsset.objects.filter(batch=batch).order_by('image_number')
            expected_number = 0
            issues = []
            
            for img in images:
                if img.image_number != expected_number:
                    issues.append(f'Expected {expected_number}, found {img.image_number}')
                expected_number += 1
            
            if issues:
                self.stdout.write(self.style.WARNING(f'Batch {batch}: Numbering issues found'))
                for issue in issues:
                    self.stdout.write(f'  - {issue}')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Cleanup complete!'))