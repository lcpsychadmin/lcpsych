from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
import hashlib

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
		return reverse("core:service_detail", args=[self.slug])


class ServiceContentBlock(models.Model):
	"""A heading + body content block attached to a Service detail page."""

	service = models.ForeignKey(
		Service,
		on_delete=models.CASCADE,
		related_name="content_blocks",
	)
	order = models.PositiveSmallIntegerField(
		default=0,
		help_text="Lower numbers appear first.",
	)
	heading = models.CharField(max_length=200, help_text="Section heading")
	body = models.TextField(help_text="Paragraph text for this section")

	class Meta:
		ordering = ["order"]

	def __str__(self):
		return self.heading


class HeroSettings(models.Model):
	"""Singleton-style model for configuring the home page hero section."""

	heading = models.CharField(
		max_length=200,
		default="L+C Psychological Services",
		help_text="Main hero heading displayed over the image.",
	)
	subheading = models.CharField(
		max_length=300,
		default="Sometimes We Get Disconnected",
		help_text="Subheading displayed beneath the main heading.",
	)
	featured_image = models.ImageField(
		upload_to="hero/",
		blank=True,
		null=True,
		help_text="Background image for the hero section.",
	)
	about_hero_image = models.ImageField(
		upload_to="hero/",
		blank=True,
		null=True,
		help_text="Featured image displayed in the About Us page hero section.",
	)

	class Meta:
		verbose_name = "Hero settings"
		verbose_name_plural = "Hero settings"

	def __str__(self) -> str:
		return "Hero Settings"

	@classmethod
	def get_solo(cls):
		obj, _ = cls.objects.get_or_create(pk=1)
		return obj


class HeroContentBlock(models.Model):
	"""A heading + body content block displayed below the home page hero image."""

	hero = models.ForeignKey(
		HeroSettings,
		on_delete=models.CASCADE,
		related_name="content_blocks",
	)
	order = models.PositiveSmallIntegerField(
		default=0,
		help_text="Lower numbers appear first.",
	)
	heading = models.CharField(max_length=200, help_text="Block heading")
	body = models.TextField(help_text="Paragraph text for this block")

	class Meta:
		ordering = ["order"]

	def __str__(self) -> str:
		return self.heading


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


class InsuranceProvider(Timestamped):
	"""Accepted insurance providers displayed on the site."""

	name = models.CharField(max_length=255, unique=True)
	order = models.PositiveIntegerField(default=0, help_text="Display ordering in the accepted list.")
	is_active = models.BooleanField(default=True)
	logo = models.ImageField(
		upload_to="insurance/logos/",
		blank=True,
		null=True,
		help_text="Optional uploaded logo shown on the insurance page."
	)
	logo_url = models.URLField(blank=True, help_text="Optional external logo URL if not uploading a file.")

	class Meta:
		ordering = ["order", "name", "id"]
		verbose_name = "Insurance provider"
		verbose_name_plural = "Insurance providers"

	def __str__(self) -> str:
		return self.name

	@property
	def logo_display_url(self) -> str:
		if self.logo:
			try:
				return self.logo.url
			except ValueError:
				return ""
		return self.logo_url or ""


class InsuranceExclusion(Timestamped):
	"""Specific insurance providers the practice does not accept."""

	name = models.CharField(max_length=255, unique=True)
	order = models.PositiveIntegerField(default=0, help_text="Display ordering in the non-accepted list.")
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["order", "name", "id"]
		verbose_name = "Insurance exclusion"
		verbose_name_plural = "Insurance exclusions"

	def __str__(self) -> str:
		return self.name


