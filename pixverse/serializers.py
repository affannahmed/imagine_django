from rest_framework import serializers
from .models import Effect, EffectCategory


class EffectSerializer(serializers.ModelSerializer):
    """Serializer for individual effects with thumbnail video support"""
    video_url = serializers.SerializerMethodField()
    thumbnailVideoUrl = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Effect
        fields = [
            'id',
            'name',
            'display_name',
            'description',
            'Prem',
            'video_url',
            'thumbnailVideoUrl',
            'template_id',
            'category_name',
            'position',
            'created_at',
            'updated_at'
        ]

    def get_video_url(self, obj):
        """Get the full URL for the video"""
        if obj.video:
            request = self.context.get('request')
            base_url = obj.video.url
            
            if request:
                return request.build_absolute_uri(base_url)
            return base_url
        return None

    def get_thumbnailVideoUrl(self, obj):
        """Get the full URL for the thumbnail video"""
        if obj.thumbnailVideoUrl:
            request = self.context.get('request')
            base_url = obj.thumbnailVideoUrl.url
            
            if request:
                return request.build_absolute_uri(base_url)
            return base_url
        return None


class EffectCategorySerializer(serializers.ModelSerializer):
    """Serializer for effect categories"""
    effect_count = serializers.SerializerMethodField()

    class Meta:
        model = EffectCategory
        fields = [
            'id',
            'name',
            'position',
            'effect_count',
            'created_at',
            'updated_at'
        ]

    def get_effect_count(self, obj):
        """Get number of effects in this category"""
        return obj.effects.count()


class EffectWithCategorySerializer(serializers.ModelSerializer):
    """Serializer for effect with category details and thumbnail video support"""
    video_url = serializers.SerializerMethodField()
    thumbnailVideoUrl = serializers.SerializerMethodField()
    category = EffectCategorySerializer(read_only=True)

    class Meta:
        model = Effect
        fields = [
            'id',
            'name',
            'display_name',
            'description',
            'Prem',
            'video_url',
            'thumbnailVideoUrl',
            'template_id',
            'category',
            'position',
            'created_at',
            'updated_at'
        ]

    def get_video_url(self, obj):
        """Get the full URL for the video"""
        if obj.video:
            request = self.context.get('request')
            base_url = obj.video.url
            
            if request:
                return request.build_absolute_uri(base_url)
            return base_url
        return None

    def get_thumbnailVideoUrl(self, obj):
        """Get the full URL for the thumbnail video"""
        if obj.thumbnailVideoUrl:
            request = self.context.get('request')
            base_url = obj.thumbnailVideoUrl.url
            
            if request:
                return request.build_absolute_uri(base_url)
            return base_url
        return None