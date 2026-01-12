from django.conf import settings
from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField


class LicenseType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ClientFocus(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TherapistProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="therapist_profile",
    )
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    salutation = models.CharField(max_length=32, blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    license_type = models.ForeignKey(
        LicenseType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="therapists",
    )
    client_focuses = models.ManyToManyField(ClientFocus, related_name="therapists", blank=True)
    services = models.ManyToManyField(
        "core.Service",
        related_name="therapists",
        blank=True,
        help_text="Select the services this therapist provides.",
    )
    top_services = models.ManyToManyField(
        "core.Service",
        related_name="featured_therapists",
        blank=True,
        help_text="Optionally choose up to three services to feature on cards.",
    )
    accepts_new_clients = models.BooleanField(default=True)
    photo = models.ImageField(upload_to="therapists/photos/", blank=True, null=True)
    intro_video_url = models.URLField(blank=True)
    bio = RichTextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "pk"]

    def __str__(self) -> str:
        return self.display_name

    @property
    def full_name(self) -> str:
        parts = [self.first_name.strip() if self.first_name else "", self.last_name.strip() if self.last_name else ""]
        name = " ".join(p for p in parts if p)
        if name:
            return name
        fallback = (self.user.get_full_name() or self.user.get_username() or "").strip()
        return fallback or "Therapist"

    @property
    def display_name(self) -> str:
        salutation = (self.salutation or "").strip()
        if salutation:
            return f"{salutation} {self.full_name}".strip()
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.full_name or self.user.get_username()) or "therapist"
            slug = base
            counter = 2
            while TherapistProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
