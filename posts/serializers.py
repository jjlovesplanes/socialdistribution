from rest_framework import serializers
from .models import Post
from authors.models import Author
from authors.serializers import AuthorSerializer, CommentSerializer

class PostSerializer(serializers.ModelSerializer):

    def get_id(self, obj):
        return obj.id

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        base_url = request.build_absolute_uri('/')
        author_id = data['author']['id']
        author_name = data['author']['displayName']
        author_uuid = author_id.split('/')[-1]
        post_title = data['title']
        post_id = self.get_id(instance)
        data['id'] = f"{base_url}authors/{author_uuid}/posts/{post_id}"
        data['source'] = f'{base_url}authors/{author_uuid}/posts/{post_id}'
        data['origin'] = f"{base_url}authors/{author_uuid}/posts/{post_id}"
        data['description'] = f"{author_name} posted '{post_title}'" 
        data['comments'] = f"{base_url}authors/{author_uuid}/posts/{post_id}/comments"

        return data

    type = serializers.CharField(default='post', max_length=4)
    author = AuthorSerializer()
    contentType = serializers.CharField(source='content_type')
    content = serializers.CharField(source='content_markdown')
    published = serializers.DateTimeField(source='created_at')

    class Meta:
        model = Post
        fields = ["type", "title", "id", "source", "origin", "description", "contentType", "content", "author", "comments", "published", "visibility"]
    
    def update(self, instance, validated_data):
        """
        Update and return an existing 'Post' instance, given the validated data
        """    
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.contentType = validated_data.get('contentType', instance.content_type)
        instance.content_markdown = validated_data.get('content_markdown', instance.content)
        instance.visibility = validated_data.get('visibility', instance.visibility)
        instance.save()
        return instance
    
class PostsResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="posts", max_length=5)
    items = PostSerializer(many=True)

class ImagePostResponseSerializer(serializers.Serializer):
    content = serializers.Field()
    contentType = serializers.CharField()