from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseNotAllowed, Http404
from rest_framework import status, exceptions
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Author, Follower, Node
from posts.models import LikePost, Post, Comment, LikeComment, Notification
from .serializers import *
from posts.serializers import *
from rest_framework.generics import GenericAPIView
from base64 import b64decode
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.authentication import SessionAuthentication, BaseAuthentication
import datetime
from posts.models import Notification, Post, Comment
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from urllib.parse import urlparse
from django.utils.dateparse import parse_datetime
import base64
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import pyimgur
import tempfile
from config import config


class NodeAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header and auth_header.startswith('Basic '):
            auth_decoded = b64decode(auth_header[6:]).decode('utf-8')
            username, password = auth_decoded.split(':', 1)
            try:
                user = User.objects.get(username=username)
                if not user.check_password(password):
                    raise exceptions.AuthenticationFailed('Incorrect user authentication credentials.')
            except User.DoesNotExist:
                pass
            else:
                return (user, None)
            try:
                node = Node.objects.get(username=username)
                if node.is_active:
                    if password == node.password:
                        return (node, None)
                    else:
                        raise exceptions.AuthenticationFailed('Incorrect node authentication credentials.')
                else:
                    raise exceptions.AuthenticationFailed('Node inactive')
            except Node.DoesNotExist:
                raise exceptions.AuthenticationFailed('Node Unauthorized')
            
        raise exceptions.AuthenticationFailed('Unauthorized access') 

