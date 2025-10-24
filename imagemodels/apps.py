# imagemodels/apps.py
from django.apps import AppConfig


class ImagemodelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'imagemodels'
    verbose_name = 'Image Models'