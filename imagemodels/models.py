# imagemodels/models.py
from django.db import models
from django.utils import timezone

class ImageModel(models.Model):
    display_name = models.CharField(
        max_length=150,
        help_text="Display name to show in App (e.g., 'Google Imagen 4')"
    )
    processing_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Internal processing name (e.g., 'google-imagen-4')"
    )
    features = models.JSONField(
        default=list,
        help_text="List of features (e.g., ['sharper visuals', 'accurate text rendering'])"
    )
    path = models.CharField(
        max_length=500,
        help_text="File path for the model image"
    )
    Prem = models.BooleanField(
        default=False,
        help_text="Whether this model is premium"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Cost per generation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this model was created"
    )

    class Meta:
        verbose_name = "Image Model"
        verbose_name_plural = "Image Models"
        ordering = ["created_at"]  # Oldest first for proper indexing

    def __str__(self):
        return self.display_name

    @property
    def template_index(self):
        """Get the 0-based index of this model"""
        models = ImageModel.objects.all().order_by('created_at')
        for idx, model in enumerate(models):
            if model.id == self.id:
                return idx
        return -1


class ImageModelMeta(models.Model):
    current_version = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Image Model Meta"
        verbose_name_plural = "Image Model Meta"

    def __str__(self):
        return f"Version {self.current_version}"