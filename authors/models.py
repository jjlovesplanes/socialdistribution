from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

# Create your models here.
class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    uuid = models.CharField(default = uuid.uuid4, max_length = 50, unique=True, editable = False)
    type = models.CharField(default="author",max_length=6)
    host = models.URLField()                            # host will look like... "127.0.0.1:8000/"
    url = models.URLField(null=True, blank=True)        # url  will look like... "https://hypertext-heroes-db392aad0426.herokuapp.com/authors/17d014d0-bff3-4818-bf61-61e9d3e9077e""
    profile_image = models.URLField(null=True, blank=True)
    github = models.URLField(null=True, blank=True)
    
    def __str__(self):
        return self.user.username

class Follower(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='author')
    follower = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='follower')
    request_accepted = models.BooleanField(default=False) # follow request has been accepted
    is_friend = models.BooleanField(default=False) # users follow each other

    class Meta:
        unique_together = ["author_id", "follower_id"]

class Node(models.Model):
    username = models.CharField(max_length=150, unique=True)
    host = models.URLField()
    is_active = models.BooleanField(default=True) # follow request has been accepted
    password = models.CharField(max_length=128)
    api_prefixed = models.BooleanField(default=False)