class AboutSection(Timestamped):
	"""Configurable copy for the homepage About and Mission section."""

	about_heading = models.CharField(
		max_length=200,
		default="About L+C Psychological Services",
		help_text="Main H1 heading in the About Us page hero.",
	)
	about_subheading = models.CharField(
		max_length=400,
		default="Founded on the belief that genuine connection is the foundation of healing — we are a team of dedicated psychologists and therapists serving Northern Kentucky and beyond.",
		help_text="Subheading paragraph in the About Us page hero.",
	)
	about_title = models.CharField(max_length=200, default="About Us")
	about_body = RichTextField(blank=True, help_text="Main About Us copy.")
	mission_title = models.CharField(max_length=200, default="Our Mission")
	mission_body = RichTextField(blank=True, help_text="Mission statement copy.")
	cta_label = models.CharField(max_length=200, blank=True, default="Schedule Your First Appointment")
	cta_url = models.URLField(
		blank=True,
		default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
		help_text="Optional CTA button link; leave blank to hide the button.",
	)
	clinicians_heading = models.CharField(
		max_length=200,
		default="Meet Our Clinicians",
		help_text="Heading for the Meet Our Clinicians section on the About Us page.",
	)
	clinicians_subtext = models.CharField(
		max_length=400,
		default="Our team of licensed psychologists and therapists brings expertise, warmth, and dedication to every client they serve.",
		help_text="Subtitle beneath the clinicians heading.",
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
	value1_title = models.CharField(max_length=100, default="Connection", help_text="First value card title.")
	value1_description = models.TextField(
		default="We believe meaningful relationships are central to healing and growth — both within therapy and in every area of life.",
		help_text="First value card description.",
	)
	value2_title = models.CharField(max_length=100, default="Compassion", help_text="Second value card title.")
	value2_description = models.TextField(
		default="We meet every client with empathy, warmth, and genuine care — creating a safe space where you feel heard and understood.",
		help_text="Second value card description.",
	)
	value3_title = models.CharField(max_length=100, default="Growth", help_text="Third value card title.")
	value3_description = models.TextField(
		default="We help clients build the skills, insight, and resilience needed to thrive — supporting real, lasting change at every stage of life.",
		help_text="Third value card description.",
	)
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


class JoinOurTeamSubmission(Timestamped):
	first_name = models.CharField(max_length=150)
	last_name = models.CharField(max_length=150)
	email = models.EmailField()
	message = models.TextField()
	resume = models.FileField(upload_to="join_our_team_resumes/")
	user_agent = models.TextField(blank=True)
	is_reviewed = models.BooleanField(default=False)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	reviewed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_join_submissions"
	)

	class Meta:
		ordering = ("-created",)

	def __str__(self) -> str:
		return f"{self.full_name} ({self.email})"

	@property
	def full_name(self) -> str:
		return f"{self.first_name} {self.last_name}".strip()

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


class SocialPlatform(models.TextChoices):
	INSTAGRAM = "instagram", "Instagram"
	X = "x", "X (Twitter)"
	FACEBOOK_PAGE = "facebook_page", "Facebook Page"
	GOOGLE_BUSINESS = "google_business", "Google Business Profile"
	LINKEDIN_PAGE = "linkedin_page", "LinkedIn Page"


class SocialProfile(Timestamped):
	platform = models.CharField(max_length=32, choices=SocialPlatform.choices, unique=True)
	account_name = models.CharField(max_length=255, blank=True, help_text="Friendly label for the connected page/profile.")
	account_id = models.CharField(max_length=255, blank=True, help_text="Platform-specific page/profile/business identifier.")
	# App-level credentials (OAuth 1.0a: consumer key/secret; OAuth 2.0: client id/secret)
	client_id = models.CharField(max_length=255, blank=True)
	client_secret = models.TextField(blank=True)
	access_token = models.TextField(blank=True)
	refresh_token = models.TextField(blank=True)
	token_expires_at = models.DateTimeField(null=True, blank=True)
	auto_post_on_publish = models.BooleanField(default=True)
	message_template = models.TextField(
		default="{title} — {excerpt} {url}",
		help_text="Use placeholders: {title}, {excerpt}, {url}. We'll trim to platform limits.",
	)

	class Meta:
		ordering = ["platform"]

	def __str__(self) -> str:
		return f"{self.get_platform_display()} profile"

	@property
	def is_configured(self) -> bool:
		return bool(self.access_token and self.account_id)

	@property
	def is_token_expired(self) -> bool:
		if not self.token_expires_at:
			return False
		return timezone.now() >= self.token_expires_at


class AnalyticsEventType(models.TextChoices):
	PAGE_VIEW = "page_view", "Page view"
	CLICK = "click", "Click"
	HEARTBEAT = "heartbeat", "Heartbeat"
	SCROLL = "scroll", "Scroll depth"
	FORM_SUBMIT = "form_submit", "Form submit"
	FORM_ERROR = "form_error", "Form error"
	AUTH_SUCCESS = "auth_success", "Auth success"
	AUTH_FAILED = "auth_failed", "Auth failed"
	RAGE_CLICK = "rage_click", "Rage click"
	DEAD_CLICK = "dead_click", "Dead click"
	HOVER_INTENT = "hover_intent", "Hover intent"
	SESSION_EXIT = "session_exit", "Session exit"


