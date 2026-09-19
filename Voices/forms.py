# forms.py
from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import password_validation
from datetime import date

try:
    from django_summernote.widgets import SummernoteWidget
except Exception:
    SummernoteWidget = None

from .models import Contact, GBVReport, Article, Blog, Story, Resource, Idea, SupportFeedback, UserProfile


# Validators
phone_validator = RegexValidator(
    regex=r'^[\d\s\+]+$',
    message='Phone number should only contain numbers, spaces, and + symbol.'
)

name_validator = RegexValidator(
    regex=r"^[a-zA-Z\s\-']+$",
    message='Name should only contain letters, spaces, hyphens, and apostrophes.'
)


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject', 'required': True}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Your Message', 'rows': 5, 'style': 'height: 150px', 'required': True}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Pre-fill if user is authenticated
        if user and user.is_authenticated:
            self.fields['name'].initial = user.get_full_name() or user.username
            self.fields['email'].initial = user.email
            self.fields['name'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['readonly'] = True
        else:
            self.fields['name'].required = True
            self.fields['email'].required = True

    def clean_name(self):
        """Validate name format."""
        name = self.cleaned_data.get('name')
        if name:
            name_validator(name)
        return name


class GBVReportForm(forms.ModelForm):
    class Meta:
        model = GBVReport
        fields = [
            'report_type', 'county', 'location', 'incident_date', 'description',
            'anonymous', 'name', 'id_number', 'gender', 'phone', 'email',
            'relationship_to_perpetrator', 'consent', 'followup_opt_in', 'followup_email',
        ]
        widgets = {
            'incident_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_consent(self):
        consent = self.cleaned_data.get('consent')
        if not consent:
            raise ValidationError('You must agree to the consent statement to submit this report.')
        return consent

    def clean_incident_date(self):
        incident_date = self.cleaned_data.get('incident_date')
        if incident_date and incident_date > date.today():
            raise ValidationError('Date cannot be in the future. Please select today or an earlier date.')
        return incident_date

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_validator(phone)
        return phone

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name_validator(name)
        return name

    def clean(self):
        cleaned = super().clean()
        anonymous = cleaned.get('anonymous', False)

        if not anonymous:
            if not cleaned.get('name'):
                self.add_error('name', 'Your name is required when not reporting anonymously.')
            if not cleaned.get('phone') and not cleaned.get('email'):
                self.add_error('phone', 'Please provide at least a phone number or email so we can follow up.')

        if cleaned.get("followup_opt_in") and not cleaned.get("followup_email"):
            self.add_error("followup_email", "Email is required for follow-up updates.")

        return cleaned


class ArticleSubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'id': 'articleTitle'})
        self.fields['author'].widget.attrs.update({'id': 'authorName'})
        self.fields['category'].widget.attrs.update({'id': 'articleCategory'})
        self.fields['image'].widget.attrs.update({'id': 'articleImage'})
        self.fields['anonymous'].widget.attrs.update({'id': 'anonymousArticle'})

        if SummernoteWidget is not None:
            self.fields['content'].widget = SummernoteWidget(attrs={
                'placeholder': 'Write your article here...',
                'summernote': {
                    'width': '100%',
                    'height': 320,
                    'dialogsInBody': True,
                    'toolbar': [
                        ['style', ['style']],
                        ['font', ['bold', 'italic', 'underline', 'clear']],
                        ['para', ['ul', 'ol', 'paragraph']],
                        ['insert', ['link', 'picture', 'table', 'hr']],
                        ['view', ['fullscreen', 'codeview']],
                    ],
                },
            })
        else:
            self.fields['content'].widget = forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'articleContent',
                'placeholder': 'Article Content',
                'rows': 10,
            })

    class Meta:
        model = Article
        fields = ['title', 'author', 'category', 'content', 'image', 'anonymous']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Article Title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (Optional)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'anonymous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_author(self):
        """Validate author name format."""
        author = self.cleaned_data.get('author')
        if author:
            name_validator(author)
        return author

    def clean_title(self):
        """Validate title is not empty and reasonable length."""
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if len(title) < 3:
                raise ValidationError('Title must be at least 3 characters long.')
            if len(title) > 200:
                raise ValidationError('Title must be 200 characters or less.')
        return title

    def clean_content(self):
        """Validate content is not empty and reasonable length."""
        content = self.cleaned_data.get('content')
        if content:
            content = content.strip()
            if len(content) < 50:
                raise ValidationError('Content must be at least 50 characters long.')
        return content


class BlogSubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'id': 'blogTitle'})
        self.fields['author'].widget.attrs.update({'id': 'blogAuthorName'})
        self.fields['category'].widget.attrs.update({'id': 'blogCategory'})
        self.fields['image'].widget.attrs.update({'id': 'blogImage'})
        self.fields['anonymous'].widget.attrs.update({'id': 'anonymousBlog'})

        if SummernoteWidget is not None:
            self.fields['content'].widget = SummernoteWidget(attrs={
                'placeholder': 'Write your blog post here...',
                'summernote': {
                    'width': '100%',
                    'height': 320,
                    'dialogsInBody': True,
                    'toolbar': [
                        ['style', ['style']],
                        ['font', ['bold', 'italic', 'underline', 'clear']],
                        ['para', ['ul', 'ol', 'paragraph']],
                        ['insert', ['link', 'picture', 'table', 'hr']],
                        ['view', ['fullscreen', 'codeview']],
                    ],
                },
            })
        else:
            self.fields['content'].widget = forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'blogContent',
                'placeholder': 'Blog Content',
                'rows': 10,
            })

    class Meta:
        model = Blog
        fields = ['title', 'author', 'category', 'content', 'image', 'anonymous']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Blog Title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (Optional)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'anonymous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_author(self):
        author = self.cleaned_data.get('author')
        if author:
            name_validator(author)
        return author

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if len(title) < 3:
                raise ValidationError('Title must be at least 3 characters long.')
            if len(title) > 200:
                raise ValidationError('Title must be 200 characters or less.')
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content:
            content = content.strip()
            if len(content) < 50:
                raise ValidationError('Content must be at least 50 characters long.')
        return content


class StorySubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['consent'].widget.attrs.update({'id': 'storyConsent'})

        if SummernoteWidget is not None:
            self.fields['story'].widget = SummernoteWidget(attrs={
                'placeholder': 'Share your story...',
                'summernote': {
                    'width': '100%',
                    'height': 300,
                    'dialogsInBody': True,
                    'toolbar': [
                        ['font', ['bold', 'italic', 'underline', 'clear']],
                        ['para', ['ul', 'ol', 'paragraph']],
                        ['insert', ['link', 'hr']],
                        ['view', ['fullscreen', 'codeview']],
                    ],
                },
            })
        else:
            self.fields['story'].widget = forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'storyContent',
                'rows': 10,
                'placeholder': 'Your Story',
            })

    class Meta:
        model = Story
        fields = ['story', 'consent']
        widgets = {
            'consent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'consent': (
                'I consent to share my story on the Voices Against Violence platform. '
                'I understand my story may be published to help raise awareness about gender-based violence, '
                'and that my name will not be displayed without my permission.'
            ),
        }

    def clean_consent(self):
        """Validate that consent is given."""
        consent = self.cleaned_data.get('consent')
        if not consent:
            raise ValidationError('You must consent to share your story.')
        return consent

    def clean_name(self):
        """Validate name format."""
        name = self.cleaned_data.get('name')
        if name:
            name_validator(name)
        return name

    def clean_story(self):
        """Validate story is not empty and reasonable length."""
        story = self.cleaned_data.get('story')
        if story:
            story = story.strip()
            if len(story) < 20:
                raise ValidationError('Story must be at least 20 characters long.')
        return story


class ResourceSubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resource_type'].widget.attrs.update({'class': 'form-select'})
        self.fields['name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Resource Name'})
        self.fields['location'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Location'})
        self.fields['address'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Full Address'})
        self.fields['phone'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Phone Number'})
        self.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 5, 'placeholder': 'Description'})
        self.fields['latitude'].widget.attrs.update({'id': 'id_latitude'})
        self.fields['longitude'].widget.attrs.update({'id': 'id_longitude'})

    class Meta:
        model = Resource
        fields = ['resource_type', 'name', 'location', 'address', 'phone', 'description', 'latitude', 'longitude']
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def clean_phone(self):
        """Validate phone number format."""
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_validator(phone)
        return phone

    def clean_name(self):
        """Validate resource name."""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 2:
                raise ValidationError('Resource name must be at least 2 characters long.')
        return name

    def clean_latitude(self):
        latitude = self.cleaned_data.get('latitude')
        if latitude is None:
            return latitude
        if latitude < -90 or latitude > 90:
            raise ValidationError('Latitude must be between -90 and 90.')
        return latitude

    def clean_longitude(self):
        longitude = self.cleaned_data.get('longitude')
        if longitude is None:
            return longitude
        if longitude < -180 or longitude > 180:
            raise ValidationError('Longitude must be between -180 and 180.')
        return longitude

    def clean_location(self):
        """Validate location."""
        location = self.cleaned_data.get('location')
        if location:
            location = location.strip()
            if len(location) < 2:
                raise ValidationError('Location must be at least 2 characters long.')
        return location


class IdeaSubmissionForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['title'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Idea Title'})
        self.fields['category'].widget.attrs.update({'class': 'form-select'})
        self.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 6, 'placeholder': 'Describe your idea'})

    class Meta:
        model = Idea
        fields = ['title', 'category', 'description']

    def clean_title(self):
        """Validate title is not empty and reasonable length."""
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if len(title) < 3:
                raise ValidationError('Title must be at least 3 characters long.')
            if len(title) > 200:
                raise ValidationError('Title must be 200 characters or less.')
        return title

    def clean_description(self):
        """Validate description is not empty and reasonable length."""
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
            if len(description) < 20:
                raise ValidationError('Description must be at least 20 characters long.')
        return description


class SupportFeedbackForm(forms.ModelForm):
    class Meta:
        model = SupportFeedback
        fields = ["score", "comment"]


class ProfileUpdateForm(forms.Form):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    user_type = forms.ChoiceField(choices=UserProfile.USER_TYPES, required=True)

    def __init__(self, *args, user=None, profile=None, **kwargs):
        self.user = user
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control'})
        self.fields['user_type'].widget.attrs.update({'class': 'form-select'})

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            phone_validator(phone)
        return phone


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field_name in ('current_password', 'new_password', 'confirm_password'):
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    def clean_current_password(self):
        current = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(current):
            raise ValidationError('Current password is incorrect.')
        return current

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get('new_password')
        confirm_password = cleaned.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'New passwords do not match.')

        if new_password and self.user:
            try:
                password_validation.validate_password(new_password, self.user)
            except ValidationError as exc:
                self.add_error('new_password', exc)

        return cleaned
