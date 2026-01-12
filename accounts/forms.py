from django import forms
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm

from ckeditor.widgets import CKEditorWidget

from core.models import Service


class InviteUserForm(forms.Form):
    email = forms.EmailField()
    is_admin = forms.BooleanField(required=False, initial=False, label="Admin role")
    is_therapist = forms.BooleanField(required=False, initial=True, label="Therapist role")


class ActivationSetPasswordForm(DjangoSetPasswordForm):
    pass


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
