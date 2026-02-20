from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm as DjangoSetPasswordForm

from ckeditor.widgets import CKEditorWidget

from core.models import (
    Service,
    PaymentFeeRow,
    FAQItem,
    WhatWeDoItem,
    WhatWeDoSection,
    AboutSection,
    OurPhilosophy,
    InspirationalQuote,
    CompanyQuote,
    ContactInfo,
    StaticPageSEO,
    SocialProfile,
)


class InviteUserForm(forms.Form):
    email = forms.EmailField()
    is_admin = forms.BooleanField(required=False, initial=False, label="Admin role")
    is_therapist = forms.BooleanField(required=False, initial=True, label="Therapist role")
    is_office_manager = forms.BooleanField(required=False, initial=False, label="Office Manager role")


class ActivationSetPasswordForm(DjangoSetPasswordForm):
    pass


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email/Username"


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "title",
            "slug",
            "status",
            "order",
            "excerpt",
            "hero_heading",
            "hero_subheading",
            "cta_label",
            "background_image",
            "image_url",
            "page",
            "body",
        ]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "hero_subheading": forms.Textarea(attrs={"rows": 3}),
            "body": CKEditorWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Optional. Leave blank to generate from the title."
        self.fields["cta_label"].help_text = "Text for the homepage card button."
        self.fields["image_url"].label = "Fallback background image URL"
        self.fields["image_url"].help_text = (
            "Used if no image file is uploaded. Accepts an absolute URL or /static relative path."
        )
        self.fields["background_image"].required = False
        self.fields["hero_heading"].label = "Hero heading"
        self.fields["hero_subheading"].label = "Hero introduction"
        self.fields["body"].label = "Detail page content"
        self.fields["page"].required = False
        self.fields["page"].empty_label = "No legacy page"
        self.fields["page"].label = "Legacy page fallback"
        self.fields["page"].queryset = self.fields["page"].queryset.order_by("title")

        for name, field in self.fields.items():
            if name == "body":
                continue
            existing = field.widget.attrs.get("class", "").strip()
            if "input-basic" not in existing.split():
                field.widget.attrs["class"] = f"{existing} input-basic".strip()
            else:
                field.widget.attrs["class"] = existing

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        return slug or ""


class PaymentFeeRowForm(forms.ModelForm):
    class Meta:
        model = PaymentFeeRow
        fields = [
            "name",
            "category",
            "order",
            "doctoral_fee",
            "masters_fee",
            "supervised_fee",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Light styling to match the settings forms
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["order"].help_text = "Controls display ordering within its category."


class FAQItemForm(forms.ModelForm):
    class Meta:
        model = FAQItem
        fields = [
            "question",
            "answer",
            "order",
            "is_active",
        ]
        widgets = {
            "answer": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_active":
                base = field.widget.attrs.get("class", "").strip()
                field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["order"].help_text = "Controls display order on the public FAQ."
        self.fields["answer"].help_text = "Supports basic HTML (paragraphs, lists)."
        self.fields["is_active"].label = "Show on site"


class WhatWeDoSectionForm(forms.ModelForm):
    class Meta:
        model = WhatWeDoSection
        fields = ["title", "description", "is_active"]
        widgets = {
            "description": CKEditorWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "description":
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["title"].help_text = "Heading shown above the section copy."
        self.fields["is_active"].label = "Show this section"


class WhatWeDoItemForm(forms.ModelForm):
    class Meta:
        model = WhatWeDoItem
        fields = ["text", "order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_active":
                base = field.widget.attrs.get("class", "").strip()
                field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["order"].help_text = "Controls display order within the list."
        self.fields["is_active"].label = "Show on site"


class AboutSectionForm(forms.ModelForm):
    class Meta:
        model = AboutSection
        fields = [
            "about_title",
            "about_body",
            "mission_title",
            "mission_body",
            "cta_label",
            "cta_url",
            "is_active",
        ]
        widgets = {
            "about_body": CKEditorWidget(),
            "mission_body": CKEditorWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"about_body", "mission_body"}:
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["cta_url"].help_text = "Optional; hide the button by leaving this blank."
        self.fields["is_active"].label = "Show this section"


class OurPhilosophyForm(forms.ModelForm):
    class Meta:
        model = OurPhilosophy
        fields = ["title", "body", "is_active"]
        widgets = {
            "body": CKEditorWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "body":
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["is_active"].label = "Show this section"


class InspirationalQuoteForm(forms.ModelForm):
    class Meta:
        model = InspirationalQuote
        fields = ["quote", "author", "is_active"]
        widgets = {
            "quote": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_active":
                base = field.widget.attrs.get("class", "").strip()
                field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["is_active"].label = "Show this section"


class CompanyQuoteForm(forms.ModelForm):
    class Meta:
        model = CompanyQuote
        fields = ["quote", "author", "is_active"]
        widgets = {
            "quote": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "is_active":
                base = field.widget.attrs.get("class", "").strip()
                field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["is_active"].label = "Show this section"


class ContactInfoForm(forms.ModelForm):
    class Meta:
        model = ContactInfo
        fields = [
            "heading",
            "map_embed_url",
            "directions_url",
            "office_title",
            "office_address",
            "office_hours_title",
            "office_hours",
            "contact_title",
            "phone_label",
            "phone_number",
            "fax_label",
            "fax_number",
            "email_label",
            "email_address",
            "cta_label",
            "cta_url",
            "is_active",
        ]
        widgets = {
            "office_address": forms.Textarea(attrs={"rows": 3}),
            "office_hours": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "is_active":
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["is_active"].label = "Show this section"


class SocialProfileForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = [
            "account_name",
            "account_id",
            "access_token",
            "refresh_token",
            "token_expires_at",
            "auto_post_on_publish",
            "message_template",
        ]
        widgets = {
            "message_template": forms.Textarea(attrs={"rows": 3}),
            "token_expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "auto_post_on_publish":
                field.label = "Auto-post on publish"
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["token_expires_at"].required = False


class StaticPageSEOForm(forms.ModelForm):
    class Meta:
        model = StaticPageSEO
        fields = [
            "page_name",
            "slug",
            "seo_title",
            "seo_description",
            "seo_keywords",
            "seo_image_url",
            "seo_image_file",
        ]
        widgets = {
            "seo_description": forms.Textarea(attrs={"rows": 2}),
            "seo_keywords": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["slug"].help_text = "Path without leading slash, e.g., about-us"
        self.fields["page_name"].label = "Page name"
        self.fields["seo_title"].label = "SEO title"
        self.fields["seo_description"].label = "Meta description"
        self.fields["seo_keywords"].label = "Keywords (optional)"
        self.fields["seo_image_url"].label = "Social image URL"
        self.fields["seo_image_file"].label = "Upload social image"
