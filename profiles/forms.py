from django import forms
from django.utils.text import slugify
import base64

from django.core.files.base import ContentFile
from django.utils import timezone

from ckeditor.widgets import CKEditorWidget

from core.models import PublishStatus, Service

from .models import ClientFocus, LicenseType, TherapistProfile


class TherapistProfileForm(forms.ModelForm):
    cropped_photo_data = forms.CharField(required=False, widget=forms.HiddenInput())
    slug = forms.SlugField(
        required=False,
        label="Profile slug",
        help_text="Custom URL segment, use letters, numbers, or hyphens (example: dr-suzanne-collins).",
    )
    client_focuses = forms.ModelMultipleChoiceField(
        queryset=ClientFocus.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Client focus",
        help_text="Select all client groups you serve.",
    )
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(status=PublishStatus.PUBLISH).order_by("order", "title"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Services",
        help_text="Choose the services clients can work with you on.",
    )
    top_services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(status=PublishStatus.PUBLISH).order_by("order", "title"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Featured services (max 3)",
        help_text="Pick up to three services to feature on cards (fallbacks to overall services).",
    )
    bio = forms.CharField(
        widget=CKEditorWidget(),
        required=False,
        label="Bio",
        help_text="Share background, approach, or anything clients should know.",
    )

    class Meta:
        model = TherapistProfile
        fields = [
            "salutation",
            "first_name",
            "last_name",
            "slug",
            "license_type",
            "client_focuses",
            "services",
            "top_services",
            "bio",
            "accepts_new_clients",
            "photo",
            "intro_video_url",
        ]
        widgets = {
            "salutation": forms.TextInput(attrs={"placeholder": "Dr."}),
            "slug": forms.TextInput(attrs={"placeholder": "dr-suzanne-collins"}),
            "intro_video_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            existing = getattr(self.instance, "slug", "") or ""
            return existing

        normalized = slugify(slug)
        if not normalized:
            raise forms.ValidationError("Enter only letters, numbers, or hyphens.")

        qs = TherapistProfile.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.filter(slug=normalized).exists():
            raise forms.ValidationError("This slug is already used by another profile.")

        return normalized

    def clean_top_services(self):
        top_services = self.cleaned_data.get("top_services") or []
        if len(top_services) > 3:
            raise forms.ValidationError("Select no more than three featured services.")

        services = self.cleaned_data.get("services") or []
        missing = [s for s in top_services if s not in services]
        if missing:
            raise forms.ValidationError("Featured services must also be selected under Services.")

        return top_services

    def _apply_cropped_photo(self, instance):
        data_url = (self.cleaned_data.get("cropped_photo_data") or "").strip()
        if not data_url or "," not in data_url:
            return

        header, encoded = data_url.split(",", 1)
        if not encoded:
            return

        ext = "jpg"
        if "png" in header:
            ext = "png"
        elif "webp" in header:
            ext = "webp"

        try:
            decoded = base64.b64decode(encoded)
        except Exception:
            return

        slug_part = instance.slug or getattr(instance.user, "username", "profile") or "profile"
        timestamp = int(timezone.now().timestamp())
        filename = f"{slug_part}-{timestamp}.{ext}"
        instance.photo.save(filename, ContentFile(decoded), save=False)

    def save(self, commit=True):
        instance = super().save(commit=False)
        self._apply_cropped_photo(instance)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

class AdminTherapistProfileForm(TherapistProfileForm):
    class Meta(TherapistProfileForm.Meta):
        fields = TherapistProfileForm.Meta.fields + ["home_order", "is_published"]
        widgets = {
            **TherapistProfileForm.Meta.widgets,
            "home_order": forms.NumberInput(attrs={"min": 0, "class": "input-basic", "placeholder": "e.g., 1"}),
        }


class LicenseTypeForm(forms.ModelForm):
    class Meta:
        model = LicenseType
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Licensed Professional Counselor", "class": "input-basic"}),
            "description": forms.TextInput(attrs={"placeholder": "Optional short note", "class": "input-basic"}),
        }


class ClientFocusForm(forms.ModelForm):
    class Meta:
        model = ClientFocus
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Couples", "class": "input-basic"}),
            "description": forms.TextInput(attrs={"placeholder": "Optional short note", "class": "input-basic"}),
        }
