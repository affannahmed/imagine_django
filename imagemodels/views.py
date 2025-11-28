# imagemodels/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import models
from .models import ImageModel, ImageModelMeta
from .serializers import (
    ImageModelSerializer, 
    ImageModelCreateSerializer, 
    ImageModelListSerializer,
    ImageModelTemplateSerializer
)

class ImageModelViewSet(viewsets.ModelViewSet):
    queryset = ImageModel.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """
        Allow public access to meta and by_template endpoints
        """
        if self.action in ['meta', 'by_template']:
            return [AllowAny()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ImageModelCreateSerializer
        elif self.action == 'list':
            return ImageModelListSerializer
        elif self.action == 'by_template':
            return ImageModelTemplateSerializer
        return ImageModelSerializer

    def list(self, request):
        """List all available image models"""
        models = self.get_queryset().order_by('created_at')
        serializer = self.get_serializer(models, many=True)
        
        return Response({
            'success': True,
            'count': models.count(),
            'image_models': serializer.data
        })

    def retrieve(self, request, pk=None):
        """Get single image model details"""
        image_model = get_object_or_404(ImageModel, pk=pk)
        serializer = self.get_serializer(image_model)
        
        return Response({
            'success': True,
            'image_model': serializer.data
        })

    def create(self, request):
        """Create new image model"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            image_model = serializer.save()
            
            # Increment version when creating new model
            meta_obj, _ = ImageModelMeta.objects.get_or_create(id=1)
            meta_obj.current_version += 1
            meta_obj.save()
            
            response_serializer = ImageModelSerializer(image_model)
            return Response({
                'success': True,
                'message': 'Image model created successfully',
                'image_model': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """Update existing image model"""
        image_model = get_object_or_404(ImageModel, pk=pk)
        serializer = self.get_serializer(image_model, data=request.data, partial=True)
        
        if serializer.is_valid():
            image_model = serializer.save()
            
            # Increment version when updating
            meta_obj, _ = ImageModelMeta.objects.get_or_create(id=1)
            meta_obj.current_version += 1
            meta_obj.save()
            
            response_serializer = ImageModelSerializer(image_model)
            
            return Response({
                'success': True,
                'message': 'Image model updated successfully',
                'image_model': response_serializer.data
            })
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """Delete image model"""
        image_model = get_object_or_404(ImageModel, pk=pk)
        model_name = image_model.display_name
        
        image_model.delete()
        
        # Increment version on delete
        meta_obj, _ = ImageModelMeta.objects.get_or_create(id=1)
        meta_obj.current_version += 1
        meta_obj.save()
        
        return Response({
            'success': True,
            'message': f'Image model "{model_name}" deleted successfully'
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search image models by name or display name"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({
                'success': False,
                'error': 'Please provide a search query using ?q=searchterm'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        models = ImageModel.objects.filter(
            models.Q(processing_name__icontains=query) | 
            models.Q(display_name__icontains=query)
        ).order_by('created_at')
        
        serializer = ImageModelListSerializer(models, many=True)
        
        return Response({
            'success': True,
            'query': query,
            'count': models.count(),
            'image_models': serializer.data
        })

    @action(detail=False, methods=['get'])
    def meta(self, request):
        """Return total count and current version of image models"""
        count = ImageModel.objects.count()
        meta_obj, _ = ImageModelMeta.objects.get_or_create(id=1)
        
        return Response({
            "count": str(count),
            "current_version": str(meta_obj.current_version)
        })

    @action(detail=False, methods=['get'])
    def by_template(self, request):
        """Return image model by templateNumber index (0-based)"""
        template_number = request.query_params.get("templateNumber", None)

        if template_number is None:
            return Response({
                "error": "Please provide ?templateNumber="
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            template_number = int(template_number)
        except ValueError:
            return Response({
                "error": "templateNumber must be an integer"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get models sorted by created_at (oldest first for 0-based indexing)
        models = ImageModel.objects.all().order_by("created_at")

        if template_number < 0 or template_number >= models.count():
            return Response({
                "error": "Invalid templateNumber"
            }, status=status.HTTP_400_BAD_REQUEST)

        image_model = models[template_number]
        serializer = self.get_serializer(image_model)

        return Response(serializer.data)