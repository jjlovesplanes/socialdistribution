from django.test import TestCase
from .models import Post, Comment, LikePost
from .forms import PostForm
from django.contrib.auth.models import User
from authors.models import Author
from PIL import Image
import os
from django.urls import reverse

from django.core.files.uploadedfile import SimpleUploadedFile

# Create your tests here.
class PostTests(TestCase):
    def setUp(self):
        # Create test user
        self.credentials = {'username': 'test', 'password': 'test'}
        new_user = User.objects.create_user(**self.credentials)
        new_user.save()
        new_user_model = User.objects.get(username="test")   
        new_author = Author.objects.create(user = new_user_model, 
                            host = "http://127.0.0.1:8000/",
                            github = "https://github.com/orgs/uofa-cmput404/teams/hypertext", 
                            profile_image = "https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        new_author.save()
        self.author = new_author
        self.client.login(**self.credentials)

    def test_create_post(self):
        '''
        Check that posts can be created
        '''
        
        expected_post = Post.objects.create(title="Test",
                             source =  "http://127.0.0.1:8000/authors/fabf22d9-c866-46c7-8016-ea036b1e5930",
                             origin = "http://127.0.0.1:8000/authors/fabf22d9-c866-46c7-8016-ea036b1e5930",
                             description = "Look at my post",
                             content="123", 
                             author=self.author) # post that should be created after submitting form
        response = self.client.post('/posts/create/', {"title": "Test", "content": "123", "author": self.author})
        self.assertTrue(response.status_code == 200)
        post = Post.objects.get(title="Test")
        self.assertEqual(post, expected_post)

    def test_create_post_with_image(self):
        '''
        Check that posts can be created with images using the Form
        '''
        image_path = r"posts\images\yoda.jpeg"

        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Create test post form data including image
        form_data = {
            'title': 'Test with Image',
            'content_markdown': 'Content with Image',
            'visibility': 'PUBLIC',
            'author': self.author.id,
            'image': SimpleUploadedFile('image.jpg', image_data, content_type='image/jpeg')
        }

        # Post form data to create_post view
        response = self.client.post(reverse('create_post'), data=form_data, format='multipart')

        # Check if post was created successfully
        self.assertEqual(response.status_code, 302)  # Assuming successful redirect
        self.assertEqual(response.url, '/')  # Assuming redirect to home page

        # Optionally, you can check if the post with image exists in the database
        self.assertTrue(Post.objects.filter(title='Test with Image').exists())

        retrieved_post = Post.objects.get(title='Test with Image')

        # Assert that the image URL exists
        self.assertIsNotNone(retrieved_post.image_url)


    def test_PostForm_exists(self):
        '''
        If the user clicks "Post" without changing anything, the post remains unchanged
        '''


        form_data = {
        'title': "Test",
        'content_markdown': "123",
        'visibility': "PUBLIC",
        'author': self.author.id,
        }

        # Post form data to create_post view
        response = self.client.post(reverse('create_post'), data=form_data, format='multipart')

        # Check if post was created successfully
        self.assertEqual(response.status_code, 302)  # Assuming successful redirect
        self.assertEqual(response.url, '/')  # Assuming redirect to home page

        # Check if the post exists and check if the title and content are the same.
        retrieved_post = Post.objects.get(title= "Test")
        self.assertEqual(retrieved_post.title,"Test")
        self.assertEqual(retrieved_post.content_markdown,"123")


class CommentTests(TestCase):
    def setUp(self):
        # Create test user
        self.credentials = {'username': 'test', 'password': 'test'}
        new_user = User.objects.create_user(**self.credentials)
        new_user.save()
        new_user_model = User.objects.get(username="test")   
        new_author = Author(user=new_user_model, 
                            github="https://github.com/orgs/uofa-cmput404/teams/hypertext", 
                            profile_image="https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        new_author.save()
        self.author = new_author
        self.client.login(**self.credentials)

        # Create test public post
        self.new_post = Post.objects.create(title="Test Post", content="Testing", author=new_author)


    def test_comment_on_post(self):
        '''
        Check that authors can comment on posts
        '''
        new_comment = Comment.objects.create(post = self.new_post,
                                             author = self.author,
                                             body = "WE ARE WRITING OUR COMMENT RN",
                                             content_type = "text/plain"
                                             )
        
        retrieved_comment = Comment.objects.get(post = self.new_post)
        self.assertEqual(new_comment, retrieved_comment)
    
    def test_comment_through_form(self):
        # Define the comment data
        comment_data = {
            'body': 'Test Comment Body'
        }

        # Post the comment to the AddCommentView
        response = self.client.post(reverse('add_comment', kwargs={'pk': self.new_post.pk}), data=comment_data)
        
        # Check if the comment was successfully added
        self.assertEqual(response.status_code, 302)  # Assuming successful redirect
        self.assertTrue(Comment.objects.filter(post=self.new_post, body='Test Comment Body').exists())

        retrieved_comment = Comment.objects.get(post=self.new_post, body='Test Comment Body')

        self.assertEqual(retrieved_comment.body, "Test Comment Body")
        

class LikePostTests(TestCase):
    def setUp(self):
        # Create test user
        self.credentials = {'username': 'test', 'password': 'test'}
        new_user = User.objects.create_user(**self.credentials)
        new_user.save()
        new_user_model = User.objects.get(username="test")   
        self.new_author = Author(user = new_user_model, github = "https://github.com/orgs/uofa-cmput404/teams/hypertext", profile_image = "https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        self.new_author.save()
        self.author = self.new_author
        self.client.login(**self.credentials)

        # Create test public post
        self.new_post = Post(title = "Test Post", content = "Testing", author = self.new_author)
        self.new_post.save()

    def test_like_post(self):
        
        like_obj = LikePost.objects.create(post = self.new_post,
                                           author = self.author )
        
        retrieved_obj = LikePost.objects.get(post = self.new_post, 
                                             author = self.author)

        self.assertEqual(like_obj, retrieved_obj)
        