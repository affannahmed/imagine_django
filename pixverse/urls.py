from django.urls import path
from .views import (
    get_version_pixverse,
    get_total_categories_pixverse,
    get_effects_pixverse,
    get_trending_temp_effects_pixverse
)

app_name = 'pixverse'

urlpatterns = [
    # New 4 API Endpoints
    path('GetVersionPixverse', get_version_pixverse, name='get_version_pixverse'),
    path('GetTotalCategoriesPixverse', get_total_categories_pixverse, name='get_total_categories_pixverse'),
    path('GetEffectsPixverse', get_effects_pixverse, name='get_effects_pixverse'),
    path('GetTrendingTempEffectsPixverse', get_trending_temp_effects_pixverse, name='get_trending_temp_effects_pixverse'),
]

# Available API Endpoints:
# ========================
# GET /GetVersionPixverse                    - Get current version and total categories (excluding Trending Templates)
# GET /GetTotalCategoriesPixverse            - Get all categories with effect counts (excluding Trending Templates)
# GET /GetEffectsPixverse?templateNumber=0   - Get all effects in category by index
# GET /GetTrendingTempEffectsPixverse        - Get all effects in Trending Templates category