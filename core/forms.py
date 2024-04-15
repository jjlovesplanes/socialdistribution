from django import forms
from authors.models import Author

class AuthorForm(forms.ModelForm):
    image = forms.FileField(required=False)
    
    class Meta:
        model = Author
        fields = ['github', 'image']

        labels = {
            'github': 'GitHub Link'
        }

class ShareForm(forms.Form):

    shared_title = forms.CharField(
        label = '',
        widget = forms.Textarea(attrs = {'rows': '1',
                                         'placeholder': 'Title...'})
    )

    shared_body = forms.CharField(
        label = '',
        widget = forms.Textarea(attrs = {'rows': '3',
                                         'placeholder': 'Say Something...'})
    )