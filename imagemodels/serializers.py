# imagemodels/serializers.py
from rest_framework import serializers
from .models import ImageModel

class ImageModelSerializer(serializers.ModelSerializer):
    """Full serializer for image models"""
    
    class Meta:
        model = ImageModel
        fields = [
            'id',
            'display_name',
            'processing_name',
            'features',
            'path',
            'Prem',
            'cost',
            'created_at'
        ]
        read_only_fields = ['created_at']


class ImageModelCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new image models"""
    
    class Meta:
        model = ImageModel
        fields = [
            'display_name',
            'processing_name',
            'features',
            'path',
            'Prem',
            'cost'
        ]
    
    def validate_processing_name(self, value):
        """Ensure processing_name is lowercase and uses hyphens"""
        if not value.islower():
            raise serializers.ValidationError("Processing name should be lowercase")
        if ' ' in value:
            raise serializers.ValidationError("Use hyphens instead of spaces in processing name")
        return value

    def validate_features(self, value):
        """Ensure features is a list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Features must be a list")
        return value


class ImageModelListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing image models"""
    
    class Meta:
        model = ImageModel
        fields = [
            'id',
            'display_name',
            'processing_name',
            'Prem',
            'cost',
            'created_at'
        ]


class ImageModelTemplateSerializer(serializers.ModelSerializer):
    """Serializer for by_template endpoint response"""
    
    class Meta:
        model = ImageModel
        fields = [
            'display_name',
            'processing_name',
            'features',
            'path',
            'Prem',
            'cost'
        ]