from django.shortcuts import render, redirect, get_object_or_404
from posts.models import Post 
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models.functions import Lower
from authors.models import Author, Follower, Node
from authors.serializers import AuthorSerializer
from posts.models import Notification
from .forms import AuthorForm, ShareForm
from datetime import datetime
from posts.serializers import PostSerializer
from django.http import JsonResponse, HttpResponse
import pytz
import pyimgur
import os
import tempfile
import requests
import base64
import json
from authors.views import send_to_node
from config import config

# Create your views here.
def stream(request):
    if request.user.is_superuser:
            logout(request)

    posts = Post.objects.filter(visibility="PUBLIC")
    if request.user.is_authenticated:
        current_user = Author.objects.get(user=request.user)
        github_name = current_user.github
        user_uuid = current_user.uuid

        # Retrieve follow Requests
        follow_requests = Follower.objects.filter(author_id = request.user.id, request_accepted = False)
        if follow_requests.count() == 0:
            follow_requests = None
        
        # Notifications
        notifications = Notification.objects.filter(receiver_user = current_user).order_by("-timestamp").exclude(action_type = "follow")
        # Get date/time of most recent post by current user (UTC time)
        most_recent_posts = Post.objects.filter(author=current_user).order_by('-created_at')
        if most_recent_posts.count() == 0:
            last_post_time = datetime.now(tz=pytz.utc).isoformat() # current UTC time in ISO 8601 format
        else:
            last_post_time = most_recent_posts[0].created_at.isoformat()
        
        remote_nodes = Node.objects.filter(is_active = True).exclude(host=request.build_absolute_uri('/')) # get active nodes (except local server)
        for node in remote_nodes:
            authorization = f"{node.username}:{node.password}"
            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
            # Handle other nodes appropriately
            if "nexapulse" in node.host:
                authors_url = f'{node.host}api/authors?request_host={request.build_absolute_uri("/")}'
            else:
                if node.api_prefixed:
                    authors_url = f'{node.host}api/authors/'
                else:
                    authors_url = f'{node.host}authors/'
            # Get all authors on node

            if config['enjoyers-host'] in node.host:
                # Team enjoyers uses not authorization header for the author endpoint
                authors_response = requests.get(authors_url)
            else:
                authors_response = requests.get(authors_url, headers=headers)
            if authors_response.status_code == 200:
                data = json.loads(authors_response.content)
                authors = data['items']
                for author in authors:
                    try:
                        author_obj = Author.objects.get(url = author['url'])
                    except Author.DoesNotExist:
                        # Create replica of remote author on our server
                        try:
                            user = User.objects.get(username=author['displayName'])
                            author_obj = Author.objects.get(user = user)
                        except User.DoesNotExist:
                            user = User.objects.create(username=author['displayName'], is_active=False)
                            uuid = author['id'].split('/')[-1]
                            author_obj = Author(user = user, uuid = uuid, github = author['github'], profile_image = author['profileImage'], host = author['host'], url = author['url'])
                            author_obj.save()

                        except Author.DoesNotExist:
                            pass
        
        # Get posts after adding remote posts
        posts = Post.objects.filter(visibility="PUBLIC")

        # User can see all of their posts and all public posts from all users
        posts = posts | Post.objects.filter(author=current_user, visibility="FRIENDS") | Post.objects.filter(author=current_user, visibility="UNLISTED")


    else: 
        github_name = None
        user_uuid = None
        last_post_time = None
        notifications = None
        follow_requests = None

    try:
        # User can see friend only posts from their friends
        friends = Follower.objects.filter(author_id=request.user.id, is_friend=True)
        friend_only_posts = Post.objects.none()
        for friend in friends:
            friend_only_posts = friend_only_posts | Post.objects.filter(author=friend.follower, visibility="FRIENDS")
        posts = (posts | friend_only_posts).order_by("-created_at") # show most recent public posts first

        # Working on sharing
        share_form = ShareForm()
        
        if posts.count() == 0:
            posts = None

    except Follower.DoesNotExist:
        posts = posts.order_by("-created_at") # show most recent public posts first
        follow_requests = None

    return render(request, "stream.html", {
        'posts': posts, 
        'shareform': share_form, 
        'user_uuid': user_uuid,
        'github': github_name,
        'last_post_time': last_post_time, 
        'follow_requests': follow_requests, 
        'notifications': notifications
    })

