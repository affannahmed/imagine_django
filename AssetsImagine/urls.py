from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImagineAssetBatchViewSet, ImagineAssetViewSet

# Create router for ViewSets (keeping the old API structure too)
router = DefaultRouter()
router.register(r'batches', ImagineAssetBatchViewSet, basename='imagineassetbatch')
router.register(r'assets', ImagineAssetViewSet, basename='imagineasset')

app_name = 'AssetsImagine'

urlpatterns = [
    # New Django REST API endpoints
    path('api/', include(router.urls)),
    
    # Legacy endpoint mappings (matching your old Flask API)
    path('getInspirationsTotalImagine/', 
         ImagineAssetBatchViewSet.as_view({'get': 'get_inspirations_total_imagine'}), 
         name='get-inspirations-total'),
    
    path('getInspirationsUrlImagine/', 
         ImagineAssetViewSet.as_view({'get': 'get_inspirations_url_imagine'}), 
         name='get-inspirations-url'),
]