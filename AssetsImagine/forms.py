from django import forms
from django.forms import modelformset_factory
from .models import ImagineAsset, ImagineAssetBatch


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={'multiple': True, 'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BulkImageUploadForm(forms.Form):
    main_category = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'vTextField',
            'placeholder': 'e.g., Art, Nature, Technology'
        }),
        help_text="Main category name (keep original capitalization)"
    )
    
    sub_category = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'vTextField',
            'placeholder': 'e.g., 3D, Portraits (optional)'
        }),
        help_text="Sub-category name (optional, keep original capitalization)"
    )
    
    images = MultipleFileField(
        help_text="Select multiple images (JPG, PNG, WebP) - Hold Ctrl/Cmd to select multiple",
        required=True
    )
    
    def clean(self):
        cleaned_data = super().clean()
        images = cleaned_data.get('images', [])
        
        if not images:
            raise forms.ValidationError("Please select at least one image.")
        
        return cleaned_data
    
    def clean_main_category(self):
        """Clean main category - keep original case but normalize spacing"""
        category = self.cleaned_data.get('main_category', '').strip()
        if category:
            # Only normalize multiple spaces to single space
            category = ' '.join(category.split())
            # Replace spaces with underscores for filesystem
            category = category.replace(' ', '_')
        return category if category else None
    
    def clean_sub_category(self):
        """Clean sub category - keep original case but normalize spacing"""
        category = self.cleaned_data.get('sub_category', '').strip()
        if category:
            # Only normalize multiple spaces to single space
            category = ' '.join(category.split())
            # Replace spaces with underscores for filesystem
            category = category.replace(' ', '_')
        return category if category else None


class ImageAssetForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'vTextField',
            'placeholder': 'woman, tree, sculpture (comma-separated)'
        }),
        help_text="Enter tags separated by commas"
    )
    
    class Meta:
        model = ImagineAsset
        fields = ['is_premium', 'tags_input']
        widgets = {
            'is_premium': forms.Select(
                choices=[(False, 'Free'), (True, 'Premium')], 
                attrs={'class': 'vSelectField'}
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.tags:
            # Convert list to comma-separated string
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)
    
    def clean_tags_input(self):
        """Convert comma-separated string to list"""
        tags_str = self.cleaned_data.get('tags_input', '')
        if tags_str:
            # Split by comma, strip whitespace, filter empty strings, keep original case
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            return tags
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tags = self.cleaned_data.get('tags_input', [])
        if commit:
            instance.save()
        return instance


# Create formset for bulk editing
ImageAssetFormSet = modelformset_factory(
    ImagineAsset,
    form=ImageAssetForm,
    extra=0,
    can_delete=False
)