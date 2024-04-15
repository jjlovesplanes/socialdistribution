from django.shortcuts import render, redirect, get_object_or_404

from .models import Post, LikePost, Comment, Notification
from .serializers import PostSerializer
from authors.models import Author, Follower, Node
from authors.serializers import AuthorSerializer, CommentSerializer
from .forms import PostForm, CommentForm
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import pyimgur
import datetime
import os
import tempfile
import markdown
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import LikeComment
import json
import base64
import requests
from authors.views import send_to_node
from config import config

CLIENT_ID = os.getenv('f20f12f52c64b32')

# Create your views here.
def index(request):
    return render(request, "index.html")

def post_list(request, pk=None):
    if pk:
        post = get_object_or_404(Post, pk=pk)
    else:
        post = None

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            return redirect('/')
    else:
        form = PostForm(instance=post)

    posts = Post.objects.all()
    return render(request, 'blog/post_list.html', {'posts': posts, 'form': form})

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = Author.objects.get(id=request.user.id)
            # Check if an image was uploaded
            if 'image' in request.FILES:
                # Handle the image upload
                image = request.FILES['image']
                new_post.content_type = "application/base64"

                # Save the InMemoryUploadedFile to a temporary file
                with tempfile.NamedTemporaryFile(delete=False) as temp:
                    for chunk in image.chunks():
                        temp.write(chunk)
                temp_path = temp.name

                imgur = pyimgur.Imgur('c431432680ddf1e')
                try:
                    uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                    new_post.image_url = uploaded_image.link
                except KeyError:
                    print("Error uploading image to Imgur")

                # Delete the temporary file
                os.unlink(temp_path)
            else:
                new_post.content = markdown.markdown(new_post.content)
            new_post.save()
            new_post.copy_of_original_id = new_post.id
            new_post.save()

            # Creating notifications for creating post to all of the followers
            # Check if the author has any followers
            followers = Follower.objects.filter(author=new_post.author)

            if followers.exists():
                # There are followers, create notifications for each follower
                for follower in followers:
                        if follower.request_accepted == True and new_post.author.host == follower.follower.host:
                            # Local
                            comment_notification = Notification.objects.create(post=new_post,
                                                                            action_user=new_post.author,
                                                                            receiver_user=follower.follower,
                                                                            action_type='post',
                                                                            notification_message = f"{new_post.author} created a new post",
                                                                            timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())
                            comment_notification.save()

                        elif follower.request_accepted == True and new_post.author.host != follower.follower.host:
                            # Remote
                            # Make if statement that checks if there is an image and markdown

                            host_name = follower.follower.host

                            if new_post.image_url:
                                # Post has an image (convert it to base64)
                                # Save references to post content and image
                                original_content_markdown = new_post.content_markdown
                                original_image_url = new_post.image_url
                                if config['enjoyers-host'] not in host_name and "nexapulse" not in host_name:
                                     # Send only text post to nexapulse and enjoyers
                                    headers = {'User-Agent': 'socialdistribution/0.1'}
                                    response = requests.get(new_post.image_url, headers=headers)

                                    if response.status_code == 200:
                                        image = base64.b64encode(response.content)#.decode('utf-8')

                                    if config['syntax-host'] in host_name:
                                        # Send string to team syntax
                                        image = base64.b64encode(response.content).decode('utf-8')
                                    # Created two post objects and we will not save it
                                    send_new_image_post = new_post
                                    send_new_image_post.content_type = "application/base64"
                                    send_new_image_post.content_markdown = image

                                    # made the postSerializer and send_to_node
                                    serializer = PostSerializer(send_new_image_post, context={"request": request})
                                    image_post_json = serializer.data
                                    json_body = json.loads(json.dumps( image_post_json))
                                    send_to_node(host_name, follower.follower.url, json_body )

                                if new_post.content_markdown and config['syntax-host'] not in host_name:
                                    # Send only image post to team syntax
                                    # Post also has markdown
                                    send_new_markdown_post = new_post
                                    send_new_markdown_post.content_type = "text/markdown"
                                    send_new_markdown_post.image_url = None
                                    send_new_markdown_post.content_markdown = original_content_markdown

                                    # made the postSerializer and send_to_node
                                    serializer = PostSerializer(send_new_markdown_post, context={"request": request})
                                    markdown_post_json = serializer.data

                                    if config['enjoyers-host'] in host_name or config['nexapulse-host'] in host_name:
                                        # Add image_ref field if follower is from enjoyers' server (expected field on their side)
                                        markdown_post_json['image_ref'] = str(new_post.id)

                                    json_body = json.loads(json.dumps( markdown_post_json))
                                    send_to_node(host_name, follower.follower.url, json_body )
                                
                                # Revert image_url and content_markdown fields back to original
                                new_post.image_url = original_image_url
                                new_post.content_markdown = original_content_markdown

                            else:
                                # markdown post
                                serializer = PostSerializer(new_post, context={"request": request})
                                post_json = serializer.data
                                host_name = follower.follower.host
                                json_body = json.loads(json.dumps(post_json))
                                send_to_node(host_name, follower.follower.url, json_body)

            
            # if no followers, don't do anything
            else:
                pass

            return redirect('/')  # Redirect to the stream page
    else:
        form = PostForm()
    return render(request, 'posts/create_post.html', {'form': form})

