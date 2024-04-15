from django.test import TestCase
from django.urls import reverse
from authors.models import Author, Follower
from .forms import AuthorForm
from posts.models import Post
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import HttpRequest
import uuid

# Create your tests here.
class LogInTest(TestCase):
    def setUp(self):
        self.credentials = {
            'username': 'testuser',
            'password': 'secret'}
        User.objects.create_user(**self.credentials)
    def test_login(self):
        # send login data
        response = self.client.post('/login/', self.credentials, follow=True)
        # should be logged in now
        user = User.objects.get(username="testuser")
        self.assertTrue(user.is_active)

class ProfileTests(TestCase):
    def setUp(self):
        self.credentials = {'username': 'test', 'password': 'test'}
        new_user = User.objects.create_user(**self.credentials)
        new_user.save()
        new_user_model = User.objects.get(username="test")   
        new_author = Author(user = new_user_model, uuid= uuid.uuid4(), github = "https://github.com/orgs/uofa-cmput404/teams/hypertext", profile_image = "https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        new_author.save()
        self.author = new_author
        self.url = reverse("profile", args=(self.author.id,))
        self.client.login(**self.credentials)

    def test_no_posts(self):
        '''
        If the user whose profile we are viewing has no posts, an appropriate message is displayed
        '''
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() has no posts
        self.assertEqual(response.context["posts"], None)
        self.assertContains(response, "No posts found")

    def test_with_post(self):
        '''
        If the user whose profile we are viewing has a public post, we should be able to see 
        the post on the profile page
        '''
        # Create Post
        Post.objects.create(title="Test", content="123", author=self.author)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() now has 1 post
        self.assertEqual(response.context["posts"].count(), 1)
        self.assertContains(response, "Test")

    def test_edit_both_fields(self):
        '''
        Check that the edit profile form is valid when both github and profile image are inputted
        '''
        data = {
            'github': 'https://github.com/uofa-cmput404/w24-project-hypertextheroes',
            'profile_image': 'https://avatars.githubusercontent.com/u/46386037?s=48&v=4'
        }
        form = AuthorForm(data={
            'github': data['github'],
            'profile_image': data['profile_image']
        })
        self.assertTrue(form.is_valid())

    def test_edit_github(self):
        '''
        Check that the edit profile form is valid when only the github link is inputted
        '''
        data = {
            'github': 'https://github.com/uofa-cmput404/w24-project-hypertextheroes'
        }
        form = AuthorForm(data={
            'github': data['github']
        })
        self.assertTrue(form.is_valid())

    
    def test_edit_profile_image(self):
        '''
        Check that the edit profile form is valid when only the profile image link is inputted
        '''
        data = {
            'profile_image': 'https://avatars.githubusercontent.com/u/46386037?s=48&v=4'
        }
        form = AuthorForm(data={
            'profile_image': data['profile_image']
        })
        self.assertTrue(form.is_valid())

    def test_edit_no_fields(self):
        '''
        Check that the edit profile form is valid when neither field is changed
        '''
        form = AuthorForm(data={})
        self.assertTrue(form.is_valid())


class StreamTests(TestCase):
    def setUp(self):
        self.credentials = {'username': 'test', 'password': 'test'}
        new_user = User.objects.create_user(**self.credentials)
        new_user.save()
        new_user_model = User.objects.get(username="test")   
        new_author = Author(user = new_user_model, uuid= uuid.uuid4(), github = "https://github.com/orgs/uofa-cmput404/teams/hypertext", profile_image = "https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        new_author.save()
        self.author = new_author
        self.client.login(**self.credentials)

    def test_no_posts(self):
        '''
        If there are no posts the user can access in the database, an appropriate message is displayed
        '''
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() has no posts
        self.assertEqual(response.context["posts"], None)
        self.assertContains(response, "No posts found")

    def test_with_post(self):
        '''
        If there is a public post, the post should be visibile on the stream page
        '''
        # Create Post
        Post.objects.create(title="Test", content="123", author=self.author)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() now has 1 post
        self.assertEqual(response.context["posts"].count(), 1)
        self.assertContains(response, "Test")

    def test_no_follow_requests(self):
        '''
        If the logged in user has no follow requests, an appropriate message is displayed
        '''
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() has no follow requests
        self.assertEqual(response.context["follow_requests"], None)
        self.assertContains(response, "No follow requests")

    def test_with_follow_request(self):
        '''
        If the logged in user has a follow request, it is displayed on the stream page
        '''
        # Create second author
        credentials = {'username': 'test2', 'password': 'test2'}
        second_user = User.objects.create_user(**credentials)
        second_user.save()
        second_user_model = User.objects.get(username="test2")   
        second_author = Author(user = second_user_model, uuid= uuid.uuid4(), github = "https://github.com/orgs/uofa-cmput404/teams/hypertext", profile_image = "https://avatars.githubusercontent.com/t/9336670?s=116&v=4")
        second_author.save()
        # Create follow request (request not accepted)
        Follower.objects.create(author=self.author, follower=second_author, request_accepted=False, is_friend=False)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # The author created in setUp() now has 1 follow request
        self.assertEqual(response.context["follow_requests"].count(), 1)
        self.assertContains(response, "test2")
