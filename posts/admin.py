from django.contrib import admin

# Register your models here.
from .models import Post, LikePost, Comment, Notification, LikeComment

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'id', 'author', 'created_at', 'visibility')
    list_filter = ('visibility', 'created_at')
    search_fields = ('title', 'content')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    
    list_display = ['id', 'action_user', 'receiver_user', 'action_type', 'timestamp']

admin.site.register(LikePost)
admin.site.register(LikeComment)
admin.site.register(Comment)