from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from .models import Effect, EffectCategory, EffectMeta
from .serializers import EffectSerializer


def clear_all_pixverse_cache():
    """Clear all pixverse-related cache keys"""
    cache.delete('pixverse_version_meta')
    cache.delete('pixverse_all_categories')
    cache.delete('pixverse_trending_effects')
    for i in range(10000):
        cache.delete(f'pixverse_effects_index_{i}')


@api_view(['GET'])
def get_version_pixverse(request):
    """
    Get current version and total categories (excluding 'Trending Templates')
    Endpoint: GET /pixverse/GetVersionPixverse
    
    Returns:
        {
            "current_version": "5",
            "total_categories": "3"
        }
    """
    cache_key = 'pixverse_version_meta'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    # Get version
    meta_obj, created = EffectMeta.objects.get_or_create(id=1)
    
    # Count categories excluding 'Trending Templates' (case-insensitive)
    total_categories = EffectCategory.objects.exclude(
        name__iexact='Trending Templates'
    ).count()
    
    data = {
        'current_version': str(meta_obj.current_version),
        'total_categories': str(total_categories)
    }
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return Response(data)


@api_view(['GET'])
def get_total_categories_pixverse(request):
    """
    Get all categories with their effect counts (excluding 'Trending Templates')
    Endpoint: GET /pixverse/GetTotalCategoriesPixverse
    
    Returns:
        {
            "0": {
                "category_name": "Transitions",
                "total_effects": "5"
            },
            "1": {
                "category_name": "Overlays",
                "total_effects": "3"
            }
        }
    """
    cache_key = 'pixverse_all_categories'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    # Get all categories excluding 'Trending Templates', ordered by position
    categories = EffectCategory.objects.exclude(
        name__iexact='Trending Templates'
    ).order_by('position')
    
    data = {}
    for index, category in enumerate(categories):
        data[str(index)] = {
            'category_name': category.name,
            'total_effects': str(category.effects.count())
        }
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return Response(data)


@api_view(['GET'])
def get_effects_pixverse(request):
    """
    Get all effects in a category by index (excluding 'Trending Templates')
    Endpoint: GET /pixverse/GetEffectsPixverse?templateNumber=0
    
    Args:
        templateNumber (int): Category index (0-based)
    
    Returns:
        {
            "category_name": "Transitions",
            "0": {
                "display_name": "Fire Transition",
                "description": "A smooth fire transition effect",
                "prem": false,
                "template_id": "xyz123",
                "cost": "99",
                "videoUrl": "http://your-server.com/media/pixverse_effects_imagine/transitions/fire_transition.mp4",
                "thumbnailVideoUrl": "http://your-server.com/media/pixverse_effects_imagine/transitions/fire_transition_thumbnail.mp4"
            },
            "1": {
                "display_name": "Water Transition",
                "description": "A water splash transition effect",
                "prem": true,
                "template_id": "abc456",
                "cost": "",
                "videoUrl": "http://your-server.com/media/pixverse_effects_imagine/transitions/water_transition.mp4",
                "thumbnailVideoUrl": ""
            }
        }
    """
    template_number = request.query_params.get('templateNumber')
    
    if template_number is None:
        return Response(
            {'error': 'templateNumber parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        template_number = int(template_number)
    except ValueError:
        return Response(
            {'error': 'templateNumber must be an integer'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    cache_key = f'pixverse_effects_index_{template_number}'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    # Get categories excluding 'Trending Templates', ordered by position
    categories = EffectCategory.objects.exclude(
        name__iexact='Trending Templates'
    ).order_by('position')
    
    # Check if index is valid
    if template_number < 0 or template_number >= categories.count():
        return Response(
            {'error': f'Invalid templateNumber. Must be between 0 and {categories.count() - 1}'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get the category at the specified index
    category = list(categories)[template_number]
    
    # Get all effects in this category, ordered by position
    effects = Effect.objects.filter(category=category).order_by('position')
    
    data = {
        'category_name': category.name
    }
    
    # Add each effect with its index as key
    for index, effect in enumerate(effects):
        video_url = None
        if effect.video:
            video_url = request.build_absolute_uri(effect.video.url)
        
        thumbnail_video_url = None
        if effect.thumbnailVideoUrl:
            thumbnail_video_url = request.build_absolute_uri(effect.thumbnailVideoUrl.url)
        
        data[str(index)] = {
            'display_name': effect.display_name,
            'description': effect.description if effect.description else "",
            'prem': effect.Prem,
            'template_id': effect.template_id if effect.template_id else "",
            'cost': effect.cost if effect.cost else "",
            'videoUrl': video_url if video_url else "",
            'thumbnailVideoUrl': thumbnail_video_url if thumbnail_video_url else ""
        }
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return Response(data)


@api_view(['GET'])
def get_trending_temp_effects_pixverse(request):
    """
    Get all effects in 'Trending Templates' category
    Endpoint: GET /pixverse/GetTrendingTempEffectsPixverse
    
    Returns:
        {
            "category_name": "Trending Templates",
            "0": {
                "display_name": "Popular Effect 1",
                "description": "A popular trending effect",
                "prem": false,
                "template_id": "trend123",
                "cost": "199",
                "videoUrl": "http://your-server.com/media/pixverse_effects_imagine/trending_templates/effect1.mp4",
                "thumbnailVideoUrl": "http://your-server.com/media/pixverse_effects_imagine/trending_templates/effect1_thumbnail.mp4"
            },
            "1": {
                "display_name": "Popular Effect 2",
                "description": "Another trending effect",
                "prem": true,
                "template_id": "trend456",
                "cost": "",
                "videoUrl": "http://your-server.com/media/pixverse_effects_imagine/trending_templates/effect2.mp4",
                "thumbnailVideoUrl": ""
            }
        }
    """
    cache_key = 'pixverse_trending_effects'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    # Find the 'Trending Templates' category (case-insensitive)
    try:
        category = EffectCategory.objects.get(name__iexact='Trending Templates')
    except EffectCategory.DoesNotExist:
        return Response(
            {'error': 'Trending Templates category not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all effects in this category, ordered by position
    effects = Effect.objects.filter(category=category).order_by('position')
    
    data = {
        'category_name': category.name
    }
    
    # Add each effect with its index as key
    for index, effect in enumerate(effects):
        video_url = None
        if effect.video:
            video_url = request.build_absolute_uri(effect.video.url)
        
        thumbnail_video_url = None
        if effect.thumbnailVideoUrl:
            thumbnail_video_url = request.build_absolute_uri(effect.thumbnailVideoUrl.url)
        
        data[str(index)] = {
            'display_name': effect.display_name,
            'description': effect.description if effect.description else "",
            'prem': effect.Prem,
            'template_id': effect.template_id if effect.template_id else "",
            'cost': effect.cost if effect.cost else "",
            'videoUrl': video_url if video_url else "",
            'thumbnailVideoUrl': thumbnail_video_url if thumbnail_video_url else ""
        }
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return Response(data)