class AnalyticsEvent(Timestamped):
	"""Lightweight event log for anonymous sessions."""

	event_type = models.CharField(max_length=32, choices=AnalyticsEventType.choices)
	session_id = models.CharField(max_length=64, db_index=True)
	path = models.CharField(max_length=500, db_index=True)
	referrer = models.CharField(max_length=500, blank=True)
	user_agent = models.TextField(blank=True)
	ip_hash = models.CharField(max_length=64, blank=True)
	label = models.CharField(max_length=255, blank=True)
	duration_ms = models.PositiveIntegerField(default=0, help_text="Client-reported duration for the event, if applicable.")
	scroll_percent = models.PositiveSmallIntegerField(default=0)
	metadata = models.JSONField(default=dict, blank=True)
	is_authenticated = models.BooleanField(default=False)
	country_code = models.CharField(max_length=2, blank=True)
	region = models.CharField(max_length=100, blank=True)
	city = models.CharField(max_length=100, blank=True)
	timezone = models.CharField(max_length=64, blank=True)

	class Meta:
		ordering = ["-created"]
		indexes = [
			models.Index(fields=["event_type", "created"]),
			models.Index(fields=["path", "created"]),
		]

	def __str__(self) -> str:
		return f"{self.event_type} @ {self.path}"

	@staticmethod
	def hash_ip(ip: str) -> str:
		if not ip:
			return ""
		secret = getattr(settings, "SECRET_KEY", "")
		return hashlib.sha256(f"{ip}|{secret}".encode()).hexdigest()


class OfficeLocation(Timestamped):
	"""Physical office location with contact info, hours, and geo/therapist associations."""

	name = models.CharField(max_length=200, help_text="Short display name, e.g. 'Florence, KY'")
	slug = models.SlugField(max_length=200, unique=True, help_text="URL slug for /contact-us/<slug>/")
	section_heading = models.CharField(
		max_length=255,
		blank=True,
		help_text="Hero heading for this office's contact page. Defaults to the office name.",
	)

	# Map & navigation
	map_embed_url = models.URLField(
		max_length=1000,
		blank=True,
		help_text="Full Google Maps embed URL for the iframe src.",
	)
	directions_url = models.URLField(
		max_length=1000,
		blank=True,
		help_text="Google Maps directions URL for the 'Get Directions' button.",
	)

	# Structured address (used for schema markup)
	address_line1 = models.CharField(max_length=200, blank=True, help_text="Street address (e.g. '6900 Houston Rd.')")
	address_line2 = models.CharField(max_length=200, blank=True, help_text="Suite/building (e.g. 'Building 500 Suite 11')")
	address_city = models.CharField(max_length=100, blank=True)
	address_state = models.CharField(max_length=50, blank=True, help_text="Two-letter state code (e.g. 'KY')")
	address_zip = models.CharField(max_length=20, blank=True)

	# Hours
	office_hours_title = models.CharField(max_length=200, default="Office hours")
	office_hours = models.TextField(
		blank=True,
		help_text="One entry per line, e.g. 'Mon – Thurs: 8AM – 9PM'.",
	)

	# Contact
	phone_label = models.CharField(max_length=100, default="Office")
	phone_number = models.CharField(max_length=50, blank=True)
	fax_label = models.CharField(max_length=100, default="Fax")
	fax_number = models.CharField(max_length=50, blank=True)
	email_label = models.CharField(max_length=100, default="Email")
	email_address = models.EmailField(blank=True)

	# Scheduling CTA
	cta_label = models.CharField(max_length=120, default="Schedule Online")
	cta_url = models.URLField(
		max_length=500,
		blank=True,
		default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
	)

	# Associations
	therapists = models.ManyToManyField(
		"profiles.TherapistProfile",
		related_name="offices",
		blank=True,
		help_text="Therapists who see clients at this location.",
	)
	geo_states = models.ManyToManyField(
		"geo.GeoState",
		related_name="offices",
		blank=True,
		help_text="States served from this office (for areas-served linking).",
	)
	geo_locations = models.ManyToManyField(
		"geo.GeoLocation",
		related_name="offices",
		blank=True,
		help_text="Specific cities/counties served from this office.",
	)
	modalities = models.ManyToManyField(
		"core.Modality",
		related_name="offices",
		blank=True,
		help_text="Therapy modalities offered at this office.",
	)
	conditions = models.ManyToManyField(
		"core.Condition",
		related_name="offices",
		blank=True,
		help_text="Conditions/presenting concerns treated at this office.",
	)

	# Display
	is_active = models.BooleanField(default=True)
	is_virtual = models.BooleanField(
		default=False,
		help_text="Mark as True for virtual/telehealth locations (no physical address).",
	)
	order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")

	class Meta:
		ordering = ["order", "name"]
		verbose_name = "Office location"
		verbose_name_plural = "Office locations"

	def __str__(self) -> str:
		return self.name

	def save(self, *args, **kwargs):
		if not self.slug:
			from django.utils.text import slugify
			self.slug = slugify(self.name)[:200]
		super().save(*args, **kwargs)

	@property
	def display_heading(self) -> str:
		return self.section_heading or self.name

	@property
	def full_address(self) -> str:
		"""Multi-line formatted address."""
		parts = [p for p in [self.address_line1, self.address_line2] if p]
		city_line = ", ".join(p for p in [self.address_city, self.address_state] if p)
		if self.address_zip:
			city_line = f"{city_line} {self.address_zip}".strip()
		if city_line:
			parts.append(city_line)
		return "\n".join(parts)

	@property
	def schema_address(self) -> dict:
		"""PostalAddress dict for JSON-LD schema."""
		return {
			"@type": "PostalAddress",
			"streetAddress": " ".join(p for p in [self.address_line1, self.address_line2] if p),
			"addressLocality": self.address_city,
			"addressRegion": self.address_state,
			"postalCode": self.address_zip,
			"addressCountry": "US",
		}

