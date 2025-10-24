from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Q, Count
import os
from pathlib import Path
from .models import ImagineAssetBatch, ImagineAsset
from .serializers import (
    ImagineAssetSerializer,
    ImagineAssetBatchSerializer,
    ImagineAssetBatchListSerializer,
    ImagineAssetLegacySerializer
)


class ImagineAssetBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ImagineAssetBatch
    
    list: Get all asset batches
    retrieve: Get a specific batch with all its images
    """
    queryset = ImagineAssetBatch.objects.all().prefetch_related('images')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['main_category', 'sub_category']
    ordering_fields = ['position', 'created_at', 'updated_at', 'main_category']
    ordering = ['position']  # Changed to position for consistent ordering
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ImagineAssetBatchListSerializer
        return ImagineAssetBatchSerializer
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get all main categories with their positions
        GET /api/batches/categories/
        """
        categories = ImagineAssetBatch.objects.values('main_category').annotate(
            count=Count('id'),
            min_position=models.Min('position')
        ).order_by('min_position', 'main_category')
        
        return Response(categories)
    
    @action(detail=False, methods=['get'])
    def subcategories(self, request):
        """
        Get subcategories for a main category with positions
        GET /api/batches/subcategories/?main_category=art
        """
        main_category = request.query_params.get('main_category')
        
        if not main_category:
            return Response(
                {'error': 'main_category parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        subcategories = ImagineAssetBatch.objects.filter(
            main_category=main_category
        ).values('sub_category', 'position').annotate(
            count=Count('id')
        ).order_by('position')
        
        return Response(subcategories)
    
    def _get_base_imagine_path(self):
        """Helper method to get the base path for Imagine assets"""
        return os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New')
    
    def _count_images_in_directory(self, directory_path):
        """Count image files in a directory"""
        if not os.path.exists(directory_path):
            return 0
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        count = 0
        
        try:
            for item in os.listdir(directory_path):
                file_path = os.path.join(directory_path, item)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(item.lower())
                    if ext in image_extensions:
                        count += 1
        except Exception as e:
            print(f"Error counting images in {directory_path}: {e}")
            
        return count
    
    @action(detail=False, methods=['get'], url_path='total-imagine')
    def get_inspirations_total_imagine(self, request):
        """
        Get category counts using DATABASE (not file system)
        GET /getInspirationsTotalImagine/
        
        Returns:
        {
            "art": {
                "3d": 36,
                "total": 132,
                "landscape": 22,
                ...
            },
            ...
        }
        """
        # Use database as source of truth
        batches = ImagineAssetBatch.objects.prefetch_related('images').order_by('position')
        
        result = {}
        
        for batch in batches:
            main_cat = batch.main_category
            sub_cat = batch.sub_category
            image_count = batch.images.count()
            
            # Initialize main category if not exists
            if main_cat not in result:
                result[main_cat] = {'total': 0}
            
            # Add subcategory count if exists
            if sub_cat:
                result[main_cat][sub_cat] = image_count
                result[main_cat]['total'] += image_count
            else:
                # No subcategory - just add to total
                result[main_cat]['total'] = image_count
        
        return Response(result)


class ImagineAssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ImagineAsset
    
    list: Get all assets with filtering options
    retrieve: Get a specific asset
    
    Filtering:
    - main_category: Filter by main category
    - sub_category: Filter by sub category
    - is_premium: Filter by premium status (true/false)
    - tags: Filter by tags (comma-separated)
    - search: Search in tags
    """
    queryset = ImagineAsset.objects.all().select_related('batch')
    serializer_class = ImagineAssetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['tags', 'batch__main_category', 'batch__sub_category']
    ordering_fields = ['created_at', 'updated_at', 'image_number', 'batch__position']
    ordering = ['batch__position', 'batch', 'image_number']  # Consistent ordering
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by main_category
        main_category = self.request.query_params.get('main_category')
        if main_category:
            queryset = queryset.filter(batch__main_category=main_category)
        
        # Filter by sub_category
        sub_category = self.request.query_params.get('sub_category')
        if sub_category:
            queryset = queryset.filter(batch__sub_category=sub_category)
        
        # Filter by premium status
        is_premium = self.request.query_params.get('is_premium')
        if is_premium is not None:
            is_premium_bool = is_premium.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_premium=is_premium_bool)
        
        # Filter by tags
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                queryset = queryset.filter(tags__contains=[tag])
        
        return queryset
    
    def _get_base_imagine_path(self):
        """Helper method to get the base path for Imagine assets"""
        return os.path.join(settings.MEDIA_ROOT, 'assets', 'Imagine-New')
    
    @action(detail=False, methods=['get'], url_path='url-imagine')
    def get_inspirations_url_imagine(self, request):
        """
        Get image URL based on template number, category, and subcategory
        NOW USES DATABASE AS SOURCE OF TRUTH
        
        GET /getInspirationsUrlImagine?templateNumber=0&category=art&subcategory=3d
        
        Returns:
        {
            "Name": "0",
            "ImageUrl": "/media/assets/Imagine-New/art/3d/0.jpg",
            "Prem": true,
            "actualTemplateNumber": "0",
            "currentIndex": 0,
            "maincategory": "art",
            "totalImages": 36,
            "subcategory": "3d",
            "objects": ["woman"]
        }
        """
        template_number = request.query_params.get('templateNumber')
        main_category = request.query_params.get('category')
        sub_category = request.query_params.get('subcategory', '').strip()
        
        if not template_number or not main_category:
            return Response(
                {'error': 'templateNumber and category are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            template_number_int = int(template_number)
        except ValueError:
            return Response(
                {'error': 'templateNumber must be a valid integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle "all" subcategory case
        if sub_category and sub_category.lower() == 'all':
            # Get all images across all subcategories in order by batch position then image number
            all_assets = ImagineAsset.objects.filter(
                batch__main_category=main_category
            ).select_related('batch').order_by('batch__position', 'image_number')
            
            if not all_assets.exists():
                return Response(
                    {'error': f'No images found for category {main_category}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            total_images = all_assets.count()
            
            if template_number_int >= total_images or template_number_int < 0:
                return Response(
                    {'error': f'Index {template_number_int} out of range. Total images: {total_images}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get the specific asset at this index
            selected_asset = list(all_assets)[template_number_int]
            
            # Build image URL
            image_url = request.build_absolute_uri(selected_asset.image.url) if selected_asset.image else None
            
            return Response({
                'Name': str(selected_asset.image_number),
                'ImageUrl': image_url,
                'Prem': selected_asset.is_premium,
                'actualTemplateNumber': str(selected_asset.image_number),
                'currentIndex': template_number_int,
                'maincategory': main_category,
                'totalImages': total_images,
                'subcategory': selected_asset.batch.sub_category or '',
                'objects': selected_asset.tags if isinstance(selected_asset.tags, list) else []
            })
        
        # Handle specific subcategory or no subcategory
        try:
            if sub_category:
                # Get specific batch with subcategory
                batch = ImagineAssetBatch.objects.get(
                    main_category=main_category,
                    sub_category=sub_category
                )
            else:
                # Get batch with no subcategory
                batch = ImagineAssetBatch.objects.get(
                    main_category=main_category,
                    sub_category__isnull=True
                )
        except ImagineAssetBatch.DoesNotExist:
            return Response(
                {'error': f"Category '{main_category}' with subcategory '{sub_category}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get the specific image by image_number
        try:
            asset = ImagineAsset.objects.get(
                batch=batch,
                image_number=template_number_int
            )
        except ImagineAsset.DoesNotExist:
            return Response(
                {'error': f'Image {template_number_int} not found in {main_category}/{sub_category or ""}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Count total images in this batch
        total_images = ImagineAsset.objects.filter(batch=batch).count()
        
        # Build image URL
        image_url = request.build_absolute_uri(asset.image.url) if asset.image else None
        
        return Response({
            'Name': str(asset.image_number),
            'ImageUrl': image_url,
            'Prem': asset.is_premium,
            'actualTemplateNumber': str(asset.image_number),
            'currentIndex': template_number_int,
            'maincategory': main_category,
            'totalImages': total_images,
            'subcategory': sub_category or '',
            'objects': asset.tags if isinstance(asset.tags, list) else []
        })
    
    @action(detail=False, methods=['get'])
    def legacy_format(self, request):
        """
        Get assets in the original JSON format
        GET /api/assets/legacy_format/?main_category=art&sub_category=3d
        
        Returns format like:
        {
            "Image0": {"Name": "0", "Prem": true, ...},
            "Image1": {"Name": "1", "Prem": false, ...}
        }
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Build the legacy format
        result = {}
        for asset in queryset:
            key = f"Image{asset.image_number}"
            result[key] = {
                "Name": str(asset.image_number),
                "Prem": asset.is_premium,
                "main_category": asset.batch.main_category,
                "sub_category": asset.batch.sub_category or "",
                "objects": asset.tags if isinstance(asset.tags, list) else []
            }
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get all assets grouped by category
        GET /api/assets/by_category/
        
        Returns:
        {
            "art/3d": [...],
            "nature/landscapes": [...]
        }
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Group by category
        grouped = {}
        for asset in queryset:
            category_path = asset.batch.get_category_path()
            if category_path not in grouped:
                grouped[category_path] = []
            
            serializer = self.get_serializer(asset)
            grouped[category_path].append(serializer.data)
        
        return Response(grouped)
    
    @action(detail=False, methods=['get'])
    def random(self, request):
        """
        Get random assets
        GET /api/assets/random/?count=10&is_premium=false
        """
        count = int(request.query_params.get('count', 10))
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get random assets
        random_assets = queryset.order_by('?')[:count]
        serializer = self.get_serializer(random_assets, many=True)
        
        return Response(serializer.data)