@api_view(['POST', 'PUT', 'DELETE'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def follow_request(request, author_id, follower_id):
    author = Author.objects.get(url=author_id)
    follower = Author.objects.get(url=follower_id)
    
    if request.method == "POST":
        # Create follower request
        if author.host != follower.host:
            new_request = Follower.objects.create(author=author, follower=follower, request_accepted=False)
            new_request.save()

        # Create notification in inbox (possibly remote inbox)
        actor_json = AuthorSerializer(follower, context={"request": request})
        object_json = AuthorSerializer(author, context={"request": request})
        body = {
            "type": "Follow",      
            "summary":f"{follower} wants to follow {author}",
            "actor": actor_json.data,
            "object": object_json.data
        }
        host_name = author_id.split("/authors")[0] + '/'
        json_body = json.loads(json.dumps(body))
        send_to_node(host_name, author_id, json_body)

        # Go back to author's profile page
        return redirect('/profile/%d/' % author.id)
    
    elif request.method == "PUT":
        # Accept follower request
        follow_request = Follower.objects.get(author=author, follower=follower)  # Follower request to author
        follow_request.request_accepted = True

        reverse_follow_request = Follower.objects.filter(author=follower, follower=author, request_accepted=True).first()

        if reverse_follow_request:
            follow_request.is_friend = True
            reverse_follow_request.is_friend = True
            reverse_follow_request.save()

        follow_request.save()

        # Send to inbox (if necessary)
        if follower.host != author.host:
            actor_json = AuthorSerializer(follower, context={"request": request})
            object_json = AuthorSerializer(author, context={"request": request})
            host_name = follower.host
            if config['syntax-host'] in host_name or config['enjoyers-host'] in host_name:
                object_type = "Approve Follow"
            else:
                object_type = "Follow"

            body = {
                "type": object_type,      
                "summary":f"{follower} wants to follow {author}",
                "actor": actor_json.data,
                "object": object_json.data
            }
            json_body = json.loads(json.dumps(body))
            send_to_node(host_name, follower.url, json_body)

        return redirect('/')

    
    elif request.method == "DELETE":
        # Decline follower request
        Follower.objects.filter(author=author, follower=follower).delete()

        # Send to inbox (if necessary)
        if follower.host != author.host:
            actor_json = AuthorSerializer(follower, context={"request": request})
            object_json = AuthorSerializer(author, context={"request": request})
            host_name = follower.host
            if config['syntax-host'] in host_name or config['enjoyers-host'] in host_name:
                object_type = "Deny Follow"
            else:
                object_type = "Follow"

            body = {
                "type": object_type,      
                "summary":f"{follower} wants to follow {author}",
                "actor": actor_json.data,
                "object": object_json.data
            }
            json_body = json.loads(json.dumps(body))
            send_to_node(host_name, follower.url, json_body)
        return redirect('/')

# API CALLS
# Pagination usage : https://www.django-rest-framework.org/api-guide/pagination/
    
@swagger_auto_schema(
method='get',
tags=['authors', 'remote'], 
operation_description="Retrieves all profiles on the server (paginated)",
manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page number"),
        openapi.Parameter('size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Number of profiles per page"),
    ],
responses={
    200: AuthorResponseSerializer,
}
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def authors_list(request):
    page = request.GET.get("page")
    page_size = request.GET.get("size")
    authors = Author.objects.filter(host=request.build_absolute_uri('/'))
    if page and page_size:
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        paginated_results = paginator.paginate_queryset(authors, request)
        serializer = AuthorSerializer(paginated_results, many=True, context={"request": request})
    else:
        serializer = AuthorSerializer(authors, many=True, context={"request": request})
    author_list_response = {"type": "authors", "items": serializer.data}
    return Response(author_list_response)

@swagger_auto_schema(
    method='get',
    tags=['authors', 'remote'],
    operation_description="Retrieves the profile of a single author.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
        ],
    responses={
        200: AuthorSerializer,
        404: openapi.Response("Author not found with the provided UUID.")
    }
)
@swagger_auto_schema(
    method='put',
    tags=['authors'],
    operation_description="Updates the profile of a single author.",
    request_body=AuthorSerializer
    )
@api_view(['GET', 'PUT'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def single_author(request, uuid):
    try:
        # author = get_object_or_404(Author, uuid = uuid)
        author = Author.objects.get(uuid=uuid) # Reason I changed from above is so that we can have a custom error message when its 404
    except Author.DoesNotExist:
        return Response("Author not found with the provided UUID.", status=404)
    if request.method == "GET":
        serializer = AuthorSerializer(author, context={"request": request})
        return Response(serializer.data)
    elif request.method == "PUT":
        serializer = AuthorSerializer(author, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.update(author, serializer.validated_data)
            return Response(serializer.data)
        return Response(status=400, data=serializer.errors)

@swagger_auto_schema(
    method='get',
    tags=['followers', 'remote'],
    operation_description="Get the list of followers for the provided author.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
        ],
    responses={
            200: FollowersResponseSerializer,
            404: openapi.Response("Author not found with the provided UUID."),
        }
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def followers_list(request, uuid):
    try:
        author = Author.objects.get(uuid=uuid) 
    except Author.DoesNotExist:
        return Response("Author not found with the provided UUID.", status=404)
    try:
        followers = Follower.objects.filter(author=author, request_accepted=True)
        list_followers = []
        for follower in followers:
            list_followers.append(return_author_format(request, follower.follower))
        response = {"type": "followers", "items": list_followers}
    except Follower.DoesNotExist:
        response = {"type": "followers", "items": []}
    return Response(response)

@swagger_auto_schema(
    method='get',
    tags=['followers', 'remote'],
    operation_description="Checks if the foreign author is a follower of the author.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('foreign_author_id_path', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique path for the foreign author."),
        ],
    responses={
        200: ForeignFollowerResponseSerializer,
        400: openapi.Response("Author ID and Foreign author ID are the same"),
        404: openapi.Response("Foreign author is not a follower of given author"),
        }
)
@swagger_auto_schema(
    methods=['put'],
    tags=['followers'],
    operation_description="Adds foreign author as a follower of author.",
    responses={
        200: openapi.Response("Foreign author has been added as a follower"),
        400: openapi.Response("This author is already following you"),
    }
)
@swagger_auto_schema(
    methods=['delete'],
    tags=['followers'],
    operation_description="Removes foreign author as a follower of author."
)
@api_view(['GET', 'PUT', 'DELETE'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
# TODO: Check if foreign author ID is authenticated for a PUT request
def foreign_follower(request, uuid, foreign_author_id_path):
    foreign_author_id_decoded_url = foreign_author_id_path.split("%")
    foreign_author_id = foreign_author_id_decoded_url[0].split("/")[-1]
    # author = get_object_or_404(Author, uuid = uuid)
    try:
        author = Author.objects.get(uuid=uuid) 
    except Author.DoesNotExist:
        return Response("Author not found with the provided UUID.", status=404)
    try:
        foreign_author = Author.objects.get(uuid = foreign_author_id)

    except Author.DoesNotExist:
        host_name = foreign_author_id_path.split("/authors")[0] + '/'
        try:
            node = Node.objects.get(host = host_name, is_active = True)
            authorization = f"{node.username}:{node.password}"
            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
            response = requests.get(foreign_author_id_path, headers=headers)

            if response.status_code == 200:
                # Attempt to get Author object through URL (remote user)
                try:
                    foreign_author = Author.objects.get(url = foreign_author_id_path)
                
                except Author.DoesNotExist:
                    foreign_author_json = json.loads(response.content)
                    user = User.objects.create(username=foreign_author_json['displayName'], is_active=False)
                    new_author = Author(user = user, uuid = foreign_author_json['uuid'], github = foreign_author_json['github'], profile_image = foreign_author_json['profileImage'], host = foreign_author_json['host'], url = foreign_author_json['url'])
                    new_author.save()

                    foreign_author = new_author
                
            else:
                # Not a foreign author
                return Response(status = 404)
            
        except Node.DoesNotExist:
            # Do not have access to host of foreign author
            return Response(status = 404)

    followers = Follower.objects.filter(author=author, request_accepted=True) # returns a query set
    list_followers = []
    for follower in followers:
        list_followers.append(follower.follower)
        
    if request.method == "GET":
        if foreign_author in list_followers:
            follower_response = {
                "type": "Follower",
                "summary": "{} is a follower of {}".format(foreign_author, author),
                "actor": return_author_format(request, foreign_author),
                "object": return_author_format(request, author)
            }
            return Response(follower_response, status=status.HTTP_200_OK)
        elif uuid == foreign_author_id:
            return Response(status=400, data="Author ID and Foreign author ID are the same")
        else:
            return Response(status=404, data="Foreign author is not a follower of given author")
    elif request.method == "PUT":
        if foreign_author in list_followers:
            return Response(status=400, data="This author is already following you") 
        else:
            new_follower = Follower.objects.create(author=author, follower=foreign_author)
            new_follower.save()
            return Response(status=200, data="Foreign author has been added as a follower") 
    elif request.method == "DELETE":
        try:
            Follower.objects.get(author=author, follower=foreign_author).delete()
        except Follower.DoesNotExist:
            return Response(status=404, data="Follower not found")
        
        # Change friend status to false if foreign author follows author
        foreign_author_follower = Follower.objects.filter(author=foreign_author, follower=author, request_accepted=True).first()
        if foreign_author_follower:
            foreign_author_follower.is_friend = False
            foreign_author_follower.save()

        # Send follow object to remote inbox if foreign author is remote
        if foreign_author.host != author.host:
            actor_json = AuthorSerializer(foreign_author, context={"request": request})
            object_json = AuthorSerializer(author, context={"request": request})
            host_name = author.host

            if config['syntax-host'] in host_name:
                object_type = "Unfollow"
            elif config['enjoyers-host'] in host_name:
                object_type = "Deny Follow"
            else:
                object_type = "Follow"
            body = {
                "type": object_type,      
                "summary":f"{foreign_author} no longer follows {author}",
                "actor": actor_json.data,
                "object": object_json.data
            }
            json_body = json.loads(json.dumps(body))
            send_to_node(host_name, author.url, json_body)
                        
        return Response(status=204)
        
@swagger_auto_schema(
    tags=['comments', 'remote'],
    method='get',
    operation_description="Retrieves the list of comments for a post (paginated).",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page number"),
            openapi.Parameter('size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Number of comments per page"),
        ],
    responses={
        200: CommentsListSerializer,
        404: openapi.Response("Post with given post ID not found"),
    }
)
@swagger_auto_schema(
    tags=['comments'],
    method='post',
    operation_description="Creates a comment for the post with given post ID.",
    request_body=CommentSerializer,
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
        ]
)
@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def comments_api(request, uuid, post_id):
    if request.method == 'GET':
        author = Author.objects.get(uuid=uuid) 
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(status=404, data="Post with given post ID not found")
        url_path = request.build_absolute_uri()
        url_path_without_comments = '/'.join(url_path.split('/')[:-1])
        post_url = request.build_absolute_uri(url_path_without_comments)
        page = request.GET.get("page")
        page_size = request.GET.get("size")
        comments = Comment.objects.filter(post_id=post.id)
        if page and page_size:
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            paginated_comments = paginator.paginate_queryset(comments, request)
            comments = CommentSerializer(paginated_comments, many=True, context={"request": request})
        else:
            comments = CommentSerializer(comments, many=True, context={"request": request})
        comments_response = {
            "type": "comments",
            "page": page,
            "size": page_size,
            "post": post_url,
            "id": url_path,
            "comments": comments.data # comment_responses_list
        }
        return Response(comments_response, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        if request.data["type"] == "comment":
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response(status=404, data="Post with given post ID not found")
            serializer = CommentSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(status=400, data=serializer.errors)
            data = serializer.validated_data
            author_uuid = data["author"]["url"].split("/")[-1]
            author = Author.objects.get(uuid = author_uuid)
            Comment.objects.create(
                post = post,
                author = author,
                body = data["body"],
                date_added = data["date_added"],
                content_type = data["content_type"]
                )
            return Response(status=200, data = serializer.validated_data)

@swagger_auto_schema(
    tags=['likes', 'remote'],
    method='get',
    operation_description="Retrieves the list of likes for a post.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
        ],
    responses={
        200: LikeResponseSerializer,
        404: openapi.Response("Post with given post ID not found"),
    }
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def list_of_likes(request, uuid, post_id):
    author = get_object_or_404(Author, uuid = uuid)
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return Response(status=404, data="Post with given post ID not found")
    liked_post = LikePost.objects.filter(post = post)
    base_url = request.build_absolute_uri('/').rstrip('/')
    likes_list = []
    for p in liked_post:
        author_p = Author.objects.get(uuid = p.author.uuid)
        data = return_author_format(request=request, author=author_p)
        likes_list.append({"summary": f"{p.author} Likes your post",         
                "type": "Like",
                "author": data,
                "object":base_url+'/authors/'+uuid+'/posts/'+post_id})
    response = {"type": "likes", "items": likes_list}
    return Response(response,status=200)

@swagger_auto_schema(
    tags=['likes', 'remote'],
    method='get',
    operation_description="Retrieves the list of likes for the provided comment on a post.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
            openapi.Parameter('comment_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the comment."),
        ],
    responses={
        200: LikeResponseSerializer,
        404: openapi.Response("Comment with given ID not found"),
    }
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def comment_likes(request, uuid, post_id, comment_id):
    author = get_object_or_404(Author, uuid=uuid)
    post = get_object_or_404(Post, id=post_id)
    try:
        comment = Comment.objects.get(id=comment_id, post=post)
    except Comment.DoesNotExist:
        return Response(status=404, data="Comment with given ID not found")
    like_comment = LikeComment.objects.filter(comment = comment).values()
    base_url = request.build_absolute_uri('/').rstrip('/')
    likes_list = []
    for p in like_comment:
        author_p = User.objects.get(id = p['user_id'])
        author_p = Author.objects.get(user = author_p)
        data = return_author_format(request=request, author=author_p)
        likes_list.append({"summary": f"{author_p.user.get_username()} Likes your comment",         
                "type": "Like",
                "author": data,
                "object":base_url+'/authors/'+author_p.uuid+'/posts/'+post_id+'/comments/'+comment_id})
    response = {"type": "likes", "items": likes_list}
    return Response(response,status=200)

@swagger_auto_schema(
    tags=['liked', 'remote'],
    method='get',
    operation_description="Retrieves the public things liked by the author.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
        ],
    responses={
        200: LikedResponseSerializer,
        404: openapi.Response("Author not found with the provided UUID."),
    }
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def liked(request,uuid):
    try:
        author = Author.objects.get(uuid=uuid)
    except Author.DoesNotExist:
        return Response("Author not found with the provided UUID.", status=404)
    liked_posts = LikePost.objects.filter(author = author)
    data = return_author_format(request=request, author=author)
    items_list = []
    for liked_post in liked_posts:
        post = liked_post.post
        if post.visibility == 'PUBLIC':
            items_list.append({"summary": liked_post.author.user.get_username() + " Likes your post", 
                               "type": "Like",
                               "author": data,
                               "object": data["id"] + "/posts/" + str(post.id)
                               
                               })
    response = {"type": "liked", "items": items_list} 
    return Response(response,status=200)

@swagger_auto_schema(
    tags=['posts', 'remote'],
    method='get',
    operation_description="Retrieves the public posts with given post ID.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
        ],
    responses={
        200: PostSerializer,
        404: openapi.Response("Post not found"),
    }
)
@swagger_auto_schema(
    tags=['posts'],
    methods=['put'],
    operation_description="Updates the post with given post ID.",
    request_body=PostSerializer
)
@swagger_auto_schema(
    tags=['posts'],
    methods=['delete'],
    operation_description="Removes the post with given post ID.",
    request_body=PostSerializer
)
@api_view(['GET', 'DELETE', 'PUT'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def single_post(request, author_id, post_id):
    # Get the public post whose id is post_id
    if request.method == "GET":
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(status=404, data="Post not found")
        author = get_object_or_404(Author, uuid=author_id)

        if author != post.author:
            return Response(status=404, data="Post not found")

        # Check if the user is friends with the author
        try:
            user = User.objects.get(username=request.user)
            requester = Author.objects.get(user = user)
            is_friend = Follower.objects.filter(author=requester, follower=author, is_friend=True).count() > 0
        except User.DoesNotExist:
            # Authenticated using node
            requester = Node.objects.get(username = request.user.username)
            is_friend = False
        
        if post.visibility == "FRIENDS":
            # User must be authenticated as a friend to see friend only posts (or the user must be the author of the post)
            if is_friend or author == requester:
                serializer = PostSerializer(post, context={"request": request})
                if post.content_type == "text/markdown":
                    return Response(status=200, data=serializer.data)
                elif post.content_type == "application/base64":
                    headers = {'User-Agent': 'socialdistribution/0.1'}
                    response = requests.get(post.image_url, headers=headers)
                    if response.status_code == 200:
                        image_content = base64.b64encode(response.content)#.decode('utf-8')
                        data = serializer.data
                        data['content'] = image_content
                        return Response(status=200, data=data)
            else:
                return Response(status=403, data="You do not have access to this post")
            
        elif post.visibility == "UNLISTED":
            # Assumption: Unlisted posts should not be returned by endpoint
            return Response(status=403, data="You do not have access to this post")

        else:
            # Public posts are visible to everyone
            serializer = PostSerializer(post, context={"request": request})
            if post.content_type == "text/markdown":
                    return Response(status=200, data=serializer.data)
            elif post.content_type == "application/base64":
                    headers = {'User-Agent': 'socialdistribution/0.1'}
                    response = requests.get(post.image_url, headers=headers)
                    if response.status_code == 200:
                        image_content = base64.b64encode(response.content)#.decode('utf-8')
                        data = serializer.data
                        data['content'] = image_content
                        return Response(status=200, data=data)
        
    # Remove the post whose id is post_id
    elif request.method == "DELETE":
        post_to_remove = get_object_or_404(Post, id=post_id)
        author = get_object_or_404(Author, uuid=author_id)
        try:
            user = User.objects.get(username=request.user)
            requester = Author.objects.get(user = user)
        except User.DoesNotExist:
            return Response(status=403, data="You do not have access to this post")
        
        if requester == author and author == post_to_remove.author:
            post_to_remove.delete()
            return Response(status=204)
        else:
            return Response(status=403, data="You do not have access to this post")

    # Update a post where its id is post_id
    elif request.method == "PUT":
        try:
            post = get_object_or_404(Post, id=post_id)
            author = get_object_or_404(Author, uuid=author_id)
            try:
                user = User.objects.get(username=request.user)
                requester = Author.objects.get(user = user)
            except User.DoesNotExist:
                return Response(status=403, data="You do not have access to this post")
            
            if requester == author and author == post.author:
                serializer = PostSerializer(post, data=request.data, partial=True, context={"request": request})
                if serializer.is_valid():
                    serializer.update(post, serializer.validated_data)
                    return Response(serializer.data)
                return Response(status=400, data=serializer.errors)
            else:
                return Response(status=403, data="You do not have access to this post")
        except json.JSONDecodeError:
            return Response(status=400, data="Invalid JSON data")

    else:
        return Response(status=405, data="Only GET, DELETE, and PUT requests allowed") # Method not allowed

@swagger_auto_schema(
    tags=['posts', 'remote'],
    method='get',
    operation_description="Retrieves all public posts (paginated).",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page number"),
            openapi.Parameter('size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Number of posts per page"),
        ],
    responses={
        200: PostsResponseSerializer,
        404: openapi.Response("Author not found with the provided UUID."),
    }
)
@swagger_auto_schema(
    tags=['posts'],
    method='post',
    operation_description="Creates a new post object.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author.")
        ]
)
@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, NodeAuthentication])
def posts(request, author_id):
    if request.method == "GET":
        try:
            author = Author.objects.get(uuid=author_id)
        except Author.DoesNotExist:
            return Response("Author not found with the provided UUID.", status=404)
        # Check if the user is friends with the author
        try:
            user = User.objects.get(username=request.user)
            requester = Author.objects.get(user = user)
            is_friend = Follower.objects.filter(author=requester, follower=author, is_friend=True).count() > 0
        except User.DoesNotExist:
            # Authenticated using node
            requester = Node.objects.get(username = request.user.username)
            is_friend = False

        try:
            page = request.GET.get("page")
            page_size = request.GET.get("size")
            if author == requester:
                posts = Post.objects.filter(author=author.id)
            elif is_friend:
                posts = Post.objects.filter(author=author.id, visibility="PUBLIC") | Post.objects.filter(author=author.id, visibility="FRIENDS")
            else:
                posts = Post.objects.filter(author=author.id, visibility="PUBLIC")

            # Paginate posts if page and size query parameters are given
            page = request.GET.get("page")
            page_size = request.GET.get("size")
            if page and page_size:
                paginator = PageNumberPagination()
                paginator.page_size = page_size
                posts = paginator.paginate_queryset(posts, request)
            serializer = PostSerializer(posts, many=True, context={"request": request})
            for post in posts:
                if post.content_type == "application/base64":
                    headers = {'User-Agent': 'socialdistribution/0.1'}
                    response = requests.get(post.image_url, headers=headers)
                    if response.status_code == 200:
                        image_content = base64.b64encode(response.content)#.decode('utf-8')
                        for post_data in serializer.data:
                            post_id = post_data["id"].split("/")[-1]
                            if post_data["contentType"] == "application/base64" and post_id == str(post.id):
                                post_data["content"] = image_content
            response = {"type": "posts", "items": serializer.data}
        except Post.DoesNotExist:
            response = {"type": "posts", "items": []}
        return Response(response)

    # Create a new post but generate a new id
    elif request.method == "POST":
        author = get_object_or_404(Author, uuid = author_id)
        try:
            user = User.objects.get(username=request.user)
            requester = Author.objects.get(user = user)
        except User.DoesNotExist:
            return Response(status=403, data="Must be authenticated as a local author to create posts")

        if requester == author:
            try:
                body = request.data
                title = body['title']
                description = body['description']
                content_type = body['contentType']
                content = body['content']
                visibility = body['visibility']
                if 'image_url' in body:
                    image_url = body['image_url']
                    new_post = Post(
                            title = title,
                            description = description,
                            content_type = content_type,
                            content_markdown = content,
                            author = author,
                            created_at = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
                            visibility = visibility,
                            image_url = image_url)
                else:
                    new_post = Post(
                            title = title,
                            description = description,
                            content_type = content_type,
                            content_markdown = content,
                            author = author,
                            created_at = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
                            visibility=visibility)
                new_post.save()
                base_url = request.build_absolute_uri('/')
                new_post.origin = f'{base_url}/authors/{author.uuid}/posts/{new_post.id}'
                new_post.copy_of_original_id = new_post.id
                new_post.save()
                return Response(status=201, data="Post with id %d added" % new_post.id)
            
            except json.JSONDecodeError:
                return Response(status=400, data="Invalid JSON data")
        else:
            return Response(status=400, data="Must be authenticated as author specified in url")
    else:
        return Response(status=405, data="Only GET and POST requests allowed") # Method not allowed

@swagger_auto_schema(
    method='get',
    tags=['posts', 'remote'],
    operation_description="Retrieves the binary of the image for the post.",
    manual_parameters=[
            openapi.Parameter('author_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author."),
            openapi.Parameter('post_id', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the post."),
        ],
    responses={
        200: ImagePostResponseSerializer,
        404: openapi.Response("No image found for requested post")
    }
)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, NodeAuthentication]) 
def image_post(request, author_id, post_id):
    # Get the public post converted to binary as an image
    if request.method == 'GET':
        post = get_object_or_404(Post, id=post_id)

        if not post.image_url:
            return Response(status=404, data="No image found for requested post")
        else:
            headers = {'User-Agent': 'socialdistribution/0.1'}
            response = requests.get(post.image_url, headers=headers)

            serializer = PostSerializer(post, context={"request": request})
            post_json = serializer.data

            if post.image_url.split('.')[-1] == "jpeg" or post.image_url.split('.')[-1] == "jpg":
                content_type = "image/jpeg;base64"
            elif post.image_url.split('.')[-1] == "png":
                content_type = "image/png;base64"

            if response.status_code == 200:
                image = base64.b64encode(response.content)
                post_json['content'] = image
                post_json['contentType'] = content_type
                return Response(status=200, data=post_json)
            else:
                return Response(status=response.status_code, data={"error": "Failed to retrieve image"})
            
    else:
        return Response(status=405, data="Only GET requests allowed") # Method not allowed

@swagger_auto_schema(
    method='get',
    tags=['inbox'],
    operation_description="Get a list of all recent posts sent to an author's inbox.",
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page number"),
        openapi.Parameter('size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Number of inbox's per page"),
        openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author.")
        ]
)
@swagger_auto_schema(
    method='post',
    tags=['inbox', 'remote'],
    operation_description="Send a post to an author's inbox.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author.")
        ]
)
@swagger_auto_schema(
    method='delete',
    tags=['inbox'],
    operation_description="Clear an author's inbox.",
    manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, type=openapi.TYPE_STRING, description="The unique identifier for the author.")
        ]
)
@api_view(['GET', 'POST', 'DELETE'])
@authentication_classes([SessionAuthentication, NodeAuthentication]) 
def inbox(request, uuid):
    if request.method == "POST":
        notification = request.data 
        notification_type = notification.get('type')
        if notification_type == 'Like':
            # Handle like objects sent to inbox
            try:
                # Get author whose inbox is being accessed
                user_id = uuid.split('/')[-1]
                author = Author.objects.get(uuid = user_id)
                post_id = notification['object'].split('/')[-1]
                try:
                    post = Post.objects.get(id = post_id)

                except Post.DoesNotExist:
                    # Like object must be associated with an existing post
                    return Response(status=400, data="Post with given id not found")
                
                try:
                    # Get author who liked the post
                    action_user_id = notification['author']['id'].split('/')[-1]
                    action_user = Author.objects.get(uuid = action_user_id)
                except Author.DoesNotExist:
                    return Response(status=400, data="Author with given id not found")
                
                try:
                    like = LikePost.objects.get(post = post, author = action_user)
                    host_name = request.query_params.get('request_host', None)
                    if host_name and config['enjoyers-host'] not in host_name:
                        # Author unliked the post
                        like.delete()
                        post.no_of_likes = post.no_of_likes - 1
                        post.save()
                    
                except LikePost.DoesNotExist:
                    # Author liked the post
                    new_like = LikePost.objects.create(post = post, author = action_user)
                    new_like.save()
                    post.no_of_likes = post.no_of_likes + 1
                    post.save()
                    
                    # Create notification only if the post was liked
                    Notification.objects.create(
                        post=post,
                        action_user=action_user,
                        receiver_user=post.author,  
                        action_type='Like',
                        timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
                        notification_message = f"{action_user} liked your post"
                    )

                # Send to remote server if necessary
                if request.build_absolute_uri('/') != author.host:
                    host_name = uuid.split("/authors/")[0] + '/'
                    send_to_node(host_name, uuid, request.data)

            except Author.DoesNotExist:
                create_author(notification['author']) # create author on local server
                host_name = uuid.split("/authors/")[0] + '/'    
                send_to_node(host_name, uuid, request.data)

            return Response(status=201)

        elif notification_type.lower() == "follow":
            # Handle follow object send to inbox
            try:
                # Handle other nodes accordingly
                if "nexapulse" in notification['actor']['host']:
                    receiver_user_id = notification['object']['id']
                    author_id = notification['actor']['id']
                else:
                    receiver_user_id = notification['object']['id'].split('/')[-1]
                    author_id = notification['actor']['id'].split('/')[-1]

                receiver_user = Author.objects.get(uuid = receiver_user_id)
                try:
                    action_user = Author.objects.get(uuid = author_id)
                except Author.DoesNotExist:
                    if request.build_absolute_uri('/') == notification['actor']['host']:
                        # Author not found on local server
                        return Response(status=400, data="Author with given id not found")
                    else:
                        # Replica of remote author needs to be created
                        create_author(notification['actor'])
                        
                try:
                    follower_object = Follower.objects.get(author = receiver_user, follower = action_user, request_accepted=True)

                    # Follow object exists (author unfollowed remotely)
                    follower_object.delete()
                    # Change friend status to false if foreign author follows author
                    reverse_follower = Follower.objects.filter(author=action_user, follower=receiver_user, request_accepted=True).first()
                    if reverse_follower:
                        reverse_follower.is_friend = False
                        reverse_follower.save()

                except Follower.DoesNotExist:
                    try:
                        follower_object = Follower.objects.get(author=receiver_user, follower=action_user)
                        # Accepted or rejected
                        # Retrieve posts if user follows remote author
                        try:
                            node = Node.objects.get(host = receiver_user.host)
                            authorization = f"{node.username}:{node.password}"
                            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
                            if node.api_prefixed:
                                if "nexapulse" in node.host:
                                    url = receiver_user.url.split('/authors/')
                                    following_url = f'{url[0]}/api/authors/{url[1]}/followers/{action_user.uuid}'
                                else:
                                    url = receiver_user.url.split('/authors/')
                                    following_url = f'{url[0]}/api/authors/{url[1]}/followers/{action_user.url}'
                            else:
                                following_url = f'{receiver_user.url}/followers/{action_user.url}'
                            # Ask server (local or remote) if the current user follows the person we received a request from
                            is_following_response = requests.get(following_url, headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"}) # this endpoint seems slow

                            if is_following_response.status_code == 404 or is_following_response.status_code == 400:
                                # Follow request rejected
                                follower_object.delete()

                            elif is_following_response.status_code == 200:
                                # Follow request accepted
                                follower_object.request_accepted = True
                                try:
                                    reverse_follower_object = Follower.objects.get(author=action_user, follower=receiver_user, request_accepted=True)
                                    # In this case, follower relationship is bi-directional
                                    reverse_follower_object.is_friend = True
                                    reverse_follower_object.save()
                                    follower_object.is_friend = True

                                except Follower.DoesNotExist:
                                    pass

                                finally:
                                    follower_object.save()

                        except Node.DoesNotExist:
                            # Ignore if node does not exist
                            pass
                    except Follower.DoesNotExist:
                        # Follow object exists in remote node, but not local server. Create the Follower object locally
                        Follower.objects.create(author=receiver_user, follower=action_user)

                # Send to remote server if necessary
                if request.build_absolute_uri('/') != receiver_user.host:
                    host_name = uuid.split("/authors/")[0] + '/'
                    send_to_node(host_name, uuid, request.data)

            except Author.DoesNotExist:
                create_author(notification['object']) # create author on local server
                host_name = uuid.split("/authors/")[0] + '/'
                send_to_node(host_name, uuid, request.data)
            
            return Response(status=201, data={"receiver_id": receiver_user_id})

        elif notification_type == "post":
            # Handle post object send to inbox
            try:
                user_id = uuid.split('/')[-1]
                author = Author.objects.get(uuid = user_id)
                post_id = notification['id'].split('/')[-1]
                try:
                    post = Post.objects.get(id = post_id)
                    host_name = notification['author']['host']
                    # Post found, the post was edited remotely
                    if "social-dist" in post.author.host or "nexapulse" in post.author.host:
                        # Edit remotely only implemented between our instances and nexapulse
                        post_author = post.author
                        post.title = notification['title']
                        post.origin = notification['origin']
                        post.description = notification['description']
                        post.content_type = notification['contentType']
                        post.content_markdown = notification['content']
                        post.created_at = notification['published']
                        post.visibility = notification['visibility'].upper()
                        post.save()

                        # Check if there is an image_ref (used by nexapulse)
                        if 'image_ref' in notification and notification['image_ref'] != None and notification['image_ref'] != "None":
                            try:
                                # Get new image url
                                host_name = request.query_params.get('request_host', None)
                                node = Node.objects.get(host = host_name, is_active = True)
                                authorization = f"{node.username}:{node.password}"
                                headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
                                image_response = requests.get(f"{notification['author']['host']}api/authors/{notification['author']['id']}/posts/{notification['id']}/image", headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})
                                
                                if image_response.status_code == 200:
                                    # Encode image retrieved in base64
                                    image_post_json = json.loads(image_response.content)
                                    base_64_content = image_post_json['content']

                                    with tempfile.NamedTemporaryFile(delete=False) as temp:
                                        temp.write(b64decode(base_64_content))
                                    temp_path = temp.name
                                    imgur = pyimgur.Imgur('c431432680ddf1e')
                                    try:
                                        # Update image_url
                                        uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                                        image_url =  uploaded_image.link
                                        post.image_url = image_url
                                        post.save()
                                    except KeyError:
                                        print("Error uploading image to Imgur")
                                        
                            except Node.DoesNotExist:
                                    return Response(status=400, data="Node does not exist")
                        
                        else:
                            # Image post from one of our instances
                            image_url = get_image(notification, post_id)
                            # Edit the image
                            post.image_url = image_url
                            post.save()
                        

                except Post.DoesNotExist:
                    # Post does not exist, need to create post
                    author_id = notification['author']['id'].split('/')[-1]
                    try:
                        post_author = Author.objects.get(uuid = author_id)

                    except Author.DoesNotExist:
                        post_author = create_author(notification['author']) # create author on local server
                    
                    if notification['contentType'] in ('text/markdown','text/plain'):
                        # Check for Nexapulse image_ref
                        if 'image_ref' in notification and notification['image_ref'] != None and notification['image_ref'] != "None":
                            # Handle image retrieval from Nexapulse
                            try:
                                host_name = request.query_params.get('request_host', None)
                                if host_name and host_name[-1] != '/':
                                    # Post object from team nexapulse (add / if necessary)
                                    host_name = host_name + '/' # add / to end of host_name
                                elif host_name:
                                    pass
                                else:
                                    # Post object from team enjoyers
                                    host_name = notification['author']['host']
                                
                                node = Node.objects.get(host = host_name, is_active = True)
                                authorization = f"{node.username}:{node.password}"
                                headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
                                
                                try:
                                    author_to_query = notification['shared_user']
                                except KeyError:
                                    author_to_query = notification['author']
                                
                                author_to_query_id = notification['author']['id'].split('/')[-1]
                                if node.api_prefixed:
                                    if config['nexapulse-host'] in author_to_query['host']:
                                        image_response = requests.get(f"{author_to_query['host']}api/authors/{author_to_query_id}/posts/{notification['id']}/image/", headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})
                                    else:
                                        image_response = requests.get(f"{author_to_query['host']}api/authors/{author_to_query_id}/posts/{notification['id']}/image", headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})
                                else:
                                    image_response = requests.get(f"{author_to_query['host']}authors/{author_to_query_id}/posts/{notification['image_ref']}/image")
                                if image_response.status_code == 200:
                                    image_post_json = json.loads(image_response.content)
                                    base_64_content = image_post_json['content']

                                    if config['enjoyers-host'] in host_name:
                                        # Remove data:image/jpeg;base64, prefix in content field
                                        base_64_content = base_64_content.split('data:image/jpeg;base64,')[-1]
                                    
                                    # Decode base64 content
                                    with tempfile.NamedTemporaryFile(delete=False) as temp:
                                        temp.write(b64decode(base_64_content))
                                    temp_path = temp.name
                                    imgur = pyimgur.Imgur('c431432680ddf1e')
                                    try:
                                        uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                                        image_url =  uploaded_image.link
                                    except KeyError:
                                        print("Error uploading image to Imgur")

                                    if config['enjoyers-host'] in host_name:
                                        content = notification['content']
                                    else:
                                        content = ''

                                    post_id = notification['id'].split('/')[-1]
                                    post = Post.objects.create(
                                        id = post_id,
                                        title = notification['title'],
                                        origin = '', # image_post_json['origin']
                                        description = notification['description'],
                                        content_type = image_post_json['contentType'],
                                        content_markdown = content,
                                        image_url = image_url,
                                        author = post_author,
                                        created_at = notification['published'],
                                        visibility = notification['visibility'].upper()
                                    )
                                try:
                                    post.origin = image_post_json['origin']
                                    post.save()
                                except KeyError:
                                    print("Post has no origin")
                            except Node.DoesNotExist:
                                return Response(status=400, data="Node does not exist")
                            
                        else:
                            # Create post without image
                            host_name = notification['author']['host']
                            if "nexapulse" in host_name:
                                post_id = notification['id']

                            post = Post.objects.create(
                                id = post_id,
                                title = notification['title'],
                                origin = notification['origin'],
                                description = notification['description'],
                                content_type = notification['contentType'],
                                content_markdown = notification['content'],
                                author = post_author,
                                created_at = notification['published'],
                                visibility = notification['visibility'].upper()
                            )

                    elif notification['contentType'] == 'image/jpeg':
                        # Ignore jpeg posts
                        post = None
                        host_name = notification['author']['host']
                                
                    else:
                        # Create Image post
                        host_name = notification['author']['host']
                        if config['syntax-host'] in host_name:
                            # Upload base64 image from content field to Imgur
                            base_64_content = notification['content']
                            with tempfile.NamedTemporaryFile(delete=False) as temp:
                                temp.write(b64decode(base_64_content))
                            temp_path = temp.name
                            # Upload to Imgur
                            imgur = pyimgur.Imgur('c431432680ddf1e')
                            try:
                                uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                                image_url =  uploaded_image.link
                            except KeyError:
                                print("Error uploading image to Imgur")
                        else:
                            image_url = get_image(notification, post_id)
                        post = Post.objects.create(
                            id = post_id,
                            title = notification['title'],
                            origin = notification['origin'],
                            description = notification['description'],
                            content_type = 'application/base64',
                            content_markdown = '',
                            image_url = image_url,
                            author = post_author,
                            created_at = notification['published'],
                            visibility = notification['visibility'].upper()
                        )
                
                    # Create notification displayed on UI
                    if post:
                        Notification.objects.create(
                            post=post,
                            action_user=post_author,
                            receiver_user=author,  
                            action_type='post',
                            timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
                            notification_message = f"{post_author} created a new post"
                        )

                try:
                    # Add shared user, title, body fields if the post is a shared post

                    # Get or create the author of the shared post
                    try:
                        shared_post_author_id = notification['shared_user']['id'].split('/')[-1]
                        shared_post_author = Author.objects.get(uuid = shared_post_author_id)
                    except Author.DoesNotExist:
                        shared_post_author = create_author(notification['shared_user']) # create author on local server
                    
                    post.shared_user = shared_post_author

                    if "nexapulse" in post.shared_user.host:
                        post.content_markdown = notification['originalContent']

                    post.shared_body = notification['shared_body']

                    message = f"{post.shared_user.user.username} shared a post"
                    try:
                        post.shared_title = notification['shared_title']
                    except KeyError:
                        # Set the title to "{shared_user} shared a post" if the shared post has no title
                        post.shared_title = message

                    # Get image from original post if necessary
                    try:
                        post.copy_of_original_id = notification['copy_of_original_id'] # get id of original post
                        if config['enjoyers-host'] in host_name:
                            image_url = get_image(notification, notification['image_ref'])
                        else:
                            image_url = get_image(notification, notification['copy_of_original_id'])
                        post.image_url = image_url

                    except KeyError:
                        pass
                    post.save()

                except KeyError:
                    # Post was created (not shared)
                    if post:
                        post.copy_of_original_id = post_id
                        post.save()
                        message = f"{post.author.user.username} created a new post"

                # Send to remote server if necessary
                if request.build_absolute_uri('/') != author.host:
                    host_name = uuid.split("/authors/")[0] + '/'
                    send_to_node(host_name, uuid, request.data)

            except Author.DoesNotExist:
                return Response(status=404, data="Author with given uuid does not exist")

            
            return Response(status=201)

        elif notification_type == "comment":
            # Handle comment object send to inbox
            try:
                user_id = uuid.split('/')[-1]
                author = Author.objects.get(uuid = user_id)
                if "nexapulse" in notification['author']['host']:
                    post_id = notification['postId']
                    comment_id = notification['id']
                else:
                    post_id = notification['id'].split('/')[6]
                    comment_id = notification['id'].split('/')[-1]
                
                try:
                    post = Post.objects.get(id = post_id)
                    
                except Post.DoesNotExist:
                    return Response(status=400, data="Post with given id not found")
                
                try:
                    if "nexapulse" in notification['author']['host']:
                        action_user_id = notification['author']['id']
                    else:
                        action_user_id = notification['author']['id'].split('/')[-1]
                    action_user = Author.objects.get(uuid = action_user_id)
                except Author.DoesNotExist:
                    return Response(status=400, data="Author with given id not found")
                
                try:
                    Comment.objects.get(id = comment_id)

                except Comment.DoesNotExist:
                    Comment.objects.create(
                        id = comment_id,
                        post = post,
                        author = action_user,
                        body = notification['comment'],
                        content_type = notification['contentType']
                    )
                # Create notification displayed on UI
                Notification.objects.create(
                    post=post,
                    action_user=action_user,
                    receiver_user=author,  
                    action_type='comment',
                    timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
                    notification_message = f"{action_user} commented on your post"
                )

                # Send to remote server if necessary
                if request.build_absolute_uri('/') != author.host:
                    host_name = uuid.split("/authors/")[0] + '/'
                    send_to_node(host_name, uuid, request.data)

            except Author.DoesNotExist:
                create_author(notification['author']) # create author on local server
                host_name = uuid.split("/authors/")[0] + '/'    
                send_to_node(host_name, uuid, request.data)

            return Response(status=201)
        
        elif notification_type == "Approve Follow":
            # Notification type used by team syntax to accept follow requests
            receiver_user_id = notification['object']['id'].split('/')[-1]
            author_id = notification['actor']['id'].split('/')[-1]

            receiver_user = Author.objects.get(uuid = receiver_user_id)
            try:
                action_user = Author.objects.get(uuid = author_id)
            except Author.DoesNotExist:
                if request.build_absolute_uri('/') == notification['actor']['host']:
                    # Author not found on local server
                    return Response(status=400, data="Author with given id not found")
                else:
                    # Replica of remote author needs to be created
                    create_author(notification['actor'])
            
            try:
                follower_object = Follower.objects.get(author=receiver_user, follower=action_user)
                follower_object.request_accepted = True
                follower_object.save()

                # Update is_friend if necessary
                try:
                    reverse_follower_object = Follower.objects.get(author=action_user, follower=receiver_user, request_accepted=True)
                    # In this case, follower relationship is bi-directional
                    reverse_follower_object.is_friend = True
                    reverse_follower_object.save()
                    follower_object.is_friend = True
                    follower_object.save()

                except Follower.DoesNotExist:
                    pass

            except Follower.DoesNotExist:
                Follower.objects.create(author=receiver_user, follower=action_user, request_accepted=True)

            return Response(status=201)
        
        elif notification_type == "Deny Follow" or notification_type == "Unfollow":
            # Notification type used by team syntax to accept follow requests
            receiver_user_id = notification['object']['id'].split('/')[-1]
            author_id = notification['actor']['id'].split('/')[-1]

            receiver_user = Author.objects.get(uuid = receiver_user_id)
            try:
                action_user = Author.objects.get(uuid = author_id)
            except Author.DoesNotExist:
                if request.build_absolute_uri('/') == notification['actor']['host']:
                    # Author not found on local server
                    return Response(status=400, data="Author with given id not found")
                else:
                    # Replica of remote author needs to be created
                    create_author(notification['actor'])
            try:
                follower_object = Follower.objects.get(author=receiver_user, follower=action_user)
                follower_object.delete()
                return Response(status=204)

            except Follower.DoesNotExist:
                return Response(status=404)
        
        else:
            return Response(status=400, data={'error': 'Unsupported notification type'})
        
    elif request.method == "GET":
        # Get the author object
        author = get_object_or_404(Author, uuid=uuid)

        # Retrieve notifications for the authenticated user
        notifications = Notification.objects.filter(receiver_user=author).order_by("-timestamp")

        page = request.GET.get("page")
        page_size = request.GET.get("size")
        if page and page_size:
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            notifications = paginator.paginate_queryset(notifications, request)

        else:
            return Response(status=400, data={'error': 'Must include page and size query parameters in URL'})

        # Serialize notifications to JSON format
        inbox_data = []
        for notification in notifications:
            if notification.action_type == 'post':
                # Show post that was created/edited
                post = notification.post
                serializer = PostSerializer(post, context={"request": request})
                inbox_data.append(serializer.data)
            elif notification.action_type == 'follow':
                # Display follow object
                follower = notification.action_user
                inbox_data.append({
                    "type": "Follow",
                    "summary": "{} wants to follow {}".format(follower, author),
                    "actor": return_author_format(request, follower),
                    "object": return_author_format(request, author)
                })
            elif notification.action_type == 'Like':
                # Show post that was liked
                post = notification.post
                serializer = PostSerializer(post, context={"request": request})
                inbox_data.append(serializer.data)

            elif notification.action_type == 'comment':
                # Show post with new comment
                post = notification.post
                serializer = PostSerializer(post, context={"request": request})
                inbox_data.append(serializer.data)
        
        return Response(status=200, data = {"type":"inbox", 
                             "author": request.build_absolute_uri('/') + "authors/" + author.uuid ,
                             'inbox': inbox_data})
    
    elif request.method == "DELETE":
        # Clear user's inbox
        author = get_object_or_404(Author, uuid=uuid)
        Notification.objects.filter(receiver_user=author).delete()
        return Response(status=204, data="Inbox cleared")

    else:
        return HttpResponseNotAllowed(['GET', 'POST'])

