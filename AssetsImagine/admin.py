from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import ImagineAssetBatch, ImagineAsset
from .forms import BulkImageUploadForm, ImageAssetFormSet


@admin.register(ImagineAsset)
class ImagineAssetAdmin(admin.ModelAdmin):
    list_display = [
        'image_preview_small', 
        'category_display',
        'main_category_position',
        'image_number', 
        'is_premium', 
        'tag_display', 
        'created_at',
        'action_buttons'
    ]
    list_filter = ['is_premium', 'batch__main_category', 'created_at']
    search_fields = ['batch__main_category', 'batch__sub_category', 'tags']
    readonly_fields = ['image_preview', 'created_at', 'updated_at']
    
    ordering = ['batch__position', 'batch__main_category', 'batch__sub_category', 'image_number']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_filters'] = False
        
        # Get unique main categories with positions (SQLite compatible)
        positions_info = []
        seen_categories = {}
        
        # Get all batches ordered by position
        all_batches = ImagineAssetBatch.objects.all().order_by('position', 'main_category')
        
        for batch in all_batches:
            main_cat_lower = batch.main_category.lower()
            if main_cat_lower not in seen_categories:
                seen_categories[main_cat_lower] = {
                    'position': batch.position,
                    'category': batch.main_category
                }
        
        # Convert to list and sort by position
        positions_info = sorted(seen_categories.values(), key=lambda x: x['position'])
        
        extra_context['positions_info'] = positions_info
        return super().changelist_view(request, extra_context=extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        return redirect('admin:assetsImagine_bulk_upload')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-upload/', self.admin_site.admin_view(self.bulk_upload_view), name='assetsImagine_bulk_upload'),
            path('configure-images/', self.admin_site.admin_view(self.configure_images_view), name='assetsImagine_configure_images'),
            path('<int:asset_id>/move-image/', self.admin_site.admin_view(self.move_image_view), name='assetsImagine_move_image'),
            path('<int:asset_id>/swap-image/', self.admin_site.admin_view(self.swap_image_view), name='assetsImagine_swap_image'),
            path('batch/<int:batch_id>/move-category/', self.admin_site.admin_view(self.move_category_view), name='assetsImagine_move_category'),
        ]
        return custom_urls + urls
    
    def bulk_upload_view(self, request):
        if request.method == 'POST':
            form = BulkImageUploadForm(request.POST, request.FILES)
            
            if form.is_valid():
                main_category = form.cleaned_data.get('main_category')
                sub_category = form.cleaned_data.get('sub_category')
                
                if not main_category and request.POST.get('existing_category'):
                    existing = request.POST.get('existing_category')
                    parts = existing.split('|')
                    main_category = parts[0] if len(parts) > 0 else None
                    sub_category = parts[1] if len(parts) > 1 and parts[1] else None
                
                if not main_category:
                    messages.error(request, "Please select or enter a category.")
                    return redirect('admin:assetsImagine_bulk_upload')
                
                images = request.FILES.getlist('images')
                
                if not images:
                    messages.error(request, "Please select at least one image.")
                    return redirect('admin:assetsImagine_bulk_upload')
                
                # Get or create batch (case-insensitive check handled in model)
                batch, created = ImagineAssetBatch.objects.get_or_create(
                    main_category__iexact=main_category,
                    sub_category__iexact=sub_category if sub_category else None,
                    defaults={
                        'main_category': main_category,
                        'sub_category': sub_category or None
                    }
                )
                
                if created:
                    messages.info(request, f"Created new category: {batch} at position {batch.position}")
                
                # Store temporary image data in session
                request.session['bulk_upload_data'] = {
                    'batch_id': batch.id,
                    'image_count': len(images),
                    'main_category': main_category,
                    'sub_category': sub_category or ''
                }
                
                # Save images temporarily WITHOUT finalizing
                temp_image_ids = []
                starting_number = batch.get_next_image_number()
                
                for idx, image_file in enumerate(images):
                    asset = ImagineAsset(
                        batch=batch,
                        image=image_file,
                        image_number=starting_number + idx,
                        is_premium=False,
                        tags=[],
                        is_finalized=False
                    )
                    asset.save()
                    temp_image_ids.append(asset.id)
                
                request.session['temp_image_ids'] = temp_image_ids
                
                return redirect('admin:assetsImagine_configure_images')
        else:
            form = BulkImageUploadForm()
        
        batches = ImagineAssetBatch.objects.all().order_by('position', 'main_category', 'sub_category')
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'batches': batches,
            'title': 'Create Assets - Bulk Upload',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/AssetsImagine/bulk_upload.html', context)
    
    def configure_images_view(self, request):
        temp_image_ids = request.session.get('temp_image_ids', [])
        
        if not temp_image_ids:
            messages.error(request, "No images to configure. Please upload images first.")
            return redirect('admin:assetsImagine_bulk_upload')
        
        images = ImagineAsset.objects.filter(id__in=temp_image_ids).order_by('image_number')
        
        if request.method == 'POST':
            formset = ImageAssetFormSet(request.POST, queryset=images)
            
            if formset.is_valid():
                # Save all data and finalize images
                with transaction.atomic():
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.save()
                        # Now finalize the image (move to final location with correct number)
                        instance.finalize_image()
                
                # Clear session data
                request.session.pop('temp_image_ids', None)
                request.session.pop('bulk_upload_data', None)
                
                messages.success(request, f"✓ Successfully saved and processed {len(images)} images!")
                return redirect('admin:AssetsImagine_imagineasset_changelist')
            else:
                messages.error(request, "Please correct the errors below.")
        else:
            formset = ImageAssetFormSet(queryset=images)
        
        upload_data = request.session.get('bulk_upload_data', {})
        
        context = {
            **self.admin_site.each_context(request),
            'formset': formset,
            'images': images,
            'upload_data': upload_data,
            'title': 'Configure Image Properties',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/AssetsImagine/configure_images.html', context)
    
    def move_image_view(self, request, asset_id):
        """View to move an image to a new position within its batch"""
        asset = get_object_or_404(ImagineAsset, pk=asset_id)
        batch = asset.batch
        all_images = ImagineAsset.objects.filter(batch=batch).order_by('image_number')
        
        if request.method == 'POST':
            new_number = int(request.POST.get('new_image_number'))
            
            try:
                with transaction.atomic():
                    success = ImagineAsset.move_to_position(asset_id, new_number)
                    
                    if success:
                        messages.success(
                            request, 
                            f"✓ Image moved from position {asset.image_number} to position {new_number} in {batch}. "
                            f"Physical files renamed and database updated."
                        )
                    else:
                        messages.error(request, "Failed to move image.")
                        
            except Exception as e:
                messages.error(request, f"Error moving image: {str(e)}")
            
            return redirect('admin:AssetsImagine_imagineasset_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'asset': asset,
            'batch': batch,
            'all_images': all_images,
            'max_number': all_images.count() - 1,
            'opts': self.model._meta,
            'has_view_permission': True,
            'title': f'Move Image in {batch}',
        }
        
        return render(request, 'admin/AssetsImagine/move_image.html', context)
    
    def swap_image_view(self, request, asset_id):
        """View to swap an image with another in the same batch"""
        asset = get_object_or_404(ImagineAsset, pk=asset_id)
        batch = asset.batch
        other_images = ImagineAsset.objects.filter(batch=batch).exclude(pk=asset_id).order_by('image_number')
        
        if request.method == 'POST':
            swap_with_id = int(request.POST.get('swap_with'))
            
            try:
                swap_with_asset = get_object_or_404(ImagineAsset, pk=swap_with_id)
                
                with transaction.atomic():
                    success = ImagineAsset.swap_positions(asset_id, swap_with_id)
                    
                    if success:
                        messages.success(
                            request,
                            f"✓ Successfully swapped Image {asset.image_number} with Image {swap_with_asset.image_number} in {batch}. "
                            f"Physical images and metadata have been swapped."
                        )
                    else:
                        messages.error(request, "Failed to swap images.")
                        
            except Exception as e:
                messages.error(request, f"Error swapping images: {str(e)}")
            
            return redirect('admin:AssetsImagine_imagineasset_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'asset': asset,
            'batch': batch,
            'other_images': other_images,
            'opts': self.model._meta,
            'has_view_permission': True,
            'title': f'Swap Image in {batch}',
        }
        
        return render(request, 'admin/AssetsImagine/swap_image.html', context)
    
    def move_category_view(self, request, batch_id):
        """View to move an entire category/subcategory to a new position"""
        batch = get_object_or_404(ImagineAssetBatch, pk=batch_id)
        
        # Get all unique main categories with their positions (SQLite compatible)
        seen_categories = {}
        all_batches_list = ImagineAssetBatch.objects.all().order_by('position', 'main_category')
        
        for b in all_batches_list:
            main_cat_lower = b.main_category.lower()
            if main_cat_lower not in seen_categories:
                seen_categories[main_cat_lower] = {
                    'main_category': b.main_category,
                    'position': b.position
                }
        
        main_categories = sorted(seen_categories.values(), key=lambda x: x['position'])
        
        if request.method == 'POST':
            new_position = int(request.POST.get('new_position'))
            
            try:
                with transaction.atomic():
                    old_position = batch.position
                    success = ImagineAssetBatch.move_to_position(batch_id, new_position)
                    
                    if success:
                        # Refresh batch to get updated position
                        batch.refresh_from_db()
                        messages.success(
                            request,
                            f"✓ Main category '{batch.main_category}' moved from position {old_position} to position {new_position}. "
                            f"All subcategories and images remain intact."
                        )
                    else:
                        messages.error(request, "Failed to move category.")
                        
            except Exception as e:
                messages.error(request, f"Error moving category: {str(e)}")
            
            return redirect('admin:AssetsImagine_imagineasset_changelist')
        
        # Get all batches grouped by main category for display
        all_batches_grouped = {}
        for cat in main_categories:
            main_cat = cat['main_category']
            if main_cat not in all_batches_grouped:
                all_batches_grouped[main_cat] = {
                    'position': cat['position'],
                    'batches': []
                }
            
            batches = ImagineAssetBatch.objects.filter(main_category__iexact=main_cat).order_by('sub_category')
            for b in batches:
                all_batches_grouped[main_cat]['batches'].append(b)
        
        context = {
            **self.admin_site.each_context(request),
            'batch': batch,
            'all_batches_grouped': all_batches_grouped,
            'max_position': len(main_categories) - 1,
            'opts': self.model._meta,
            'has_view_permission': True,
            'title': f'Move Main Category: {batch.main_category}',
        }
        
        return render(request, 'admin/AssetsImagine/move_category.html', context)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}?t={}" style="max-height: 300px; max-width: 300px;" />',
                obj.image.url,
                obj.updated_at.timestamp() if obj.updated_at else ''
            )
        return "No image"
    image_preview.short_description = "Preview"
    
    def image_preview_small(self, obj):
        if obj.image:
            # Add timestamp to force browser refresh
            return format_html(
                '<img src="{}?t={}" style="max-height: 50px; max-width: 50px; border-radius: 4px;" />',
                obj.image.url,
                obj.updated_at.timestamp() if obj.updated_at else ''
            )
        return "No image"
    image_preview_small.short_description = "Preview"
    
    def category_display(self, obj):
        return str(obj.batch)
    category_display.short_description = "Category"
    category_display.admin_order_field = 'batch__position'
    
    def main_category_position(self, obj):
        """Display main category position"""
        return f"Pos {obj.batch.position}"
    main_category_position.short_description = "Cat Pos"
    main_category_position.admin_order_field = 'batch__position'
    
    def tag_display(self, obj):
        if obj.tags:
            tags_display = ', '.join(obj.tags[:3])
            if len(obj.tags) > 3:
                tags_display += f' (+{len(obj.tags) - 3} more)'
            return tags_display
        return "No tags"
    tag_display.short_description = "Tags"
    
    def action_buttons(self, obj):
        """Action buttons for swap and move operations"""
        return format_html(
            '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            '<a class="button" style="font-size:11px; padding:5px 10px; white-space: nowrap;" href="{}">↕ Move Image</a>'
            '<a class="button" style="font-size:11px; padding:5px 10px; white-space: nowrap;" href="{}">⇄ Swap Image</a>'
            '<a class="button" style="font-size:11px; padding:5px 10px; background:#28a745; color:white; white-space: nowrap;" href="{}">📦 Move Category</a>'
            '</div>',
            reverse('admin:assetsImagine_move_image', args=[obj.pk]),
            reverse('admin:assetsImagine_swap_image', args=[obj.pk]),
            reverse('admin:assetsImagine_move_category', args=[obj.batch.pk])
        )
    action_buttons.short_description = "Actions"