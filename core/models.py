from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from ckeditor.fields import RichTextField
class PublishStatus(models.TextChoices):
	DRAFT = 'draft', 'Draft'
	PUBLISH = 'publish', 'Published'



class Timestamped(models.Model):
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Category(Timestamped):
	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=200, unique=True)
	description = models.TextField(blank=True)
	wp_id = models.IntegerField(null=True, blank=True, db_index=True)

	def __str__(self):
		return self.name


class Tag(Timestamped):
	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=200, unique=True)
	description = models.TextField(blank=True)
	wp_id = models.IntegerField(null=True, blank=True, db_index=True)

	def __str__(self):
		return self.name


class Page(Timestamped):
	title = models.CharField(max_length=500)
	slug = models.SlugField(max_length=255)
	path = models.CharField(max_length=1000, unique=True, help_text="Slash-separated path without leading/trailing slash")
	# Optional per-page SEO overrides
	seo_title = models.CharField(max_length=255, blank=True, help_text="Overrides the page title tag if set")
	seo_description = models.CharField(max_length=300, blank=True, help_text="Overrides meta description if set")
	seo_keywords = models.CharField(max_length=500, blank=True, help_text="Comma-separated keywords (optional; most search engines ignore this)")
	seo_image_url = models.URLField(blank=True, help_text="Absolute URL for social share image (og:image). Leave blank to use default.")
	excerpt_html = models.TextField(blank=True)
	content_html = models.TextField()
	parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
	menu_order = models.IntegerField(default=0)
	status = models.CharField(max_length=50, choices=PublishStatus.choices, default=PublishStatus.PUBLISH)
	original_url = models.URLField(blank=True)
	published_at = models.DateTimeField(null=True, blank=True)
	modified_at = models.DateTimeField(null=True, blank=True)
	wp_id = models.IntegerField(db_index=True)
	wp_type = models.CharField(max_length=50, default='page')

	class Meta:
		unique_together = (('wp_id', 'wp_type'),)
		ordering = ['menu_order', 'title']

	def __str__(self):
		return self.title

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)[:255]
		if self.path:
			self.path = self.path.strip('/')
		else:
			# derive from parent
			parts = []
			if self.parent and self.parent.path:
				parts.append(self.parent.path)
			parts.append(self.slug)
			self.path = '/'.join([p for p in parts if p])
		super().save(*args, **kwargs)


class Post(Timestamped):
	title = models.CharField(max_length=500)
	slug = models.SlugField(max_length=255, unique=True)
	excerpt_html = models.TextField(blank=True)
	content_html = models.TextField()
	status = models.CharField(max_length=50, choices=PublishStatus.choices, default=PublishStatus.PUBLISH)
	original_url = models.URLField(blank=True)
	published_at = models.DateTimeField(null=True, blank=True)
	modified_at = models.DateTimeField(null=True, blank=True)
	categories = models.ManyToManyField(Category, blank=True)
	tags = models.ManyToManyField(Tag, blank=True)
	wp_id = models.IntegerField(db_index=True)
	wp_type = models.CharField(max_length=50, default='post')
	# Optional per-post SEO overrides
	seo_title = models.CharField(max_length=255, blank=True, help_text="Overrides the post title tag if set")
	seo_description = models.CharField(max_length=300, blank=True, help_text="Overrides meta description if set")
	seo_keywords = models.CharField(max_length=500, blank=True, help_text="Comma-separated keywords (optional; most search engines ignore this)")
	seo_image_url = models.URLField(blank=True, help_text="Absolute URL for social share image (og:image). Leave blank to use default.")

	class Meta:
		unique_together = (('wp_id', 'wp_type'),)
		ordering = ['-published_at']

	def __str__(self):
		return self.title


## NavItem removed – navigation is managed by static templates now.

# Create your models here.


class Service(Timestamped):
	"""Homepage services card with an optional long-form detail page."""

	title = models.CharField(max_length=200)
	slug = models.SlugField(max_length=200, unique=True)
	excerpt = models.TextField(blank=True, help_text="Short blurb shown on the homepage card and detail hero.")
	image_url = models.URLField(
		max_length=1000,
		blank=True,
		help_text="Optional external/background image URL used when no file is uploaded.",
	)
	background_image = models.ImageField(
		upload_to="services/backgrounds/",
		blank=True,
		null=True,
		help_text="Upload a background image for the card and detail hero.",
	)
	cta_label = models.CharField(max_length=80, blank=True, default="Learn More...")
	hero_heading = models.CharField(max_length=200, blank=True, help_text="Overrides the hero heading on the detail page.")
	hero_subheading = models.TextField(blank=True, help_text="Intro copy that appears under the hero heading on the detail page.")
	body = RichTextField(blank=True, help_text="Full detail page content (supports rich text).")
	page = models.ForeignKey(
		Page,
		on_delete=models.SET_NULL,
		related_name="service_cards",
		blank=True,
		null=True,
		help_text="Optional legacy page to pull content from when no body content is provided.",
	)
	order = models.PositiveIntegerField(default=0, help_text="Controls display ordering on the homepage.")
	status = models.CharField(max_length=50, choices=PublishStatus.choices, default=PublishStatus.PUBLISH)

	class Meta:
		ordering = ["order", "title"]

	def __str__(self):
		return self.title

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)[:200]
		super().save(*args, **kwargs)

	@property
	def card_background_url(self) -> str:
		if self.background_image:
			try:
				return self.background_image.url
			except ValueError:
				return ""
		return self.image_url or ""

	@property
	def hero_title(self) -> str:
		return self.hero_heading or self.title

	@property
	def hero_intro(self) -> str:
		return self.hero_subheading or self.excerpt

	@property
	def body_html(self) -> str:
		if self.body:
			return self.body
		if self.page:
			return self.page.content_html
		return ""

	@property
	def seo_image_url(self) -> str:
		if self.background_image:
			try:
				return self.background_image.url
			except ValueError:
				return ""
		return self.image_url or ""

	def get_absolute_url(self) -> str:
		return reverse("service_detail", args=[self.slug])