def login_user(request):
    if request.method == "POST":
        username = request.POST.get('inputUsername')
        password = request.POST.get('inputPassword')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.info(request, "Incorrect login informations")
            return redirect("login")

        if user.is_active:
            authenticated_user = authenticate(username=username, password=password)
            if authenticated_user is not None:
                login(request, authenticated_user)
                return redirect("/")
            else:
                messages.info(request, "Incorrect password")
                return redirect("login")
        else:
            messages.info(request, "Your account has not been approved yet by the administrator.")
            return redirect("login")
    else:
        return render(request, "login.html")


def signup_user(request):
    if request.method == 'POST':
        username = request.POST['inputUsername']
        email = request.POST['inputEmail']
        github = request.POST['inputGitHub']
        password = request.POST['inputPassword']
        password2 = request.POST['inputPassword2']
        if request.build_absolute_uri('/') != "http://127.0.0.1:8000/":
            host = 'https://' + request.get_host() + '/'
        else:
            host = 'http://' + request.get_host() + '/'
    
        if password != password2:
            messages.info(request, 'Passwords dont match')
            return redirect("signup")
        elif User.objects.filter(username=username).exists():
            messages.info(request, 'username taken')
            return redirect("signup")
        
        if 'inputProfileImage' in request.FILES:
            # Handle the image upload
            image = request.FILES['inputProfileImage']
            # Save the InMemoryUploadedFile to a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                for chunk in image.chunks():
                    temp.write(chunk)
            temp_path = temp.name

            try:
                uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                profile_image = uploaded_image.link
            except KeyError:
                print("Error uploading image to Imgur")
        
        # Create User Object and set is_active to False
        new_user = User.objects.create_user(username=username,email=email,password=password, is_active=False)
        new_user.save()

        # Creat Author object
        new_user_model = User.objects.get(username=username)    
        new_author = Author(user = new_user_model, id = new_user_model.id, github = github,profile_image = profile_image, host = host)
        new_author.save()
        new_author.url = f"{host}authors/{new_author.uuid}"
        new_author.save()
            
        # login(request,new_user)
        return redirect("login")
    else:
        return render(request, "signup.html")

@login_required
def logout_user(request):
    if request.method == "POST":
        logout(request)
        return redirect('/')


