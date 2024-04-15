from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.core import serializers
from .models import Author, Node, Follower
from posts.models import LikePost
from rest_framework import status
from django.contrib.auth.models import User
from base64 import b64encode, b64decode
from urllib.parse import quote
from posts.models import Post, Comment

# Create your tests here.
# Tests reference : https://docs.djangoproject.com/en/4.2/topics/testing/overview/
class APITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='TestUser')
        self.user_two = User.objects.create(username='TestUserTwo')
        self.node = Node.objects.create(username = 'TestNode', password = 'test123')
        self.local_host = "http://127.0.0.1:8000/"

        self.client = Client()

        # Author objects
        self.author_one = Author.objects.create(
            user = self.user,
            host = self.local_host,
            github = "https://github.com/almer18",
            profile_image = "https://as2.ftcdn.net/v2/jpg/05/79/10/95/1000_F_579109504_bOyS2098DZ8EN6l9YwI5WHTI33NZqem3.jpg"
        )
        self.author_one.url = f"{self.author_one.host}authors/{self.author_one.uuid}"
        self.author_one.save()

        self.author_two = Author.objects.create(
            user = self.user_two,
            host = self.local_host,
            github = "https://github.com/almer09",
            profile_image = "https://as2.ftcdn.net/v2/jpg/05/79/10/95/1000_F_579109504_bOyS2098DZ8EN6l9YwI5WHTI33NZqem3.jpg"
        )
        self.author_two.url = f"{self.author_two.host}authors/{self.author_two.uuid}"
        self.author_two.save()
        
        # Follower objects
        self.follower_one = Author.objects.create(
            user=User.objects.create(username='FollowerOne')
        )

        self.follower_two = Author.objects.create(
            user=User.objects.create(username='FollowerTwo')
        )
        Follower.objects.create(author=self.author_one, follower=self.follower_one, request_accepted=True)
        Follower.objects.create(author=self.author_one, follower=self.follower_two, request_accepted=True)

        # Post objects
        self.post_one = Post.objects.create(
            title='Test Post',
            content='Hello, world!',
            author=self.author_one,
            visibility='PUBLIC'
        )
        self.post_two = Post.objects.create(
            title='Test Post 2',
            content='Hello!',
            author=self.author_one,
            visibility='UNLISTED'
        )
        self.image_post = Post.objects.create(
            title='Test Image Post',
            image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Lamborghini_Urus_19.09.20_JM_%282%29_%28cropped%29.jpg/560px-Lamborghini_Urus_19.09.20_JM_%282%29_%28cropped%29.jpg",
            author=self.author_one,
            visibility='PUBLIC'
        )

        # Comment objects
        Comment.objects.create(
            post = self.post_one,
            author = self.author_one,
            body = "TEST comment",
            date_added = "2024-04-08T01:11:00Z",
            content_type = "text/markdown"
        )

    # Author API tests

    def test_authors_list(self):
        '''
        Test returns status code 200 and all authors when user is logged in (authorized)
        '''
        # Login
        self.client.force_login(self.user)
        
        url = reverse("authors_list")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_single_author(self):
        '''
        Test returns status code 200 and single author when user is logged in (authorized)
        '''
        # Login
        self.client.force_login(self.user)

        test_user = User.objects.get(username="TestUser")
        author_one = Author.objects.get(user = test_user)
        url = reverse("single_author", args=[author_one.uuid])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_put_single_author(self):
        # Login
        self.client.force_login(self.user)

        test_user = User.objects.get(username="TestUser")
        author_one = Author.objects.get(user = test_user)
        updated_author = {
            "type": "author",
            "id": author_one.url,
            "url": author_one.url,
            "host": author_one.host+self.local_host,
            "displayName": author_one.user.username + "James",
            "github": author_one.github,
            "profileImage": author_one.profile_image

        }

        url = reverse("single_author", args=[author_one.uuid])
        response = self.client.put(url, data=updated_author, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['displayName'], updated_author['displayName'])
    
    # Follower API tests

    def test_get_followers_list(self):
        # Login
        self.client.force_login(self.user)

        
        url = reverse("followers_list", args=[self.author_one.uuid])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_foreign_follower(self):
        foreign_author = self.follower_one

        # Login
        self.client.force_login(self.user)
        
        url = reverse("foreign_follower", args=[self.author_one.uuid, foreign_author.uuid])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_foreign_follower(self):
        foreign_author = self.author_two

        # Login
        self.client.force_login(self.user)

        
        url = reverse("foreign_follower", args=[self.author_one.uuid, foreign_author.uuid])
        response = self.client.put(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Follower.objects.filter(author=self.author_one, follower=foreign_author).exists())
    
    def test_remove_foreign_follower(self):
        foreign_author = self.author_two
        Follower.objects.create(author=self.author_one, follower=foreign_author, request_accepted=True)

        # Login
        self.client.force_login(self.user)
        
        url = reverse("foreign_follower", args=[self.author_one.uuid, foreign_author.uuid])
        response = self.client.delete(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Follower.objects.filter(author=self.author_one, follower=foreign_author).exists())

    # Post API tests

    def test_get_single_public_post(self):
        # Login
        self.client.force_login(self.user)
        
        url = reverse("single_post", args=[self.author_one.uuid, self.post_one.id])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_single_unlisted_post(self):
        # Login
        self.client.force_login(self.user)

        
        url = reverse("single_post", args=[self.author_one.uuid, self.post_two.id])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_single_post(self):
        # Login
        self.client.force_login(self.user)
        
        url = reverse("single_post", args=[self.author_one.uuid, self.post_two.id])
        response = self.client.delete(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
    def test_update_single_post(self):
         # Login
        self.client.force_login(self.user)

        updated_post = {
            'type': 'post',  
            'title': self.post_one.title + "Updated",
            'id': self.post_one.id,  
            'source': f'{self.local_host}authors/{self.post_one.author.uuid}/posts/{self.post_one.id}',  
            'origin': f'{self.local_host}authors/{self.post_one.author.uuid}/posts/{self.post_one.id}',  
            'description': f"{self.post_one.author.user.username} posted '{self.post_one.title}'",  
            'contentType': self.post_one.content_type,
            'content': "CONTENT",  
            'author': {
                    "type": "author",
                    "id": self.post_one.author.uuid,
                    "url": self.post_one.author.url,
                    "host": self.post_one.author.host,
                    "displayName": self.post_one.author.user.username,
                    "github": self.post_one.author.github,
                    "profileImage": self.post_one.author.profile_image
            },
            'comments': [],
            'published': self.post_one.created_at,
            'visibility': self.post_one.visibility
        }

        url = reverse("single_post", args=[self.author_one.uuid, self.post_one.id])
        response = self.client.put(url, data=updated_post, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], updated_post['title'])
    
    def test_get_all_public_posts(self):
        # Login
        self.client.force_login(self.user)

        
        url = reverse("posts", args=[self.author_one.uuid])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_new_post(self):
        # Login
        self.client.force_login(self.user)

        post_data = {
            "title": "Test Post",
            "description": "This is a test post",
            "contentType": "text/markdown",
            "content": "Test content",
            "visibility": "PUBLIC"
        }

        url = reverse("posts", args=[self.author_one.uuid])
        response = self.client.post(url, data=post_data, format='json')

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_get_image_post(self):
        # Login
        self.client.force_login(self.user)

        url = reverse("image_post", args=[self.author_one.uuid, self.image_post.id])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Comments API tests

    def test_get_comments(self):
        # Login
        self.client.force_login(self.user)

        url = reverse("comments_api", args=[self.author_one.uuid, self.post_one.id])
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_comment(self):
        # Login
        self.client.force_login(self.user)

        url = reverse("comments_api", args=[self.author_one.uuid, self.post_one.id])
        dataJson = {
            'type': 'comment',
            'author': {
                "type": "author",
                "id": self.post_one.author.uuid,  
                "url": self.post_one.author.url,
                "host": self.post_one.author.host,
                "displayName": self.post_one.author.user.username,
                "github": self.post_one.author.github,
                "profileImage": self.post_one.author.profile_image
            },
            'comment': 'This is a test comment.',
            'contentType': 'text/plain',
            'published': '2024-04-08T00:00:00Z',
            'id': f'{self.local_host}authors/{self.post_one.author.uuid}/posts/{self.post_one.id}/comments'
        }
        response = self.client.post(url, data = dataJson, content_type="application/json")
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_liked(self):
        self.client.force_login(self.user)

        like_obj = LikePost.objects.create(post = self.post_one, author = self.author_two)
        like_obj.save()
        url = reverse("Liked", args=[self.author_two.uuid])
        response = self.client.get(url)
        expected_output = {'type': 'liked', 'items': [{'summary': 'TestUserTwo Likes your post', 'type': 'Like', 'author': {'type': 'author', 'id': 'http://127.0.0.1:8000/authors/e42f3434-0836-4d8e-a91c-7e21d5ae5bc3', 'url': 'http://127.0.0.1:8000/authors/e42f3434-0836-4d8e-a91c-7e21d5ae5bc3', 'host': 'http://127.0.0.1:8000/', 'displayName': 'TestUserTwo', 'github': 'https://github.com/almer09', 'profileImage': 'https://as2.ftcdn.net/v2/jpg/05/79/10/95/1000_F_579109504_bOyS2098DZ8EN6l9YwI5WHTI33NZqem3.jpg'}, 'object': 'http://127.0.0.1:8000/authors/e42f3434-0836-4d8e-a91c-7e21d5ae5bc3/posts/206f3c50-e55c-40af-becb-bdb6f3e5cf90'}]}
        self.assertEqual(expected_output['items'][0]['type'], response.json()['items'][0]['type'])
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
