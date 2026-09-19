from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from urllib.parse import quote_plus
from .services.geocoding import geocode_kenya_resource


class UserProfile(models.Model):
    USER_TYPES = [
        ('victim', 'Reporter'),
        ('contributor', 'Contributor'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='victim')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.user_type}"


class GBVReport(models.Model):
    STATUS_RECEIVED = "received"
    STATUS_ASSIGNED = "assigned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_CLOSED, "Closed"),
    ]

    REPORT_TYPES = [
        ('physical', 'Physical Violence'),
        ('sexual', 'Sexual Violence'),
        ('emotional', 'Emotional/Psychological Abuse'),
        ('economic', 'Economic Abuse'),
        ('other', 'Other'),
    ]

    GENDER_CHOICES = [
        ('female', 'Female'),
        ('male', 'Male'),
        ('non_binary', 'Non-binary'),
        ('prefer_not', 'Prefer not to say'),
    ]

    RELATIONSHIP_CHOICES = [
        ('partner', 'Intimate Partner / Spouse'),
        ('family', 'Family Member'),
        ('acquaintance', 'Acquaintance / Neighbour'),
        ('employer', 'Employer / Authority Figure'),
        ('stranger', 'Stranger'),
        ('unknown', 'Unknown'),
        ('other', 'Other'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    location = models.CharField(max_length=255)
    county = models.CharField(max_length=100, blank=True, null=True)
    incident_date = models.DateField(blank=True, null=True)
    description = models.TextField()
    anonymous = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    relationship_to_perpetrator = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES, blank=True, null=True
    )
    consent = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    status_updated_at = models.DateTimeField(default=timezone.now)
    followup_opt_in = models.BooleanField(default=False)
    followup_email = models.EmailField(blank=True, null=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gbv_reports",
    )

    def __str__(self):
        return f"Report by {self.name or 'Anonymous'} - {self.report_type}"

    def set_status(self, status_value, changed_by=None, note=""):
        self.status = status_value
        self.status_updated_at = timezone.now()
        self.save(update_fields=["status", "status_updated_at"])
        GBVReportStatusUpdate.objects.create(
            report=self,
            status=status_value,
            note=note or "",
            changed_by=changed_by
        )
        recipient = self.followup_email if self.followup_opt_in and self.followup_email else None
        if not recipient and self.submitted_by and self.submitted_by.email:
            recipient = self.submitted_by.email

        if recipient:
            try:
                send_mail(
                    subject=f"VAV Report #{self.id} Status Updated",
                    message=(
                        f"Your report status is now: {self.get_status_display()}.\n\n"
                        f"Note: {note or 'No additional note provided.'}\n\n"
                        "Thank you for using Voices Against Violence."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[recipient],
                    fail_silently=True,
                )
            except Exception:
                pass


class GBVReportStatusUpdate(models.Model):
    report = models.ForeignKey(GBVReport, on_delete=models.CASCADE, related_name="status_updates")
    status = models.CharField(max_length=20, choices=GBVReport.STATUS_CHOICES)
    note = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Resource(models.Model):
    RESOURCE_TYPES = [
        ('police', 'Police Post'),
        ('safehouse', 'Safe House'),
        ('church', 'Church'),
        ('hospital', 'Hospital'),
        ('counseling', 'Counseling Center'),
        ('legal', 'Legal Aid'),
        ('other', 'Other'),
    ]

    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='other')
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    last_confirmed_at = models.DateTimeField(blank=True, null=True)
    opens_at = models.TimeField(blank=True, null=True)
    closes_at = models.TimeField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    @property
    def open_now(self):
        if not self.opens_at or not self.closes_at:
            return None
        now_t = timezone.localtime().time()
        if self.opens_at <= self.closes_at:
            return self.opens_at <= now_t <= self.closes_at
        return now_t >= self.opens_at or now_t <= self.closes_at

    def __str__(self):
        return f"{self.name} - {self.location}"

    @property
    def services(self):
        if self.resource_type == 'police':
            return "Emergency Response, Investigation"
        elif self.resource_type == 'safehouse':
            return "Shelter, Counseling"
        elif self.resource_type == 'church':
            return "Counseling, Support Groups"
        elif self.resource_type == 'hospital':
            return "Medical Care, Trauma Support"
        elif self.resource_type == 'counseling':
            return "Psychological Support, Therapy"
        elif self.resource_type == 'legal':
            return "Legal Aid, Advocacy"
        else:
            return "Support Services"

    @property
    def get_directions_url(self):
        if self.latitude is not None and self.longitude is not None:
            return (
                "https://www.google.com/maps/dir/?api=1"
                f"&destination={self.latitude},{self.longitude}&travelmode=driving"
            )

        parts = [self.name, self.location, self.address]
        query = ', '.join([p for p in parts if p])
        if not query:
            return None
        return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(query)}&travelmode=driving"

    def _geocode(self, default_county="Nakuru County"):
        result = geocode_kenya_resource(
            name=self.name,
            location=self.location,
            address=self.address,
            default_county=default_county,
        )
        if not result:
            return

        self.latitude = result.get("latitude")
        self.longitude = result.get("longitude")

    def save(self, *args, **kwargs):
        if self.latitude is None or self.longitude is None:
            self._geocode()
        super().save(*args, **kwargs)


REVIEW_STATUS_CHOICES = [
    ('pending', 'Pending Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class Article(models.Model):
    CATEGORIES = [
        ('education', 'Education'),
        ('prevention', 'Prevention'),
        ('support', 'Support Services'),
        ('legal', 'Legal Rights'),
        ('awareness', 'Awareness'),
        ('recovery', 'Recovery & Healing'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100, blank=True, null=True)
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_articles",
    )
    category = models.CharField(max_length=20, choices=CATEGORIES)
    content = models.TextField()
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    read_time = models.PositiveIntegerField(default=5)
    views = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    review_note = models.TextField(blank=True, null=True, help_text="Feedback shown to the contributor")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Blog(models.Model):
    CATEGORIES = [
        ('education', 'Education'),
        ('prevention', 'Prevention'),
        ('support', 'Support Services'),
        ('legal', 'Legal Rights'),
        ('awareness', 'Awareness'),
        ('recovery', 'Recovery & Healing'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100, blank=True, null=True)
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_blogs",
    )
    category = models.CharField(max_length=20, choices=CATEGORIES, default='other')
    content = models.TextField()
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    read_time = models.PositiveIntegerField(default=5)
    views = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    review_note = models.TextField(blank=True, null=True, help_text="Feedback shown to the contributor")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Story(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stories',
    )
    story = models.TextField()
    consent = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    review_note = models.TextField(blank=True, null=True, help_text="Feedback shown to the contributor")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Stories"

    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f"Story by {username}"


class Idea(models.Model):
    CATEGORIES = [
        ('platform', 'Platform Improvement'),
        ('feature', 'New Feature'),
        ('campaign', 'Awareness Campaign'),
        ('education', 'Education Content'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ideas',
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    review_note = models.TextField(blank=True, null=True, help_text="Feedback shown to the contributor")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Contact(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contacts',
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contact from {self.name} - {self.subject}"


class Team(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    image = models.ImageField(upload_to='team/', blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.role}"




class AuditLog(models.Model):
    action = models.CharField(max_length=120)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    target_type = models.CharField(max_length=80, blank=True, default="")
    target_id = models.CharField(max_length=80, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SupportFeedback(models.Model):
    report = models.ForeignKey(GBVReport, on_delete=models.CASCADE, related_name="feedback_items")
    score = models.PositiveSmallIntegerField()  # 1-5
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback #{self.id} for report #{self.report_id} ({self.score}/5)"