def return_author_format(request, author):
    serializer = AuthorSerializer(author, context={"request": request})
    return serializer.data

def create_author(data):
    full_list = data['id'].split("/")
    foreign_author_uuid = full_list[-1]
    foreign_author_host = data["host"]
    foreign_author_url = data["url"]
    foreign_author_profileImage = data["profileImage"]
    foreign_author_github = data["github"]
    try:
        foreign_user_object = User.objects.get(username=data['displayName'])
    except:
        foreign_user_object = User.objects.create_user(username=data['displayName'], email="sameemail@gmail.com",password="sameemail", is_active=False)
        foreign_user_object.save()
    foreign_author = Author.objects.create(user=foreign_user_object,uuid = foreign_author_uuid, host=foreign_author_host, url =foreign_author_url, 
                                           profile_image = foreign_author_profileImage, github = foreign_author_github
                                           )
    foreign_author.save()
    return foreign_author

def get_image(notification, post_id):
    # Get image url from content of image post
    try:
        # Add / to end of host if necessary
        if notification['author']['host'][-1] != '/':
            host = notification['author']['host'] + '/'
        else:
            host = notification['author']['host']

        node = Node.objects.get(host = host, is_active = True)
        author_id = notification['author']['id'].split('/')[-1]
        if config['enjoyers-host'] in node.host:
            image_response = requests.get(f"{node.host}authors/{author_id}/posts/{post_id}/image")
        else:
            authorization = f"{node.username}:{node.password}"
            headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}
            image_response = requests.get(f"{node.host}authors/{author_id}/posts/{post_id}/image", headers=headers)
        if image_response.status_code == 200:
            # Decode base64 content
            image_post_json = json.loads(image_response.content)
            base_64_content = image_post_json['content']
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp.write(b64decode(base_64_content))
            temp_path = temp.name
            # Upload to Imgur
            imgur = pyimgur.Imgur('c431432680ddf1e')
            try:
                uploaded_image = imgur.upload_image(path=temp_path, title="Uploaded with PyImgur")
                image_url =  uploaded_image.link
            except KeyError:
                print("Error uploading image to Imgur")
            
            return image_url
        else:
            # Post has no image url (return empty string)
            return ''
    except Node.DoesNotExist:
            return Response(status=400, data="Node does not exist")

