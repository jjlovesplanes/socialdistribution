from django import forms
from .models import Post, Comment
from django.contrib.auth.models import User

class PostForm(forms.ModelForm):
    image = forms.FileField(required=False)
    class Meta:
        model = Post
        fields = ['title', 'content_markdown', 'visibility', 'image']
    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean() # clean() returns the cleaned data, which is a dictionary of the form data

        return cleaned_data

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('body',)

        widgets = {
            'body': forms.Textarea(attrs={'class': 'form-control'})
        }