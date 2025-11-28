from rest_framework import serializers
from .models import ImagineAssetBatch, ImagineAsset


class ImagineAssetSerializer(serializers.ModelSerializer):
    """Serializer for individual assets"""
    image_url = serializers.SerializerMethodField()
    main_category = serializers.CharField(source='batch.main_category', read_only=True)
    sub_category = serializers.CharField(source='batch.sub_category', read_only=True, allow_null=True)
    objects = serializers.ListField(source='tags', child=serializers.CharField())
    name = serializers.CharField(source='image_number', read_only=True)
    prem = serializers.BooleanField(source='is_premium')
    
    class Meta:
        model = ImagineAsset
        fields = [
            'id',
            'name',
            'prem',
            'main_category',
            'sub_category',
            'objects',
            'image_url',
            'image_number',
            'created_at',
            'updated_at'
        ]
    
    def get_image_url(self, obj):
        """Get the full URL for the image"""
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        elif obj.image:
            return obj.image.url
        return None


class ImagineAssetLegacySerializer(serializers.ModelSerializer):
    """Serializer that matches the original JSON format exactly"""
    Name = serializers.CharField(source='image_number')
    Prem = serializers.BooleanField(source='is_premium')
    main_category = serializers.CharField(source='batch.main_category', read_only=True)
    sub_category = serializers.CharField(source='batch.sub_category', read_only=True, allow_blank=True)
    objects = serializers.ListField(source='tags', child=serializers.CharField())
    
    class Meta:
        model = ImagineAsset
        fields = ['Name', 'Prem', 'main_category', 'sub_category', 'objects']
    
    def to_representation(self, instance):
        """Format as Image{number}: {...}"""
        data = super().to_representation(instance)
        return {
            f"Image{instance.image_number}": data
        }


class ImagineAssetBatchSerializer(serializers.ModelSerializer):
    """Serializer for asset batches"""
    images = ImagineAssetSerializer(many=True, read_only=True)
    image_count = serializers.SerializerMethodField()
    category_path = serializers.CharField(source='get_category_path', read_only=True)
    
    class Meta:
        model = ImagineAssetBatch
        fields = [
            'id',
            'main_category',
            'sub_category',
            'category_path',
            'image_count',
            'images',
            'created_at',
            'updated_at'
        ]
    
    def get_image_count(self, obj):
        return obj.images.count()


class ImagineAssetBatchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing batches"""
    image_count = serializers.SerializerMethodField()
    category_path = serializers.CharField(source='get_category_path', read_only=True)
    
    class Meta:
        model = ImagineAssetBatch
        fields = [
            'id',
            'main_category',
            'sub_category',
            'category_path',
            'image_count',
            'created_at',
            'updated_at'
        ]
    
    def get_image_count(self, obj):
        return obj.images.count()