class Modality(Timestamped):
	"""A therapy modality offered at one or more office locations."""

	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=200, unique=True)
	description = models.TextField(blank=True)
	active = models.BooleanField(default=True)
	icon = models.CharField(max_length=100, blank=True, help_text="Optional icon class or emoji.")
	featured_image = models.ImageField(
		upload_to="modalities/",
		blank=True,
		null=True,
		help_text="Card background image for the listing page.",
	)

	class Meta:
		ordering = ["name"]
		verbose_name = "Modality"
		verbose_name_plural = "Modalities"

	def __str__(self) -> str:
		return self.name

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)[:200]
		super().save(*args, **kwargs)

	@property
	def card_background_url(self) -> str:
		if self.featured_image:
			try:
				return self.featured_image.url
			except ValueError:
				return ""
		return ""


class Condition(Timestamped):
	"""A mental health condition or presenting concern treated at one or more office locations."""

	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=200, unique=True)
	description = models.TextField(blank=True)
	active = models.BooleanField(default=True)
	icon = models.CharField(max_length=100, blank=True, help_text="Optional icon class or emoji.")
	featured_image = models.ImageField(
		upload_to="conditions/",
		blank=True,
		null=True,
		help_text="Card background image for the listing page.",
	)

	class Meta:
		ordering = ["name"]
		verbose_name = "Condition"
		verbose_name_plural = "Conditions"

	def __str__(self) -> str:
		return self.name

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)[:200]
		super().save(*args, **kwargs)

	@property
	def card_background_url(self) -> str:
		if self.featured_image:
			try:
				return self.featured_image.url
			except ValueError:
				return ""
		return ""


class ModalityContentBlock(models.Model):
	"""A heading + body content block attached to a Modality detail page."""

	modality = models.ForeignKey(
		Modality,
		on_delete=models.CASCADE,
		related_name="content_blocks",
	)
	order = models.PositiveSmallIntegerField(default=0, help_text="Lower numbers appear first.")
	heading = models.CharField(max_length=200, help_text="Section heading")
	body = models.TextField(help_text="Paragraph text for this section")

	class Meta:
		ordering = ["order"]

	def __str__(self):
		return self.heading


class ConditionContentBlock(models.Model):
	"""A heading + body content block attached to a Condition detail page."""

	condition = models.ForeignKey(
		Condition,
		on_delete=models.CASCADE,
		related_name="content_blocks",
	)
	order = models.PositiveSmallIntegerField(default=0, help_text="Lower numbers appear first.")
	heading = models.CharField(max_length=200, help_text="Section heading")
	body = models.TextField(help_text="Paragraph text for this section")

	class Meta:
		ordering = ["order"]

	def __str__(self):
		return self.heading


class Gone410URL(models.Model):
    """A URL path that should return 410 Gone, managed via the admin UI."""
    path = models.CharField(max_length=500, unique=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["path"]

    def __str__(self):
        return self.path