def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = Author.objects.get(user=request.user)  # Get the Author instance for the current user
            # Check if an image was uploaded
            if 'image' in request.FILES:
                # Handle the image upload
                image = request.FILES['image']
                # Save the InMemoryUploadedFile to a temporary file
                with tempfile.NamedTemporaryFile(delete=False) as temp:
                    for chunk in image.chunks():
                        temp.write(chunk)
                temp_path = temp.name

                imgur = pyimgur.Imgur('c431432680ddf1e')
                try:
                    uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                    post.image_url = uploaded_image.link
                except KeyError:
                    print("Error uploading image to Imgur")
            else:
                post.content_html = markdown.markdown(post.content_markdown)
            post.save()
            
            # Creating notifications for creating post to all of the followers
            # Check if the author has any followers
            followers = Follower.objects.filter(author=post.author)

            if followers.exists():
                # There are followers, create notifications for each follower
                for follower in followers:
                        if follower.request_accepted == True and post.author.host == follower.follower.host:
                            # Local
                            comment_notification = Notification.objects.create(post=post,
                                                                            action_user=post.author,
                                                                            receiver_user=follower.follower,
                                                                            action_type='post',
                                                                            notification_message = f"{post.author} created a new post",
                                                                            timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())
                            comment_notification.save()

                        elif follower.request_accepted == True and post.author.host != follower.follower.host:
                            # Remote
                            # Create notification in inbox (possibly remote inbox)
                            post_json = PostSerializer(post, context={"request": request})
                            host_name = follower.follower.host
                            json_body = json.loads(json.dumps(post_json.data))
                            send_to_node(host_name, follower.follower.url, json_body)

            
            # if no followers, don't do anything
            else:
                pass
            # TODO: This should redirect back to the profile page if the user clicked Edit Post in the profile page
            # Problem: Can only retrieve previous url (using request.META.get('HTTP_REFERER')) which is the edit post page
            return redirect('/')
    else:
        form = PostForm(instance=post)
    return render(request, 'posts/edit_post.html', {'form': form})

@require_http_methods(["POST"])  # Only allow POST requests
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # Only allow the author or person who shared the post (if it is a shared post) to delete the post
    if request.user == post.author.user or request.user == post.shared_user.user: 
        post.delete()
    return redirect('/')  # Redirect to the stream page after deletion

def view_post(request, pk):
    post = Post.objects.get(id=pk)
    return render(request, 'posts/view_post.html', {'post': post})

@login_required
def like_post(request):
    author = Author.objects.get(user=request.user)
    post_id = request.GET.get('post_id')

    post = Post.objects.get(id=post_id)

    # This will query the LikePost of the user and see if the post_id already exists.
    # This will return any LikePost instance if the user already like this.
    like_filter = LikePost.objects.filter(post = post, author = author).first()

    # Referenced: https://stackoverflow.com/questions/35796195/how-to-redirect-to-previous-page-in-django-after-post-request (accessed Feb. 21 2024)

    # Add/remove like locally
    if like_filter == None:
        # Save the new LikePost object
        new_like = LikePost.objects.create(post = post, author = author)
        new_like.save()
        post.no_of_likes = post.no_of_likes + 1
        post.save()

        Notification.objects.create(
            post=post,
            action_user=author,
            receiver_user=post.author,  
            action_type='Like',
            timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
            notification_message = f"{author} liked your post"
        )

    # if the user already liked the post, then we unlike and delete.
    else:
        like_filter.delete()
        post.no_of_likes = post.no_of_likes - 1
        post.save()

    # Create like object to send to remote user's inbox
    remote_nodes = Node.objects.filter(is_active=True).exclude(host=request.build_absolute_uri('/')) # get active nodes (except local server)
    for node in remote_nodes:
        send_like_to_inbox(request, node, node.host, author, post)
        
    return redirect(request.META.get('HTTP_REFERER'))
    
