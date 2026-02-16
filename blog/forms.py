from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import Post, Category


class PostForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('name'),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'w-full rounded-lg border border-slate-200 px-3 py-2 text-sm'}),
    )
    new_categories = forms.CharField(
        required=False,
        help_text='Comma-separated; new categories will be created automatically.',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Anxiety, Workplace', 'class': 'w-full rounded-lg border border-slate-200 px-3 py-2 text-sm'}),
    )
    class Meta:
        model = Post
        fields = ['title', 'slug', 'status', 'publish_at', 'body', 'seo_title', 'seo_description', 'feature_image', 'categories']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 20}),
            'publish_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.publish_at:
            self.initial['publish_at'] = self.instance.publish_at.strftime('%Y-%m-%dT%H:%M')
        if self.instance and self.instance.pk:
            self.initial['categories'] = self.instance.categories.all()

    def clean_slug(self):
        slug = self.cleaned_data.get('slug') or ''
        title = self.cleaned_data.get('title') or ''
        final_slug = slugify(slug or title)
        if not final_slug:
            raise ValidationError('Please provide a slug or title that can generate one.')

        qs = Post.objects.filter(slug__iexact=final_slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('This slug is already in use. Choose another.')
        return final_slug

    def clean_seo_description(self):
        desc = self.cleaned_data.get('seo_description', '') or ''
        return desc[:160]

    def clean_seo_title(self):
        title = self.cleaned_data.get('seo_title', '') or ''
        return title[:160]

    def save_new_categories(self, post: Post) -> None:
        raw = (self.cleaned_data.get('new_categories') or '').strip()
        if not raw:
            return
        names = [part.strip() for part in raw.split(',') if part.strip()]
        for name in names:
            slug = slugify(name)[:100] or None
            if not slug:
                continue
            category, _ = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            post.categories.add(category)
