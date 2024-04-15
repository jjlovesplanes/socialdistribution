from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .views import AddCommentView

from . import views # . referes to the current module we are in

urlpatterns = [
    path('index/', views.index, name="index"),
    path('', views.post_list, name='post_list'),
    path('create/', views.create_post, name='create_post'),
    path('<str:pk>/', views.view_post, name='view_post'),
    path('<str:pk>/edit/', views.post_edit, name='post_edit'),
    path('like-post/', views.like_post, name='like-post'),
    path('like-post', views.like_post),  
    
    # POST comment URL: ://service/authors/{AUTHOR_ID}/posts/{POST_ID}/comments
    path('<str:pk>/comment/', login_required(AddCommentView.as_view()), name='add_comment'),
    
    #post_delete
    path('posts/<str:pk>/delete/', views.post_delete, name='post_delete'),
    path('like_comment/<str:comment_id>/', views.like_comment, name='like_comment'),

    

]
