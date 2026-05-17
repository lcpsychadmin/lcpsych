from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm as DjangoSetPasswordForm

from ckeditor.widgets import CKEditorWidget

from core.models import (
    Service,
    ServiceContentBlock,
    PaymentFeeRow,
    InsuranceProvider,
    InsuranceExclusion,
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
    SocialPlatform,
    OfficeLocation,
    HeroSettings,
    HeroContentBlock,
    Modality,
    ModalityContentBlock,
    Condition,
    ConditionContentBlock,
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


class ServiceContentBlockForm(forms.ModelForm):
    """Form for a single ServiceContentBlock.

    Sets initial['order'] = 0 so that an empty extra form row whose order
    widget renders as 0 is NOT considered 'changed', preventing spurious
    required-field validation errors when the user saves without filling in
    any blocks.
    """

    class Meta:
        model = ServiceContentBlock
        fields = ["order", "heading", "body"]
        widgets = {
            "order": forms.NumberInput(attrs={"class": "input-basic"}),
            "heading": forms.TextInput(attrs={"class": "input-basic"}),
            "body": forms.Textarea(attrs={"rows": 4, "class": "input-basic"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("order", 0)


ServiceContentBlockFormSet = forms.inlineformset_factory(
    Service,
    ServiceContentBlock,
    form=ServiceContentBlockForm,
    extra=1,
    can_delete=True,
)


class ModalityContentBlockForm(forms.ModelForm):
    class Meta:
        model = ModalityContentBlock
        fields = ["order", "heading", "body"]
        widgets = {
            "order": forms.NumberInput(attrs={"class": "input-basic"}),
            "heading": forms.TextInput(attrs={"class": "input-basic"}),
            "body": forms.Textarea(attrs={"rows": 4, "class": "input-basic"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("order", 0)


ModalityContentBlockFormSet = forms.inlineformset_factory(
    Modality,
    ModalityContentBlock,
    form=ModalityContentBlockForm,
    extra=1,
    can_delete=True,
)


class ConditionContentBlockForm(forms.ModelForm):
    class Meta:
        model = ConditionContentBlock
        fields = ["order", "heading", "body"]
        widgets = {
            "order": forms.NumberInput(attrs={"class": "input-basic"}),
            "heading": forms.TextInput(attrs={"class": "input-basic"}),
            "body": forms.Textarea(attrs={"rows": 4, "class": "input-basic"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("order", 0)


ConditionContentBlockFormSet = forms.inlineformset_factory(
    Condition,
    ConditionContentBlock,
    form=ConditionContentBlockForm,
    extra=1,
    can_delete=True,
)


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "title",
            "slug",
            "status",
            "order",
            "excerpt",
            "cta_label",
            "background_image",
            "hero_heading",
            "hero_subheading",
        ]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "hero_subheading": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Optional. Leave blank to auto-generate from the title."
        self.fields["cta_label"].help_text = "Button label shown on the homepage card."
        self.fields["background_image"].required = False
        self.fields["background_image"].label = "Background image"
        self.fields["hero_heading"].label = "Hero heading"
        self.fields["hero_heading"].help_text = "Defaults to the service title if left blank."
        self.fields["hero_subheading"].label = "Hero introduction"
        self.fields["hero_subheading"].help_text = "Defaults to the excerpt if left blank."
        for name, field in self.fields.items():
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


class InsuranceProviderForm(forms.ModelForm):
    class Meta:
        model = InsuranceProvider
        fields = ["name", "order", "logo", "logo_url", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["order"].help_text = "Controls display ordering in the accepted list."
        self.fields["is_active"].label = "Show on site"


class InsuranceExclusionForm(forms.ModelForm):
    class Meta:
        model = InsuranceExclusion
        fields = ["name", "order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["order"].help_text = "Controls display ordering in the non-accepted list."
        self.fields["is_active"].label = "Show on site"


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
            "about_heading",
            "about_subheading",
            "about_title",
            "about_body",
            "mission_title",
            "mission_body",
            "cta_label",
            "cta_url",
            "clinicians_heading",
            "clinicians_subtext",
            "is_active",
        ]
        widgets = {
            "about_body": CKEditorWidget(),
            "mission_body": CKEditorWidget(),
            "about_subheading": forms.Textarea(attrs={"rows": 3}),
            "clinicians_subtext": forms.Textarea(attrs={"rows": 2}),
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


class AboutHeroImageForm(forms.ModelForm):
    class Meta:
        model = HeroSettings
        fields = ["about_hero_image"]


class OurPhilosophyForm(forms.ModelForm):
    class Meta:
        model = OurPhilosophy
        fields = [
            "title",
            "body",
            "value1_title",
            "value1_description",
            "value2_title",
            "value2_description",
            "value3_title",
            "value3_description",
            "is_active",
        ]
        widgets = {
            "body": CKEditorWidget(),
            "value1_description": forms.Textarea(attrs={"rows": 3}),
            "value2_description": forms.Textarea(attrs={"rows": 3}),
            "value3_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"body"}:
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
            "phone_number",
            "fax_number",
            "email_address",
            "cta_label",
            "cta_url",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["email_address"].required = False


class OfficeLocationForm(forms.ModelForm):
    class Meta:
        model = OfficeLocation
        fields = [
            "name",
            "slug",
            "section_heading",
            "map_embed_url",
            "directions_url",
            "address_line1",
            "address_line2",
            "address_city",
            "address_state",
            "address_zip",
            "office_hours_title",
            "office_hours",
            "phone_label",
            "phone_number",
            "fax_label",
            "fax_number",
            "email_label",
            "email_address",
            "cta_label",
            "cta_url",
            "is_active",
            "is_virtual",
            "order",
        ]
        widgets = {
            "office_hours": forms.Textarea(attrs={"rows": 4}),
            "map_embed_url": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("is_active", "is_virtual"):
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Leave blank to auto-generate from the office name."
        self.fields["section_heading"].required = False
        self.fields["section_heading"].help_text = "Defaults to the office name if blank."


# Per-platform metadata used by SocialProfileForm to show accurate labels/help text.
PLATFORM_META: dict[str, dict] = {
    SocialPlatform.INSTAGRAM: {
        "client_id_label": "App ID",
        "client_id_help": "Your Meta app's App ID. Not required for page token auth — leave blank if you're using a manually-generated long-lived token.",
        "client_secret_label": "App Secret",
        "client_secret_help": "Your Meta app's App Secret. Required only if you need to programmatically extend or refresh tokens.",
        "account_id_label": "Instagram Business Account ID",
        "account_id_help": "The numeric ID of your Instagram Business or Creator account (not the username). Find it in Meta Business Suite → Settings → Business Info.",
        "access_token_label": "Long-lived access token",
        "access_token_help": "Meta long-lived tokens are valid for ~60 days. Extend via the Meta API before expiry.",
        "refresh_token_help": "Instagram does not issue refresh tokens. Leave blank — extend the long-lived token directly before it expires.",
        "message_char_limit": 2200,
        "message_help": "Up to 2,200 characters. URLs in captions are not clickable on Instagram — consider directing followers to the link in your bio instead.",
    },
    SocialPlatform.X: {
        "client_id_label": "API Key (Consumer Key)",
        "client_id_help": "Found in the X Developer Portal under your app's 'Keys and Tokens' tab. Also called the Consumer Key.",
        "client_secret_label": "API Secret (Consumer Secret)",
        "client_secret_help": "Found alongside the API Key in the Developer Portal. Also called the Consumer Secret. Keep this private.",
        "account_id_label": "X / Twitter User ID",
        "account_id_help": "The numeric user ID of the @lcpsychological account. Optional — the Access Token is already scoped to the correct account.",
        "access_token_label": "Access Token",
        "access_token_help": "The OAuth 1.0a Access Token generated for your account in the Developer Portal (under 'Authentication Tokens').",
        "refresh_token_label": "Access Token Secret",
        "refresh_token_help": "Access Token Secret (OAuth 1.0a). Generated alongside the Access Token in the Developer Portal. Required for signing requests.",
        "message_char_limit": 280,
        "message_help": "Hard limit of 280 characters. The URL alone takes ~23 characters — keep the rest very concise.",
    },
    SocialPlatform.FACEBOOK_PAGE: {
        "client_id_label": "App ID",
        "client_id_help": "Your Meta app's App ID. Not required for page token auth — leave blank if you're using a manually-generated long-lived page token.",
        "client_secret_label": "App Secret",
        "client_secret_help": "Your Meta app's App Secret. Required only if you need to programmatically extend or refresh tokens.",
        "account_id_label": "Facebook Page ID",
        "account_id_help": "The numeric Page ID. Find it in your Page's About section or via the Meta Graph API Explorer (/me/accounts).",
        "access_token_label": "Long-lived page access token",
        "access_token_help": "A Page access token generated from a long-lived user token via /me/accounts. Valid for ~60 days.",
        "refresh_token_help": "Facebook does not use standard OAuth refresh tokens. Leave blank — re-generate the page token from a new user token when it expires.",
        "message_char_limit": 63206,
        "message_help": "Facebook Page posts support up to 63,206 characters.",
    },
    SocialPlatform.GOOGLE_BUSINESS: {
        "client_id_label": "OAuth 2.0 Client ID",
        "client_id_help": "From Google Cloud Console → APIs & Services → Credentials. Required for automatic token renewal via the refresh token.",
        "client_secret_label": "OAuth 2.0 Client Secret",
        "client_secret_help": "Found alongside the Client ID in Google Cloud Console. Required for automatic token renewal.",
        "account_id_label": "Location resource name",
        "account_id_help": "Full format: accounts/{account_id}/locations/{location_id}. Find it via the Google Business Profile API or your GBP dashboard URL.",
        "access_token_label": "OAuth 2.0 access token",
        "access_token_help": "Short-lived Google OAuth 2.0 token (expires in ~1 hour). The refresh token below is required for automatic renewal.",
        "refresh_token_help": "Required. Google access tokens expire in 1 hour — the refresh token is used to obtain new access tokens automatically without re-authenticating.",
        "message_char_limit": 1500,
        "message_help": "Google Business Profile posts support up to 1,500 characters.",
    },
    SocialPlatform.LINKEDIN_PAGE: {
        "client_id_label": "Client ID",
        "client_id_help": "From LinkedIn Developer Portal → your app → Auth. Required for automatic token renewal.",
        "client_secret_label": "Client Secret",
        "client_secret_help": "Found alongside the Client ID in the LinkedIn Developer Portal. Required for automatic token renewal.",
        "account_id_label": "Organization ID",
        "account_id_help": "The numeric ID from your LinkedIn Page URL (linkedin.com/company/12345). You can also enter the full URN: urn:li:organization:12345.",
        "access_token_label": "OAuth 2.0 access token",
        "access_token_help": "OAuth 2.0 token with w_organization_social scope. Valid for 60 days.",
        "refresh_token_help": "Recommended. Request the refresh_token scope during OAuth authorization to enable automatic renewal.",
        "message_char_limit": 3000,
        "message_help": "LinkedIn posts support up to 3,000 characters; 700 or fewer is recommended for best engagement.",
    },
}


class SocialProfileForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = [
            "account_name",
            "client_id",
            "client_secret",
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
        platform = kwargs.pop("platform", None)
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "auto_post_on_publish":
                field.label = "Auto-post on publish"
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()
        self.fields["token_expires_at"].required = False

        meta = PLATFORM_META.get(platform, {})
        if meta:
            self.fields["client_id"].label = meta["client_id_label"]
            self.fields["client_id"].help_text = meta["client_id_help"]
            self.fields["client_secret"].label = meta["client_secret_label"]
            self.fields["client_secret"].help_text = meta["client_secret_help"]
            self.fields["account_id"].label = meta["account_id_label"]
            self.fields["account_id"].help_text = meta["account_id_help"]
            self.fields["access_token"].label = meta["access_token_label"]
            self.fields["access_token"].help_text = meta["access_token_help"]
            self.fields["refresh_token"].help_text = meta["refresh_token_help"]
            if "refresh_token_label" in meta:
                self.fields["refresh_token"].label = meta["refresh_token_label"]
            self.fields["message_template"].help_text = meta["message_help"]
            self.fields["message_template"].widget.attrs["data-char-limit"] = meta["message_char_limit"]


class HeroSettingsForm(forms.ModelForm):
    class Meta:
        model = HeroSettings
        fields = ["heading", "subheading", "featured_image"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "featured_image":
                continue
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()


class HeroContentBlockForm(forms.ModelForm):
    class Meta:
        model = HeroContentBlock
        fields = ["heading", "body", "order"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{base} input-basic".strip()


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