@login_required
def profile(request, id):
    author = get_object_or_404(Author, id=id)
    current_user = Author.objects.get(id=request.user.id) # used to check if the user follows the author whose profile we are viewing
    is_follower = Follower.objects.filter(author=author, follower=current_user, request_accepted=True)
    if author.host != current_user.host:
        # Check if foreign author follows the current user
        if author.host[-1] != '/':
            # Host name should have a / at the end
            host = author.host + '/'
        else:
            host = author.host

        node = get_object_or_404(Node, host = host, is_active = True)
        authorization = f"{node.username}:{node.password}"
        headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
        if node.api_prefixed:
            url = author.url.split('/authors/')
            followers_url = f'{url[0]}/api/authors/{url[1]}/followers/{current_user.url}'
        else:
            followers_url = f'{author.url}/followers/{current_user.url}'
        response = requests.get(followers_url, headers=headers)
        
        if response.status_code == 200:
            is_friend = Follower.objects.filter(author=author, follower=current_user, is_friend=True)
        else:
            is_friend = False
        
    else:
        is_friend = Follower.objects.filter(author=author, follower=current_user, is_friend=True)
        
    request_sent = Follower.objects.filter(author=author, follower=current_user, request_accepted=False)
    if request.user.id == id:
        # Case 1: User is visiting their own profile
        posts = Post.objects.filter(author=id, shared_user__isnull = True).order_by("-created_at")
        is_friend = True # edge case: authors follow themselves
    elif is_friend:
        # Case 2: User is visiting a profile belonging to an author they are friends with
        posts = (Post.objects.filter(author=id, shared_user__isnull = True, visibility="PUBLIC") | Post.objects.filter(author=id, shared_user__isnull = True, visibility="FRIENDS")).order_by("-created_at")
    else:
        # Case 3: User is visiting a profile belonging to an author they aren't friends with
        posts = Post.objects.filter(author=id, shared_user__isnull = True).filter(visibility="PUBLIC").order_by("-created_at")
    
    # Include shared posts
    posts = posts | Post.objects.filter(shared_user=id)
    
    # Get number of followers and users following
    num_followers = Follower.objects.filter(author_id=id, request_accepted=True).count()
    num_following = Follower.objects.filter(follower_id=id, request_accepted=True).count()

    if author.github and 'github.com/' in author.github:
        github_name = author.github.split('github.com/')[1]
    else:
        github_name = author.github

    if posts.count() == 0:
        posts = None
    # Edit Profile Form
    form = AuthorForm(instance=author)

    # Share Post Form
    share_form = ShareForm()
    return render(request, "profile.html", 
                  {'posts': posts, 
                   'author': author, 
                   'current_user': current_user,
                   'github_name': github_name, 
                   'is_friend': is_friend, 
                   'is_follower': is_follower, 
                   'request_sent': request_sent,
                   'num_followers': num_followers, 
                   'num_following': num_following, 
                   'shareform': share_form,
                   'form': form})

imgur = pyimgur.Imgur('c431432680ddf1e')

def edit_profile(request, id):
    author = get_object_or_404(Author, id=id)
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES, instance=author)
        if form.is_valid():
            # Check if an image was uploaded
            if 'image' in request.FILES:
                # Handle the image upload
                image = request.FILES['image']
                # Save the InMemoryUploadedFile to a temporary file
                with tempfile.NamedTemporaryFile(delete=False) as temp:
                    for chunk in image.chunks():
                        temp.write(chunk)
                temp_path = temp.name

                try:
                    uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                    author.profile_image = uploaded_image.link
                except KeyError:
                    print("Error uploading image to Imgur")

            form.save()
            return redirect('/profile/%d'%id)
    else:
        form = AuthorForm(instance=author)
    return redirect('/profile/%d'%id)

@login_required
def followers(request, author_id):
    get_object_or_404(Author, id=author_id) # return 404 if author with given id not found
    try:
        followers = Follower.objects.filter(author_id=author_id, request_accepted=True).order_by(Lower('author__user__username')) # order alphabetically by username
        if followers.count() == 0:
            followers = None
    except Follower.DoesNotExist:
        followers = None
    return render(request, 'followers.html', {'users': followers, 'title': "Followers"})

@login_required
def following(request, author_id):
    author = get_object_or_404(Author, id=author_id) # return 404 if author with given id not found
    try:
        following = Follower.objects.filter(follower_id = author_id, request_accepted=True).order_by(Lower('author__user__username')) # order alphabetically by username
        if following.count() == 0:
            following = None
    except Follower.DoesNotExist:
        following = None

    return render(request, 'following.html', {'users': following, 'title': "Following", 'author': author})

@login_required
def users(request):
    input = request.GET.get('input')
    if input:
        # Display authors containing input as a substring
        authors = Author.objects.filter(user__username__icontains=input).order_by(Lower("user__username"))
    else:
        # Display all authors
        authors = Author.objects.all().order_by(Lower("user__username"))
    return render(request, 'users.html', {'users': authors})