def send_like_to_inbox(request, node, host, author, post):
    author_json = AuthorSerializer(author, context={"request": request})
    author_data = author_json.data
    if node:
        # Send to remote inbox
        if config['syntax-host'] in node.host:
            # Get a user from syntax's server to send comment to (can't send to replica author)
            url = config['syntax-host'] + '/api/authors/'
            authorization = f"{node.username}:{node.password}"
            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
            authors_response = requests.get(url, headers=headers)
            if authors_response.status_code == 200:
                data = json.loads(authors_response.content)
                authors = data['items']
                author_object = authors[0]
                author_id = author_object['id'].split('/')[-1]
                uuid = f"{node.host}authors/{author_id}"

            else:
                return
        else:
            uuid = f"{node.host}authors/{post.author.uuid}"

        if config['syntax-host'] in node.host:
            # Add / to end of post url for team syntax
            if post.origin:
                # Post from team syntax's server
                post_url = f'{post.origin}/'
            else:
                # Post from our server
                post_url = f'{config["host"]}authors/{post.author.uuid}/posts/{post.id}'
        elif node.api_prefixed:
            # Add api prefix to url
            post_url = f'{node.host}api/authors/{post.author.uuid}/posts/{post.id}'
        else:
            post_url = f'{node.host}authors/{post.author.uuid}/posts/{post.id}'
            
        like_object = {
            "summary": f"{author} liked your post",
            "type": "Like",
            "author": author_data,
            "object": post_url
        }
        json_body = json.loads(json.dumps(like_object))
        send_to_node(host, uuid, json_body) # Create notification in inbox
        
    else:
        like_object = {
            "summary": f"{author} liked your post",
            "type": "Like",
            "author": author_data,
            "object": f"{request.build_absolute_uri('/')}authors/{post.author.uuid}/posts/{post.id}"
        }
        json_body = json.loads(json.dumps(like_object))
        # Send to local inbox
        send_to_node(host, post.author.url, json_body) # Create notification in inbox

def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    author = Author.objects.get(user=request.user)
    like, created = LikeComment.objects.get_or_create(comment=comment, user=author)
    if not created:
        like.delete()
    return redirect(request.META.get('HTTP_REFERER', '/'))

class AddCommentView(CreateView):
    model = Comment
    template_name = 'add_comment.html'
    form_class = CommentForm
    #content_type = "text/markdown"
    
    def get(self, request, *args, **kwargs):
        # Store the referring URL in the session
        request.session['referring_url'] = request.META.get('HTTP_REFERER', '/')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.post = Post.objects.get(id = self.kwargs['pk'])
        form.instance.author = Author.objects.get(user=self.request.user)
        response = super().form_valid(form)

        # Create the notification object when someone makes a comment
        post = form.instance.post

        # Create like object to send to remote user's inbox
        remote_nodes = Node.objects.filter(is_active=True)
        for node in remote_nodes:
            send_comment_to_inbox(self.request, node, node.host, post, form.instance)

        return response

    def get_success_url(self):
        # Redirect to the stored referring URL from the session
        return self.request.session.pop('referring_url', '/')
    
def send_comment_to_inbox(request, node, host, post, comment_object):
    serialized_comment = CommentSerializer(comment_object, context = {"request": request})
    comment_json = serialized_comment.data
    comment_json["postId"] = comment_object.post.id
    json_body = json.loads(json.dumps(comment_json))

    if node:
        # Send to remote inbox
        """authorization = f"{node.username}:{node.password}"
        headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
        if node.api_prefixed:
            # Add api prefix to url
            author_url = f'{node.host}api/authors/{post.author.uuid}'
        else:
            author_url = f'{node.host}authors/{post.author.uuid}'"""
        # Check if the author exists on the remote server
        # response = requests.get(author_url, headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})
        # if response.status_code == 200:
        # Send comment object to remote inbox (do not include api prefix)

        if config['syntax-host'] in node.host:
            # Get a user from syntax's server to send comment to (can't send to replica author)
            url = config['syntax-host'] + '/api/authors/'
            authorization = f"{node.username}:{node.password}"
            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
            authors_response = requests.get(url, headers=headers)
            if authors_response.status_code == 200:
                data = json.loads(authors_response.content)
                authors = data['items']
                author_object = authors[0]
                author_id = author_object['id'].split('/')[-1]
                uuid = f"{node.host}authors/{author_id}"

            else:
                return
        else:
            uuid = f"{node.host}authors/{post.author.uuid}"
        send_to_node(host, uuid, json_body) # Create notification in inbox
    else:
        # Send to local inbox
        send_to_node(host, post.author.url, json_body) # Create notification in inbox
