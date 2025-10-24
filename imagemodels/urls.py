# imagemodels/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImageModelViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'models', ImageModelViewSet, basename='imagemodel')

app_name = 'imagemodels'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),

    # Custom Endpoints:
    # For Getting the count and version:
    # /imagemodels/api/models/meta/
    
    # For Getting models by templateNumber:
    # /imagemodels/api/models/by_template/?templateNumber=0
]