@method_decorator(login_required(login_url='/accounts/login/'), name='dispatch')
class SharedPostView(View):
    def post(self, request, pk, *args, **kwargs):
        original_post = Post.objects.get(pk = pk)
        # Create the form and pass in the post request data
        form = ShareForm(request.POST)

        if form.is_valid():
            new_post = Post(

                shared_title = self.request.POST.get('shared_title'),
                shared_body = self.request.POST.get('shared_body'),
                shared_on = timezone.now(),
                # shared_user = self.request.user,
                shared_user = Author.objects.get(id = request.user.id),
                copy_of_original_id = original_post.copy_of_original_id,
                title = original_post.title,
                content = original_post.content,
                content_markdown = original_post.content_markdown,
                content_html = original_post.content_html,
                author = original_post.author,
                created_at = original_post.created_at,
                visibility="PUBLIC",
                image_url = original_post.image_url,) 
            
            new_post.save()

             # Creating notifications for creating post to all of the followers
            # Check if the author has any followers
            followers = Follower.objects.filter(author=new_post.shared_user)

            if followers.exists():
                # There are followers, create notifications for each follower
                for follower in followers:
                        if follower.request_accepted == True and new_post.shared_user.host == follower.follower.host:
                            # Local
                            share_notification = Notification.objects.create(post=new_post,
                                                                            action_user=new_post.shared_user,
                                                                            receiver_user=follower.follower,
                                                                            action_type='post',
                                                                            notification_message = f"{new_post.shared_user} shared a post",
                                                                            timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat())
                            share_notification.save()

                        elif follower.request_accepted == True and new_post.shared_user.host != follower.follower.host:
                            # Remote
                            # Create notification in inbox (possibly remote inbox)
                            serializer = PostSerializer(new_post, context={"request": request})
                            post_json = serializer.data

                            shared_author_serializer = AuthorSerializer(new_post.shared_user, context={"request": request})
                            # Add necessary fields for sharing posts to nexapulse
                            if "nexapulse" in follower.follower.host:
                                original_author_serializer = AuthorSerializer(new_post.author, context={"request": request})
                                post_json['author'] = shared_author_serializer.data
                                post_json['sharedBy'] = original_author_serializer.data
                                post_json['content'] = new_post.shared_body
                                post_json['originalContent'] = new_post.content_markdown
                                post_json['isShared'] = True

                                # Determine if an reference to an image post needs to be sent
                                if original_post.image_url:
                                    post_json['image_ref'] = new_post.copy_of_original_id

                            elif config['enjoyers-host'] in follower.follower.host:
                                post_json['author'] = shared_author_serializer.data
                                post_json['published'] = str(new_post.shared_on)

                                # Determine if an reference to an image post needs to be sent
                                if original_post.image_url:
                                    post_json['image_ref'] = new_post.copy_of_original_id

                            else:
                                # Add necessary fields for sharing posts between instances
                                post_json['shared_title'] = new_post.shared_title
                                post_json['shared_body'] = new_post.shared_body
                                post_json['shared_user'] = shared_author_serializer.data
                                post_json['copy_of_original_id'] = new_post.copy_of_original_id
                            
                            host_name = follower.follower.host
                            json_body = json.loads(json.dumps(post_json))
                            send_to_node(host_name, follower.follower.url, json_body)

            
            # if no followers, don't do anything
            else:
                pass

        return redirect('/')
    
def ajax_follow(request):
    if request.user.is_authenticated:
        follow_requests = Follower.objects.filter(author_id = request.user.id, request_accepted = False)
    else:
        follow_requests = None
        return HttpResponse(status_code=500)
    if follow_requests.count() == 0:
        data = []
    else: 
        data = []
        for req in range(len(follow_requests)):
            data.append({"follower_id":follow_requests[req].follower.id, "follower_name":follow_requests[req].follower.user.get_username(),"follower_profile_image":follow_requests[req].follower.profile_image,
                        "follower_url": follow_requests[req].follower.url, 'authorID':follow_requests[req].author.url})
    return JsonResponse({"followers_req":data})

def ajax_notification(request):
    if request.user.is_authenticated:
        current_user = Author.objects.get(user=request.user)
        notifications = Notification.objects.filter(receiver_user = current_user).order_by("-timestamp").exclude(action_type = "follow")
    else:
        return HttpResponse(status_code=500)
    data = []
    for req in range(len(notifications)):
        data.append({"notification_post_id":notifications[req].post.id, "notification_message":notifications[req].notification_message})
                    
    return JsonResponse({"notifications":data})