from django.urls import path
from . import views # . referes to the current module we are in

# used for sharing
from .views import SharedPostView

urlpatterns = [
    path("", views.stream, name="stream"),
    path("profile/<int:id>/", views.profile, name="profile"), 
    path("accounts/login/", views.login_user, name='login'),
    path("accounts/logout/", views.logout_user, name='logout'),
    path("signup", views.signup_user, name='signup'),
    path("profile/<int:id>/edit", views.edit_profile, name="edit_profile"),
    path("followers/<int:author_id>/", views.followers, name="followers"),
    path("following/<int:author_id>/", views.following, name="following"),
    path('share_post/<str:pk>', SharedPostView.as_view(), name = 'share-post'),
    path('users', views.users, name = "users"),
    path('ajax_follow', views.ajax_follow,name = "ajax_follow"),
    path('ajax_notification', views.ajax_notification,name = "ajax_notification")
]
