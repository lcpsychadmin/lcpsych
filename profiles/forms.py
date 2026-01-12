from django import forms
from django.utils.text import slugify
from ckeditor.widgets import CKEditorWidget

from core.models import PublishStatus, Service

from .models import ClientFocus, LicenseType, TherapistProfile


class TherapistProfileForm(forms.ModelForm):
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


class AdminTherapistProfileForm(TherapistProfileForm):
    class Meta(TherapistProfileForm.Meta):
        fields = TherapistProfileForm.Meta.fields + ["is_published"]


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
