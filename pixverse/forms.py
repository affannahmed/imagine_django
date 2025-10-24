from django import forms
from .models import EffectCategory, Effect


class EffectCategoryForm(forms.ModelForm):
    """Form for creating/editing effect categories"""
    class Meta:
        model = EffectCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'e.g., Transitions, Overlays, Effects',
                'help_text': 'Enter a unique category name'
            }),
        }


class EffectForm(forms.ModelForm):
    """Form for creating/editing effects with video and thumbnail video support"""
    class Meta:
        model = Effect
        fields = ['name', 'display_name', 'description', 'category', 'Prem', 'template_id', 'cost', 'video', 'thumbnailVideoUrl']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'e.g., fire_transition (unique, lowercase with underscores)',
            }),
            'display_name': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'e.g., Fire Transition (for display)',
            }),
            'description': forms.Textarea(attrs={
                'class': 'vLargeTextField',
                'placeholder': 'Optional: describe what this effect does',
                'rows': 4,
            }),
            'category': forms.Select(attrs={
                'class': 'vSelectField',
            }),
            'Prem': forms.CheckboxInput(attrs={
                'class': 'vCheckboxInput',
            }),
            'template_id': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'Pixverse template ID (optional)',
            }),
            'cost': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'e.g., 0, 99, 199 (optional - leave empty for free)',
                'help_text': 'Cost in rupees. Leave empty if the effect is free.',
            }),
            'video': forms.FileInput(attrs={
                'accept': 'video/mp4,video/mpeg',
                'help_text': 'Upload an MP4 video showing the effect (required)',
            }),
            'thumbnailVideoUrl': forms.FileInput(attrs={
                'accept': 'video/mp4,video/mpeg',
                'help_text': 'Upload an MP4 thumbnail video of the effect (optional - will be saved as {effect_name}_thumbnail.mp4)',
            }),
        }