def send_to_node(host_name, uuid, data):
    try:
        # Ensure the host name has a / at the end
        if host_name[-1] != '/':
            host_name = host_name + '/'

        # Determine if author is a remote author
        node = Node.objects.get(host = host_name, is_active = True)
        authorization = f"{node.username}:{node.password}"
        headers = {'Authorization': f'Basic {base64.b64encode(authorization.encode("utf-8")).decode("utf-8")}'}

        if config['nexapulse-host'] in node.host:
            # Can't send to authors that don't exist on nexapulse
            url = uuid.split('/authors/')
            request_url = f'{url[0]}/api/authors/{url[1]}'
            response = requests.get(request_url, headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})
            if response.status_code != 200:
                return Response(status = 400, data="Author does not exist on nexapulse")

        # Team syntax has an exception where they don't prefix their inbox endpoint with api/
        if node.api_prefixed and config['syntax-host'] not in host_name:
            url = uuid.split('/authors/')
            request_url = f'{url[0]}/api/authors/{url[1]}/inbox'
        else:
            request_url = f"{uuid}/inbox"

        if config['enjoyers-host'] in host_name:
            # Team enjoyers uses different request headers
            response = requests.post(request_url, json=data, headers={"username": node.username, "password": node.password, "url": config['host']})
        else:
            # Send to remote author's inbox
            response = requests.post(request_url, json=data, headers=headers, params={"request_host": "https://social-dist1-e4a42d3ec395.herokuapp.com/"})

        if response.status_code == 201:
            return Response(status = 201)
        else:
            return Response(status = 400, data="Data formatted incorrectly")

    except Node.DoesNotExist:
        return Response(status=404, data="Author not found")
