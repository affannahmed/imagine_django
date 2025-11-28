from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.core.cache import cache
from .models import EffectCategory, Effect, EffectMeta


def clear_all_pixverse_cache():
    """Clear all pixverse-related cache keys"""
    cache.delete('effect_categories_meta')
    cache.delete('all_categories')
    cache.delete('pixverse_version_meta')
    cache.delete('pixverse_all_categories')
    cache.delete('pixverse_trending_effects')
    cache.delete('effect_meta')
    cache.delete('all_effects')
    
    for i in range(10000):
        cache.delete(f'category_position_{i}')
        cache.delete(f'effect_position_{i}')
        cache.delete(f'pixverse_effects_index_{i}')
        


@admin.register(EffectMeta)
class EffectMetaAdmin(admin.ModelAdmin):
    """Admin for checking effect version"""
    change_list_template = 'admin/pixverse/effectmeta/change_list.html'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist to show custom view"""
        meta_obj, created = EffectMeta.objects.get_or_create(id=1)
        
        categories = EffectCategory.objects.all().order_by('position')
        category_data = []
        
        for category in categories:
            category_data.append({
                'name': category.name,
                'position': category.position,
                'effect_count': category.effects.count(),
            })
        
        extra_context = extra_context or {}
        extra_context.update({
            'current_version': meta_obj.current_version,
            'category_count': len(category_data),
            'categories': category_data,
            'total_effects': Effect.objects.count(),
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset-version/', self.admin_site.admin_view(self.reset_version_view), name='pixverse_reset_version'),
        ]
        return custom_urls + urls
    
    def reset_version_view(self, request):
        """View to reset version to 0"""
        meta_obj, created = EffectMeta.objects.get_or_create(id=1)
        
        if request.method == 'POST':
            old_version = meta_obj.current_version
            meta_obj.current_version = 0
            meta_obj.save()
            clear_all_pixverse_cache()
            messages.success(request, f"✓ Version reset from {old_version} to 0")
            return redirect('admin:pixverse_effectmeta_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'current_version': meta_obj.current_version,
            'opts': self.model._meta,
            'title': 'Reset Version',
        }
        
        return render(request, 'admin/pixverse/effectmeta/reset_version.html', context)


@admin.register(EffectCategory)
class EffectCategoryAdmin(admin.ModelAdmin):
    """Admin for managing effect categories"""
    list_display = ['position_display', 'name', 'effect_count', 'created_at', 'action_buttons']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at', 'position']
    ordering = ['position']
    
    def position_display(self, obj):
        return f"Position {obj.position}"
    position_display.short_description = "Pos"
    position_display.admin_order_field = 'position'
    
    def effect_count(self, obj):
        count = obj.effects.count()
        return format_html(
            '<span style="background: #417690; color: white; padding: 3px 8px; border-radius: 3px;">{} effect{}</span>',
            count,
            's' if count != 1 else ''
        )
    effect_count.short_description = "Effects"
    
    def action_buttons(self, obj):
        return format_html(
            '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            '<a class="button" style="font-size:11px; padding:5px 10px; white-space: nowrap;" href="{}">↕ Move Category</a>'
            '</div>',
            reverse('admin:pixverse_move_category', args=[obj.pk])
        )
    action_buttons.short_description = "Actions"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:category_id>/move-category/', self.admin_site.admin_view(self.move_category_view), name='pixverse_move_category'),
        ]
        return custom_urls + urls
    
    def move_category_view(self, request, category_id):
        """View to move a category to a new position"""
        category = get_object_or_404(EffectCategory, pk=category_id)
        all_categories = EffectCategory.objects.all().order_by('position')
        
        if request.method == 'POST':
            new_position = int(request.POST.get('new_position'))
            
            try:
                with transaction.atomic():
                    old_position = category.position
                    success = EffectCategory.move_to_position(category_id, new_position)
                    
                    if success:
                        clear_all_pixverse_cache()
                        messages.success(
                            request,
                            f"✓ Category '{category.name}' moved from position {old_position} to {new_position}. "
                            f"All effects remain intact."
                        )
                    else:
                        messages.error(request, "Failed to move category.")
            except Exception as e:
                messages.error(request, f"Error moving category: {str(e)}")
            
            return redirect('admin:pixverse_effectcategory_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'category': category,
            'all_categories': all_categories,
            'max_position': all_categories.count() - 1,
            'opts': self.model._meta,
            'title': f'Move Category: {category.name}',
        }
        
        return render(request, 'admin/pixverse/category/move_category.html', context)


@admin.register(Effect)
class EffectAdmin(admin.ModelAdmin):
    """Admin for managing video effects with thumbnail video support"""
    list_display = [
        'position_display',
        'video_preview_thumbnail',
        'thumbnail_video_preview_thumbnail',
        'display_name',
        'video_name_display',
        'category_display',
        'template_id_display',
        'cost_display',
        'is_premium_display',
        'created_at',
        'action_buttons'
    ]
    search_fields = ['name', 'display_name', 'category__name']
    readonly_fields = ['created_at', 'updated_at', 'video_preview', 'thumbnail_video_preview', 'position']
    ordering = ['category__position', 'position']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description')
        }),
        ('Category & Position', {
            'fields': ('category', 'position')
        }),
        ('Configuration', {
            'fields': ('Prem', 'template_id', 'cost')
        }),
        ('Media', {
            'fields': ('video', 'video_preview', 'thumbnailVideoUrl', 'thumbnail_video_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def position_display(self, obj):
        return f"Pos {obj.position}"
    position_display.short_description = "Position"
    position_display.admin_order_field = 'position'
    
    def video_preview_thumbnail(self, obj):
        """Display video thumbnail in list view"""
        if obj.video:
            return format_html(
                '<div style="width: 60px; height: 45px; border-radius: 4px; overflow: hidden; background: #f0f0f0; display: flex; align-items: center; justify-content: center;">'
                '<video width="60" height="45" style="object-fit: cover; border-radius: 4px;">'
                '<source src="{}" type="video/mp4">'
                '</video>'
                '</div>',
                obj.video.url
            )
        return format_html(
            '<div style="width: 60px; height: 45px; background: #f0f0f0; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #999; font-size: 12px;">No Video</div>'
        )
    video_preview_thumbnail.short_description = "Video"
    
    def thumbnail_video_preview_thumbnail(self, obj):
        """Display thumbnail video preview in list view"""
        if obj.thumbnailVideoUrl:
            return format_html(
                '<div style="width: 60px; height: 45px; border-radius: 4px; overflow: hidden; background: #f0f0f0; display: flex; align-items: center; justify-content: center;">'
                '<video width="60" height="45" style="object-fit: cover; border-radius: 4px;">'
                '<source src="{}" type="video/mp4">'
                '</video>'
                '</div>',
                obj.thumbnailVideoUrl.url
            )
        return format_html(
            '<div style="width: 60px; height: 45px; background: #f0f0f0; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #999; font-size: 12px;">No Thumbnail</div>'
        )
    thumbnail_video_preview_thumbnail.short_description = "Thumbnail"
    
    def video_name_display(self, obj):
        if obj.video:
            return obj.video.name.split('/')[-1]
        return "No video"
    video_name_display.short_description = "Video File"
    
    def thumbnail_video_name_display(self, obj):
        if obj.thumbnailVideoUrl:
            return obj.thumbnailVideoUrl.name.split('/')[-1]
        return "No thumbnail"
    thumbnail_video_name_display.short_description = "Thumbnail File"
    
    def category_display(self, obj):
        return format_html(
            '<span style="background: #e8f4f8; padding: 3px 8px; border-radius: 3px;">{}</span>',
            obj.category.name
        )
    category_display.short_description = "Category"
    category_display.admin_order_field = 'category__name'
    
    def template_id_display(self, obj):
        if obj.template_id:
            return obj.template_id
        return "-"
    template_id_display.short_description = "Template ID"
    template_id_display.admin_order_field = 'template_id'
    
    def cost_display(self, obj):
        cost_value = obj.cost if obj.cost else "0"
        return format_html(
            '<span style="background: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            cost_value
        )
    cost_display.short_description = "Cost"
    cost_display.admin_order_field = 'cost'
    
    def is_premium_display(self, obj):
        if obj.Prem:
            return format_html(
                '<span style="background: #ffc107; color: black; padding: 3px 8px; border-radius: 3px;">Premium</span>'
            )
        return format_html(
            '<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">Free</span>'
        )
    is_premium_display.short_description = "Premium"
    is_premium_display.admin_order_field = 'Prem'
    
    def video_preview(self, obj):
        if obj.video:
            return format_html(
                '<video width="400" height="300" controls style="border-radius: 4px; border: 2px solid #ddd;">'
                '<source src="{}" type="video/mp4">'
                'Your browser does not support the video tag.'
                '</video>',
                obj.video.url
            )
        return "No video uploaded"
    video_preview.short_description = "Video Preview"
    
    def thumbnail_video_preview(self, obj):
        if obj.thumbnailVideoUrl:
            return format_html(
                '<video width="400" height="300" controls style="border-radius: 4px; border: 2px solid #ddd;">'
                '<source src="{}" type="video/mp4">'
                'Your browser does not support the video tag.'
                '</video>',
                obj.thumbnailVideoUrl.url
            )
        return "No thumbnail video uploaded"
    thumbnail_video_preview.short_description = "Thumbnail Video Preview"
    
    def action_buttons(self, obj):
        return format_html(
            '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            '<a class="button" style="font-size:11px; padding:5px 10px; white-space: nowrap;" href="{}">↕ Move Effect</a>'
            '<a class="button" style="font-size:11px; padding:5px 10px; white-space: nowrap;" href="{}">⇄ Swap Effect</a>'
            '</div>',
            reverse('admin:pixverse_move_effect', args=[obj.pk]),
            reverse('admin:pixverse_swap_effect', args=[obj.pk])
        )
    action_buttons.short_description = "Actions"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:effect_id>/move-effect/', self.admin_site.admin_view(self.move_effect_view), name='pixverse_move_effect'),
            path('<int:effect_id>/swap-effect/', self.admin_site.admin_view(self.swap_effect_view), name='pixverse_swap_effect'),
        ]
        return custom_urls + urls
    
    def move_effect_view(self, request, effect_id):
        """View to move an effect to a new position within its category"""
        effect = get_object_or_404(Effect, pk=effect_id)
        category = effect.category
        all_effects = Effect.objects.filter(category=category).order_by('position')
        
        if request.method == 'POST':
            new_position = int(request.POST.get('new_position'))
            
            try:
                with transaction.atomic():
                    old_position = effect.position
                    success = Effect.move_to_position(effect_id, new_position)
                    
                    if success:
                        clear_all_pixverse_cache()
                        messages.success(
                            request,
                            f"✓ Effect moved from position {old_position} to {new_position} in {category.name}."
                        )
                    else:
                        messages.error(request, "Failed to move effect.")
            except Exception as e:
                messages.error(request, f"Error moving effect: {str(e)}")
            
            return redirect('admin:pixverse_effect_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'effect': effect,
            'category': category,
            'all_effects': all_effects,
            'max_position': all_effects.count() - 1,
            'opts': self.model._meta,
            'title': f'Move Effect in {category.name}',
        }
        
        return render(request, 'admin/pixverse/effect/move_effect.html', context)
    
    def swap_effect_view(self, request, effect_id):
        """View to swap an effect with another in same category"""
        effect = get_object_or_404(Effect, pk=effect_id)
        category = effect.category
        other_effects = Effect.objects.filter(category=category).exclude(pk=effect_id).order_by('position')
        
        if request.method == 'POST':
            swap_with_id = int(request.POST.get('swap_with'))
            
            try:
                swap_with_effect = get_object_or_404(Effect, pk=swap_with_id)
                
                with transaction.atomic():
                    success = Effect.swap_positions(effect_id, swap_with_id)
                    
                    if success:
                        clear_all_pixverse_cache()
                        messages.success(
                            request,
                            f"✓ Successfully swapped '{effect.display_name}' with '{swap_with_effect.display_name}' in {category.name}."
                        )
                    else:
                        messages.error(request, "Failed to swap effects.")
            except Exception as e:
                messages.error(request, f"Error swapping effects: {str(e)}")
            
            return redirect('admin:pixverse_effect_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'effect': effect,
            'category': category,
            'other_effects': other_effects,
            'opts': self.model._meta,
            'title': f'Swap Effect in {category.name}',
        }
        
        return render(request, 'admin/pixverse/effect/swap_effect.html', context)