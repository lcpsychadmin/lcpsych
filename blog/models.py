from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from tinymce.models import HTMLField


class PublishedManager(models.Manager):
    def get_queryset(self):
        now = timezone.now()
        return (
            super()
            .get_queryset()
            .filter(status=Post.STATUS_PUBLISHED)
            .filter(models.Q(publish_at__lte=now) | models.Q(publish_at__isnull=True))
        )


class Post(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
    )

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    body = HTMLField()
    excerpt = models.TextField(blank=True)
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)
    feature_image = models.ImageField(upload_to='posts/', blank=True, null=True)
    categories = models.ManyToManyField('Category', related_name='posts', blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    publish_at = models.DateTimeField(blank=True, null=True, default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        ordering = ['-publish_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'publish_at']),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        if not self.excerpt:
            self.excerpt = self._build_excerpt()
        if not self.seo_title:
            self.seo_title = self.title[:160]
        if self.publish_at is None:
            self.publish_at = timezone.now()
        super().save(*args, **kwargs)

    def _build_excerpt(self, words: int = 40) -> str:
        text = strip_tags(self.body or '')
        collapsed = ' '.join(text.split())
        parts = collapsed.split(' ')
        snippet = ' '.join(parts[:words])
        if len(parts) > words:
            snippet += '…'
        return snippet


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)
