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


class StaticPageSEO(Timestamped):
	"""SEO metadata for static/hand-built pages (non-imported)."""

	slug = models.SlugField(max_length=255, unique=True, help_text="Slug matching the URL path without leading slash, e.g., 'about-us'.")
	page_name = models.CharField(max_length=255, help_text="Friendly name shown in the admin and templates.")
	seo_title = models.CharField(max_length=255, blank=True, help_text="Overrides the <title> tag if set.")
	seo_description = models.CharField(max_length=300, blank=True, help_text="Overrides the meta description if set.")
	seo_keywords = models.CharField(max_length=500, blank=True, help_text="Comma-separated keywords (optional).")
	seo_image_url = models.URLField(blank=True, help_text="Absolute or /static URL for social sharing (og:image).")
	seo_image_file = models.ImageField(upload_to="seo/", blank=True, null=True, help_text="Upload a social sharing image (og:image). Overrides the URL if provided.")

	class Meta:
		verbose_name = "Static page SEO"
		verbose_name_plural = "Static page SEO entries"
		ordering = ["page_name", "slug"]

	def __str__(self):
		return self.page_name or self.slug


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


class FeeCategory(models.TextChoices):
	PROFESSIONAL = 'professional', 'Professional Service'
	MISC = 'misc', 'Miscellaneous'


class PaymentFeeRow(Timestamped):
	"""Fee table rows for payment options, grouped by category and ordered."""

	name = models.CharField(max_length=255)
	category = models.CharField(max_length=20, choices=FeeCategory.choices, default=FeeCategory.PROFESSIONAL)
	order = models.PositiveIntegerField(default=0, help_text="Display ordering within the category.")
	doctoral_fee = models.CharField(max_length=100, blank=True, help_text="Shown under Doctoral level column.")
	masters_fee = models.CharField(max_length=100, blank=True, help_text="Shown under Master's level column.")
	supervised_fee = models.CharField(max_length=100, blank=True, help_text="Shown under Clinicians under supervision column.")
	notes = models.TextField(blank=True, help_text="Optional notes shown beneath the table when applicable.")

	class Meta:
		ordering = ['category', 'order', 'id']
		verbose_name = "Payment fee row"
		verbose_name_plural = "Payment fee rows"

	def __str__(self) -> str:
		return self.name


class AboutSection(Timestamped):
	"""Configurable copy for the homepage About and Mission section."""

	about_title = models.CharField(max_length=200, default="About Us")
	about_body = RichTextField(blank=True, help_text="Main About Us copy.")
	mission_title = models.CharField(max_length=200, default="Our Mission")
	mission_body = RichTextField(blank=True, help_text="Mission statement copy.")
	cta_label = models.CharField(max_length=200, blank=True, default="Schedule Your First Appointment Today")
	cta_url = models.URLField(
		blank=True,
		default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
		help_text="Optional CTA button link; leave blank to hide the button.",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "About section"
		verbose_name_plural = "About sections"

	def __str__(self) -> str:
		return self.about_title


class WhatWeDoSection(Timestamped):
	"""Configurable copy for the homepage "What We Do" section."""

	title = models.CharField(max_length=200, default="What We Do")
	description = RichTextField(blank=True, help_text="Intro text shown above the bullet list.")
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "What we do section"
		verbose_name_plural = "What we do sections"

	def __str__(self) -> str:
		return self.title


class OurPhilosophy(Timestamped):
	"""Homepage philosophy block content."""

	title = models.CharField(max_length=255, default="Our philosophy of treatment is that people have a need to be connected.")
	body = RichTextField(blank=True, help_text="Displayed under the philosophy heading.")
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "Our philosophy"
		verbose_name_plural = "Our philosophy"

	def __str__(self) -> str:
		return self.title


class ContactInfo(Timestamped):
	"""Homepage contact section content."""

	heading = models.CharField(max_length=255, default="Proud to Serve Cincinnati/Northern Kentucky")
	map_embed_url = models.URLField(
		max_length=1000,
		blank=True,
		help_text="Full Google Maps embed URL for the iframe src.",
		default="https://maps.google.com/maps?q=6900%20houston%20rd.%20Florence%2C%20KY%2041091&t=m&z=15&output=embed&iwloc=near",
	)
	directions_url = models.URLField(
		max_length=1000,
		blank=True,
		help_text="Link for the 'Get Directions' button.",
		default="https://maps.google.com/maps/dir//6900+Houston+Rd+Florence,+KY+41042/@39.0086253,-84.647614,15z/data=!4m5!4m4!1m0!1m2!1m1!1s0x8841c7da6f65d4c7:0xa64ac61629ef897f",
	)
	office_title = models.CharField(max_length=200, default="Our Office")
	office_address = models.TextField(
		default="6900 Houston Rd.\nBuilding 500 Suite 11\nFlorence, KY 41042",
		help_text="Supports line breaks to split the address.",
	)
	office_hours_title = models.CharField(max_length=200, default="Office Hours")
	office_hours = models.TextField(
		default="Mon - Thurs: 8AM - 9PM\nFriday: 8AM - 5PM\nSaturday: 8AM - 2PM",
		help_text="One entry per line. Bold labels can be added in the template.",
	)
	contact_title = models.CharField(max_length=200, default="Contact Us")
	phone_label = models.CharField(max_length=100, default="Office")
	phone_number = models.CharField(max_length=50, default="859-525-4911")
	fax_label = models.CharField(max_length=100, default="Fax")
	fax_number = models.CharField(max_length=50, default="859-525-6446")
	email_label = models.CharField(max_length=100, default="Front Office")
	email_address = models.EmailField(blank=True, default="")
	cta_label = models.CharField(max_length=120, default="Schedule Online")
	cta_url = models.URLField(
		max_length=500,
		blank=True,
		default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
	)
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "Contact info"
		verbose_name_plural = "Contact info"

	def __str__(self) -> str:
		return self.heading


class InspirationalQuote(Timestamped):
	"""Homepage inspirational quote block."""

	quote = models.TextField(help_text="Quote content shown inside the blockquote.")
	author = models.CharField(max_length=255, blank=True, help_text="Optional author/attribution displayed below the quote.")
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "Inspirational quote"
		verbose_name_plural = "Inspirational quotes"

	def __str__(self) -> str:
		return self.author or (self.quote[:50] + "...")


class CompanyQuote(Timestamped):
	"""Homepage company quote block."""

	quote = models.TextField(help_text="Quote content shown inside the blockquote.")
	author = models.CharField(max_length=255, blank=True, default="L+C Psychological Services", help_text="Optional author/attribution displayed below the quote.")
	is_active = models.BooleanField(default=True)

	class Meta:
		verbose_name = "Company quote"
		verbose_name_plural = "Company quotes"

	def __str__(self) -> str:
		return self.author or (self.quote[:50] + "...")


class WhatWeDoItem(Timestamped):
	"""Bullet points displayed within the "What We Do" list."""

	text = models.CharField(max_length=200)
	order = models.PositiveIntegerField(default=0, help_text="Display ordering for the list.")
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["order", "id"]
		verbose_name = "What we do item"
		verbose_name_plural = "What we do items"

	def __str__(self) -> str:
		return self.text


class FAQItem(Timestamped):
	"""Frequently asked questions shown on the public site."""

	question = models.CharField(max_length=500)
	answer = models.TextField()
	order = models.PositiveIntegerField(default=0, help_text="Controls display order.")
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["order", "id"]
		verbose_name = "FAQ item"
		verbose_name_plural = "FAQ items"

	def __str__(self) -> str:
		return self.question
