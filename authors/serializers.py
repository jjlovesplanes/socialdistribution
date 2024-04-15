from rest_framework import serializers
from .models import Author, User
from posts.models import Comment

class AuthorSerializer(serializers.ModelSerializer):
    def get_uuid(self, obj):
        return obj.uuid
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['id'] = data['url']
        return data

    type = serializers.CharField(default='author', max_length=6)
    displayName = serializers.CharField(source='user')
    profileImage = serializers.CharField(source='profile_image')
    
    class Meta:
        model = Author
        fields = ["type", "id", "url", "host", "displayName", "github", "profileImage"]
    
    def update(self, instance, validated_data):
        instance.type = validated_data.get('type', instance.type)
        user = instance.user
        user.username = validated_data.get('user', user.username) 
        user.save()
        instance.github = validated_data.get('github', instance.github)
        instance.profile_image = validated_data.get('profile_image', instance.profile_image)
        instance.save()
        return instance

class AuthorResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="authors", max_length=7)
    items = AuthorSerializer(many=True)

class FollowersResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="followers", max_length=9)
    items = AuthorSerializer(many=True)

class ForeignFollowerResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="Follower", max_length=8)
    summary = serializers.CharField()
    actor = AuthorSerializer()
    object = AuthorSerializer()
    
class CommentSerializer(serializers.ModelSerializer):
    def get_id(self, obj):
        return obj.id
    
    def get_post_id(self, obj):
        return obj.post.id
    
    def get_author_url(self, obj):
        return obj.post.author.url
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        comment_id = self.get_id(instance)
        data['id'] = f"{self.get_author_url(instance)}/posts/{self.get_post_id(instance)}/comments/{comment_id}"
        return data
    
    type = serializers.CharField(default='comment', max_length=7)
    author = AuthorSerializer()
    comment = serializers.CharField(source='body')
    contentType = serializers.CharField(source='content_type')
    published = serializers.CharField(source='date_added')
    
    class Meta:
        model = Comment
        fields = ['type', 'author', 'comment', 'contentType', 'published', 'id']

class CommentsListSerializer(serializers.Serializer):
    type = serializers.CharField(default="comments", max_length=8)
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    post = serializers.CharField()
    comments = CommentSerializer(many=True)
    id = serializers.CharField()

class LikeSerializer(serializers.Serializer):
    summary = serializers.CharField()
    type = serializers.CharField(default="Like", max_length=4)
    author = AuthorSerializer()
    object = serializers.CharField()

class LikeResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="likes", max_length=5)
    items = LikeSerializer(many=True)

class LikedResponseSerializer(serializers.Serializer):
    type = serializers.CharField(default="liked", max_length=5)
    items = LikeSerializer(many=True)
