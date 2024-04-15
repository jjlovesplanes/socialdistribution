from django.contrib import admin
from .models import Author, Follower, Node

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('user', 'uuid','type', 'profile_image', 'github')
    list_filter = ('user','uuid', 'type')

@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ('username', 'host', 'is_active')


admin.site.register(Follower)