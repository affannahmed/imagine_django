# imagemodels/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import ImageModel, ImageModelMeta

@admin.register(ImageModel)
class ImageModelAdmin(admin.ModelAdmin):
    list_display = [
        'template_index',
        'display_name',
        'processing_name',
        'features_display',
        'path_display',
        'cost',
        'Prem',
        'created_at'
    ]
    list_filter = ['Prem', 'created_at']
    search_fields = ['display_name', 'processing_name', 'features']
    readonly_fields = ['created_at', 'template_index_display']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('display_name', 'processing_name', 'Prem', 'cost')
        }),
        ('Features & Path', {
            'fields': ('features', 'path')
        }),
        ('Metadata', {
            'fields': ('created_at', 'template_index_display'),
            'classes': ('collapse',)
        })
    )

    def template_index(self, obj):
        """Show the 0-based index of this model"""
        models = ImageModel.objects.all().order_by('created_at')
        for idx, model in enumerate(models):
            if model.id == obj.id:
                return idx
        return '-'
    template_index.short_description = "Index"

    def template_index_display(self, obj):
        """Show the 0-based index in detail view"""
        models = ImageModel.objects.all().order_by('created_at')
        for idx, model in enumerate(models):
            if model.id == obj.id:
                return idx
        return '-'
    template_index_display.short_description = "Template Index"

    def features_display(self, obj):
        """Display features as comma-separated values"""
        if obj.features and isinstance(obj.features, list):
            return ", ".join(obj.features)
        return "-"
    features_display.short_description = "Features"

    def path_display(self, obj):
        """Display truncated path"""
        if len(obj.path) > 50:
            return obj.path[:50] + "..."
        return obj.path
    path_display.short_description = "Path"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'processing_name' in form.base_fields:
            form.base_fields['processing_name'].help_text = (
                "Use lowercase with hyphens (e.g., 'google-imagen-4'). "
                "This will be used for API processing."
            )
        if 'features' in form.base_fields:
            form.base_fields['features'].help_text = (
                'Enter as JSON array: ["feature1", "feature2", "feature3"]'
            )
        return form

    def save_model(self, request, obj, form, change):
        """Increment version when saving model"""
        super().save_model(request, obj, form, change)
        
        # Increment version when creating or updating
        meta_obj, _ = ImageModelMeta.objects.get_or_create(id=1)
        meta_obj.current_version += 1
        meta_obj.save()


@admin.register(ImageModelMeta)
class ImageModelMetaAdmin(admin.ModelAdmin):
    list_display = ['current_version']
    readonly_fields = ['current_version']

    def has_add_permission(self, request):
        # Only allow one meta object
        return not ImageModelMeta.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of meta object
        return False