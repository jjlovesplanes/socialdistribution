from django.db import models

# Create your models here.
# from django.conf import settings
from authors.models import Author
import uuid
from django import forms
import markdown
from django.utils import timezone

class Post(models.Model):
    visibility_choices = [
		("PUBLIC", "PUBLIC"),
        ("FRIENDS", "FRIENDS"),
        ("UNLISTED", "UNLISTED")
	]

    content_type_choices = [
        ("text/markdown", "text/markdown"),
        ("text/plain", "text/plain"),
        ("application/base64", "application/base64"),
        ("image/png;base64", "image/png;base64"),
        ("image/jpeg;base64", "image/jpeg;base64")
    ]

    shared_title = models.TextField(blank = True, null = True)
    shared_body = models.TextField(blank=True, null = True)
    # shared_on is shared date
    shared_on = models.DateTimeField(blank = True, null = True)
    shared_user = models.ForeignKey(Author, on_delete = models.CASCADE, blank = True, null = True, related_name = '+')
    copy_of_original_id = models.CharField(null = True, max_length=50)
    title = models.CharField(max_length=200)
    source = models.URLField()
    origin = models.URLField()
    description = models.TextField(max_length=250)
    content_type = models.CharField(max_length=50, choices=content_type_choices, default="text/markdown")
    content = models.TextField()
    content_markdown = models.TextField(default='', blank=True)  # new field to store the Markdown content
  # new field to store the Markdown content
    content_html = models.TextField(default='')
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    visibility = models.CharField(max_length=10, choices=visibility_choices, default="PUBLIC")
    image_url = models.URLField(null=True)  # Allow null values
    no_of_likes = models.IntegerField(default=0)
    id = models.CharField(default = uuid.uuid4, primary_key=True, max_length = 50, unique=True, editable = False)

    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-created_at', '-shared_on']

class LikePost(models.Model):
    # post_id = models.CharField(max_length = 500)
    # post = models.ForeignKey(Post, related_name = "Likeddddd", on_delete = models.CASCADE, default = Post(title = "flaksjd",
    #                                                                                                       source = "la;sk",
    #                                                                                                       origin = "d;lsfjs",
    #                                                                                                       description = "lsakdjf",
    #                                                                                                       content = "lsd",
    #                                                                                                       author = ))
    post = models.ForeignKey(Post, related_name = "Likeddddd", on_delete = models.CASCADE, default = 1)
    # name of the user that likes a post
    #username = models.CharField(max_length = 100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.author.user.username} liked {self.post_id}'
    
class Comment(models.Model):
    post = models.ForeignKey(Post, related_name = "comments", on_delete=models.CASCADE)
    # Who made the comment?
    id = models.CharField(default = uuid.uuid4, primary_key=True, max_length = 50, unique=True, editable = False)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    body = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)
    content_type = models.CharField(max_length=20, default="text/markdown")
    def get_markdown(self):
            return markdown.markdown(self.body)
    def __str__(self):
        return f"{self.post.title}  -  {self.author}"
    
class LikeComment(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    user = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'user')

    # def __str__(self):
    #     return f'{self.user.username} likes {self.comment}'
    
#######################  DO NOT DELETE  GET JAY PERMISSION #######################################################
class Notification(models.Model):

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='notifications', null = True)
    action_user = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='notifications_sent')
    receiver_user = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='notifications_received')
    action_type = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    notification_message = models.CharField(max_length=100, null= True)

    # def __str__(self):
    #     return f"{self.action_user.user.username} - {self.action_type}"