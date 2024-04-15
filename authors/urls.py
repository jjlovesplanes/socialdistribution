from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from posts import views as post_views

from . import views # . refers to the current module we are in

urlpatterns = [
    # Author API calls
    path('', views.authors_list, name="authors_list"),
    path('<str:uuid>', views.single_author, name="single_author"),

    # Followers API calls
    path('<str:uuid>/followers', views.followers_list, name="followers_list"),
    path('<str:uuid>/followers/<path:foreign_author_id_path>', views.foreign_follower, name="foreign_follower"),

    # Comments API calls
    path('<str:uuid>/posts/<str:post_id>/comments', views.comments_api, name="comments_api"),

    # Follower Request Endpoints (not API calls)
    path('<path:author_id>/follow_request/<path:follower_id>', views.follow_request, name="follow_request"),

    # Post API calls
    path('<str:author_id>/posts/<str:post_id>', views.single_post, name="single_post"),
    path('<str:author_id>/posts/<str:post_id>/image', views.image_post, name="image_post"),
    path('<str:author_id>/posts/', views.posts, name='posts'),
    
    # Likes API calls
    path('<str:uuid>/posts/<str:post_id>/likes', views.list_of_likes, name="Likes list"),
    path('<str:uuid>/posts/<str:post_id>/comments/<str:comment_id>/likes',views.comment_likes, name = "Comment Likes"),

    # Liked API calls
    path('<str:uuid>/liked', views.liked, name="Liked"),
    
    # Inbox API calls
    path('<path:uuid>/inbox', views.inbox, name = 'inbox')
    # http://127.0.0.1:8000/authors/0a0c2dd8-dfa6-464d-abf9-c34f7d9a17be/inbox
]
