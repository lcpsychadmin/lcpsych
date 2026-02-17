from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.template.loader import select_template
from django.utils.safestring import mark_safe
from django.utils.http import urlencode
import re
from pathlib import Path
from .forms import JoinOurTeamForm
from .models import Page, Post, PublishStatus, Service, StaticPageSEO, ContactInfo
from profiles.models import TherapistProfile


def _build_therapist_cards(profiles):
	cards = []
	for profile in profiles:
		focus_names = [focus.name for focus in profile.client_focuses.all()]
		tagline_items = focus_names[:2]
		if profile.license_type:
			license_label = (profile.license_type.description or '').strip()
			license_name = license_label or profile.license_type.name
		else:
			license_name = ''

		top_service_titles = [service.title for service in profile.top_services.all()]
		service_titles = top_service_titles or [service.title for service in profile.services.all()]

		cards.append({
			'profile': profile,
			'title': license_name,
			'license_name': license_name,
			'tagline': ' • '.join(tagline_items) if tagline_items else '',
			'tagline_items': tagline_items,
			'photo_url': profile.photo.url if profile.photo else '',
			'focuses': focus_names,
			'services': service_titles[:3],
			'slug': profile.slug,
			'accepts_new_clients': profile.accepts_new_clients,
		})

	return cards


def _static_seo_context(
	slug: str,
	fallback_title: str,
	fallback_description: str,
	page_name: str,
	fallback_keywords: str = "",
	fallback_og_image_url: str | None = None,
) -> dict:
	entry = StaticPageSEO.objects.filter(slug=slug).first()
	seo_title = entry.seo_title if entry and entry.seo_title else fallback_title
	seo_description = entry.seo_description if entry and entry.seo_description else fallback_description
	seo_keywords = entry.seo_keywords if entry else fallback_keywords
	og_image_url = fallback_og_image_url
	if entry:
		if getattr(entry, 'seo_image_file', None):
			try:
				og_image_url = entry.seo_image_file.url
			except ValueError:
				og_image_url = None
		if not og_image_url and entry.seo_image_url:
			og_image_url = entry.seo_image_url
	page_heading = entry.page_name if entry and entry.page_name else page_name
	return {
		'seo_title': seo_title,
		'seo_description': seo_description,
		'seo_keywords': seo_keywords,
		'og_type': 'website',
		'og_image_url': og_image_url,
		'page_title': page_heading,
	}


def _published_therapists_queryset():
    return (
        TherapistProfile.objects.filter(is_published=True)
		.select_related('license_type')
		.prefetch_related('client_focuses', 'services', 'top_services')
        .order_by('last_name', 'first_name')
    )


def home(request):
	# Render the home page and, if available, apply SEO overrides from the Page with path='home'
	seo_ctx = {}
	fallback_title = 'L+C Psychological Services'
	fallback_description = 'Therapy and psychological services in Northern Kentucky to help you reconnect with life and relationships.'
	fallback_keywords = ''
	fallback_og_image_url = None
	try:
		page = Page.objects.get(path='home')
		from django.utils.html import strip_tags

		def _truncate(s, n=155):
			s = (s or '').strip()
			return (s[: n - 1] + '…') if len(s) > n else s

		fallback_title = page.seo_title or page.title
		fallback_description = page.seo_description or _truncate(strip_tags(page.excerpt_html or ''))
		fallback_keywords = page.seo_keywords
		fallback_og_image_url = page.seo_image_url or None
	except Page.DoesNotExist:
		pass

	seo_ctx = _static_seo_context(
		'home',
		fallback_title,
		fallback_description,
		'Home',
		fallback_keywords=fallback_keywords,
		fallback_og_image_url=fallback_og_image_url,
	)
	# Services cards for homepage: only published, ordered
	services = list(
		Service.objects.filter(status=PublishStatus.PUBLISH)
		.select_related('page')
		.order_by('order', 'title')
	)

	therapists = _build_therapist_cards(_published_therapists_queryset())

	ctx = {**seo_ctx, 'services': services, 'therapists': therapists}
	return render(request, 'home.html', ctx)


def location_xml(request):
	"""Return location.xml populated from ContactInfo for local SEO/NAP."""
	contact = ContactInfo.objects.order_by('id').first()
	if not contact:
		contact = ContactInfo.objects.create()
	site_base = getattr(settings, 'BASE_URL', '').rstrip('/') or request.build_absolute_uri('/').rstrip('/')
	content = select_template(['location.xml']).render({'contact': contact, 'site_base': site_base}, request=request)
	return HttpResponse(content, content_type='application/xml')


def our_team(request):
	profiles = (
		TherapistProfile.objects.filter(is_published=True)
		.select_related('license_type', 'user')
		.prefetch_related('client_focuses', 'services', 'top_services')
	)

	query = (request.GET.get('q') or '').strip()
	if query:
		profiles = profiles.filter(
			Q(first_name__icontains=query)
			| Q(last_name__icontains=query)
			| Q(user__first_name__icontains=query)
			| Q(user__last_name__icontains=query)
			| Q(license_type__name__icontains=query)
			| Q(services__title__icontains=query)
			| Q(client_focuses__name__icontains=query)
		)

	new_only = request.GET.get('new') == '1'
	if new_only:
		profiles = profiles.filter(accepts_new_clients=True)

	profiles = profiles.distinct()

	context = {
		**_static_seo_context(
			'our-team',
			'Our Team | L+C Psychological Services',
			'Meet the licensed psychologists and therapists at L+C Psychological Services serving Northern Kentucky and Kentucky telehealth clients.',
			'Our Team',
		),
		'profiles': profiles,
		'query': query,
		'new_only': new_only,
	}
	return render(request, 'profiles/profile_list.html', context)


def about_us(request):
	context = _static_seo_context(
		'about-us',
		'About L+C Psychological Services',
		'Learn how L+C Psychological Services supports clients with compassionate therapy, psychological testing, and a mission built on genuine connection.',
		'About Us',
	)
	return render(request, 'pages/about_us.html', context)


def insurance(request):
	context = _static_seo_context(
		'insurance',
		'Insurance & Payment Options | L+C Psych',
		'Review accepted insurance plans, Medicare coverage, and payment details for therapy and psychological services at L+C Psychological Services.',
		'Insurance & Payment',
	)
	return render(request, 'pages/insurance.html', context)


def contact_us(request):
	context = _static_seo_context(
		'contact-us',
		'Contact L+C Psychological Services',
		'Get directions to our Florence, Kentucky office, review hours, and contact L+C Psychological Services by phone, fax, or email.',
		'Contact Us',
	)
	return render(request, 'pages/contact_us.html', context)


def faq(request):
	context = _static_seo_context(
		'faq',
		'Therapy FAQs | L+C Psych',
		'Find answers to common questions about therapy costs, insurance coverage, first appointments, and what to expect at L+C Psychological Services.',
		'Frequently Asked Questions',
	)
	return render(request, 'pages/faq.html', context)


def appointments(request):
	portal_base = getattr(settings, "THERAPY_PORTAL_BASE_URL", "https://www.therapyportal.com/p/lcpsych41042").rstrip("/")
	availability_url = f"{portal_base}/appointments/availability/"
	request_base = f"{portal_base}/appointments/requests/"

	new_patient_params = {
		"isExistingPatient": "false",
	}
	new_patient_availability_url = f"{availability_url}?{urlencode(new_patient_params)}"

	context = {
		**_static_seo_context(
			'appointments',
			'Schedule an Appointment | L+C Psych',
			'Choose your clinician and request a time online. Existing clients can head straight to the client portal.',
			'Appointments',
		),
		"portal_base": portal_base,
		"availability_url": availability_url,
		"new_patient_availability_url": new_patient_availability_url,
		"request_base_url": request_base,
	}
	return render(request, 'pages/appointments.html', context)


def service_detail(request, slug: str):
	service = get_object_or_404(
		Service.objects.select_related('page').prefetch_related(
			'therapists__license_type',
			'therapists__client_focuses',
		),
		slug=slug,
		status=PublishStatus.PUBLISH,
	)
	from django.utils.html import strip_tags

	def _truncate(s, n=155):
		s = (s or '').strip()
		return (s[: n - 1] + '…') if len(s) > n else s

	body_html = service.body_html
	intro_text = service.hero_intro
	if intro_text:
		description_source = intro_text
	elif body_html:
		description_source = strip_tags(body_html)
	else:
		description_source = ''
	seo_description = _truncate(description_source)
	seo_title = service.hero_title
	other_services = (
		Service.objects.filter(status=PublishStatus.PUBLISH)
		.exclude(pk=service.pk)
		.order_by('order', 'title')[:6]
	)
	therapists_qs = (
		service.therapists.filter(is_published=True)
		.select_related('license_type')
		.prefetch_related('client_focuses')
		.order_by('last_name', 'first_name')
	)
	therapists = _build_therapist_cards(therapists_qs)
	context = {
		'service': service,
		'body_html': mark_safe(body_html),
		'hero_intro': intro_text,
		'seo_title': seo_title,
		'seo_description': seo_description,
		'og_image_url': service.seo_image_url,
		'other_services': other_services,
		'therapists': therapists,
	}
	return render(request, 'core/service_detail.html', context)


def page_detail(request, path: str):
	page = get_object_or_404(Page, path=path.strip('/'))
	# Gate unpublished content: allow staff to preview drafts; 404 for others
	if page.status != PublishStatus.PUBLISH and not request.user.is_staff:
		raise Http404()
	# Prepare per-page SEO overrides
	seo_title = page.seo_title or page.title
	# Prefer explicit seo_description; else derive from excerpt_html (strip tags lightly)
	from django.utils.html import strip_tags
	derived_desc = strip_tags(page.excerpt_html).strip()
	# SERP-friendly truncation ~155 chars
	def _truncate(s, n=155):
		s = (s or '').strip()
		return (s[: n - 1] + '…') if len(s) > n else s
	seo_description = page.seo_description or _truncate(derived_desc)
	# Prefer a template based on path/slug if present; else fall back to generic
	candidates = [
		f"pages/{page.path}.html",
		f"pages/{page.slug}.html",
		"core/page_detail.html",
	]
	tpl = select_template(candidates)
	# OG type and last modified
	lastmod_dt = page.modified_at or page.published_at or page.updated
	lastmod_iso = lastmod_dt.isoformat() if lastmod_dt else None
	ctx = {
		'page': page,
		'title': page.title,
		'content_html': mark_safe(page.content_html),
		'seo_title': seo_title,
		'seo_description': seo_description,
		'seo_keywords': page.seo_keywords,
		'og_image_url': page.seo_image_url or None,
		'og_type': 'article',
		'lastmod_iso': lastmod_iso,
	}
	# Service detail enhancements: attach related Service and image
	service_obj = None
	service_image_url = None
	if page.path.startswith('services/') and page.path != 'services':
		try:
			service_obj = Service.objects.filter(page=page).order_by('order', 'title').first()
		except Exception:
			service_obj = None
		if service_obj and getattr(service_obj, 'image_url', None):
			service_image_url = service_obj.image_url
		ctx['service'] = service_obj
		ctx['service_image_url'] = service_image_url
		# If no explicit SEO image, prefer the service image for social previews
		if not ctx.get('og_image_url') and service_image_url:
			ctx['og_image_url'] = service_image_url
	# If this is the Services index page, provide the services queryset for the template
	if page.path == 'services':
		from django.db.models import Q
		q = (request.GET.get('q') or '').strip()
		svc_qs = Service.objects.filter(status=PublishStatus.PUBLISH, page__status=PublishStatus.PUBLISH)
		if q:
			svc_qs = svc_qs.filter(
				Q(title__icontains=q) |
				Q(excerpt__icontains=q) |
				Q(page__title__icontains=q)
			)
		services = list(svc_qs.select_related('page').order_by('order', 'title'))
		ctx['services'] = services
	return HttpResponse(tpl.render(ctx, request))


def post_list(request):
	# Show only published posts to public; staff can see drafts in list
	qs = Post.objects.all()
	if not request.user.is_staff:
		qs = qs.filter(status=PublishStatus.PUBLISH)
	posts = qs[:50]
	return render(request, 'core/post_list.html', {
		'posts': posts,
	})


def post_detail(request, slug: str):
	post = get_object_or_404(Post, slug=slug)
	if post.status != PublishStatus.PUBLISH and not request.user.is_staff:
		raise Http404()
	from django.utils.html import strip_tags
	def _truncate(s, n=155):
		s = (s or '').strip()
		return (s[: n - 1] + '…') if len(s) > n else s
	derived_desc = strip_tags(post.excerpt_html or post.content_html).strip()
	seo_title = post.seo_title or post.title
	seo_description = post.seo_description or _truncate(derived_desc)
	candidates = [
		f"posts/{post.slug}.html",
		"core/post_detail.html",
	]
	tpl = select_template(candidates)
	# OG type and last modified
	lastmod_dt = post.modified_at or post.published_at or post.updated
	lastmod_iso = lastmod_dt.isoformat() if lastmod_dt else None
	ctx = {
		'post': post,
		'content_html': mark_safe(post.content_html),
		'seo_title': seo_title,
		'seo_description': seo_description,
		'seo_keywords': post.seo_keywords,
		'og_image_url': post.seo_image_url or None,
		'og_type': 'article',
		'lastmod_iso': lastmod_iso,
	}
	return HttpResponse(tpl.render(ctx, request))


@require_POST
def join_our_team(request):
	"""Persist Join Our Team submissions and bounce back with a flash message."""
	form = JoinOurTeamForm(request.POST, request.FILES)
	if form.is_valid():
		submission = form.save(commit=False)
		submission.user_agent = request.META.get("HTTP_USER_AGENT", "")
		submission.save()
		messages.success(request, "Thanks for reaching out—your info was received.")
	else:
		messages.error(request, "Please check your details and try again.")

	redirect_target = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
	return redirect(redirect_target)


def search(request):
	"""Simple site search across Page and Post titles and content_html."""
	from django.db.models import Q
	q = (request.GET.get('q') or '').strip()
	pages = posts = []
	if q:
		pages_qs = Page.objects.filter(
			Q(title__icontains=q) | Q(content_html__icontains=q)
		)
		posts_qs = Post.objects.filter(
			Q(title__icontains=q) | Q(content_html__icontains=q)
		)
		if not request.user.is_staff:
			pages_qs = pages_qs.filter(status=PublishStatus.PUBLISH)
			posts_qs = posts_qs.filter(status=PublishStatus.PUBLISH)
		pages = list(pages_qs[:20])
		posts = list(posts_qs[:20])
	ctx = {
		'q': q,
		'pages': pages,
		'posts': posts,
		'seo_title': f"Search results for '{q}'" if q else "Search",
		'seo_description': "Search pages and articles from L+C Psychological Services.",
		'og_type': 'website',
	}
	return render(request, 'core/search.html', ctx)

# Create your views here.


def import_preview(request):
	"""
	Serve the copied lcpsych.html as-is but rewrite WordPress upload URLs to
	local /media basenames so downloaded assets display. Intended for design
	parity comparison only.
	"""
	src_path = Path(settings.BASE_DIR) / 'lcpsych.html'
	if not src_path.exists():
		raise Http404('lcpsych.html not found at project root')
	html = src_path.read_text(encoding='utf-8')

	# Rewrite wp uploads to local media by basename
	def _rewrite_uploads(match: re.Match) -> str:
		full = match.group(0)
		url = match.group('url')
		# Extract basename
		basename = url.rstrip('/').split('/')[-1]
		if basename:
			return full.replace(url, f"/media/{basename}")
		return full

	pattern = re.compile(r"(?P<prefix>(?:src|href)=[\"'])(?P<url>https?://(?:www\.)?lcpsych\.com/wp-content/uploads/[^\"']+)(?P<suffix>[\"'])",
						 re.IGNORECASE)
	html = pattern.sub(lambda m: m.group('prefix') + f"/media/{m.group('url').rstrip('/').split('/')[-1]}" + m.group('suffix'), html)

	# Optional: normalize same-site anchor links to local anchors
	html = re.sub(r"href=\"https?://(?:www\.)?lcpsych\.com/(?:#([^\"']+))\"", r'href="#\1"', html, flags=re.IGNORECASE)

	return HttpResponse(html, content_type='text/html')


@csrf_exempt
def cloudflare_rum(request):
	"""No-op endpoint to absorb Cloudflare RUM POSTs without CSRF.

	Accepts POSTs at /cdn-cgi/rum and returns 204 No Content to avoid log noise.
	"""
	if request.method == 'POST':
		return HttpResponse(status=204)
	# For any other method, return 405 to indicate it's not supported
	return HttpResponse(status=405)


def cloudflare_email_decode_js(request):
	"""Serve a minimal stub for Cloudflare email decode script to avoid 404 noise.

	This script is often injected by copied markup; we don't need its behavior
	locally, so a harmless no-op is sufficient.
	"""
	js = (
		"/*! Cloudflare email-decode stub */\n"
		"// Intentionally left blank for local environment.\n"
	)
	resp = HttpResponse(js, content_type='application/javascript')
	# Cache briefly to reduce requests during dev
	resp['Cache-Control'] = 'public, max-age=300'
	return resp


@csrf_exempt
def wp_admin_ajax_stub(request):
	"""Local stub for WordPress admin-ajax.php to avoid external calls.

	Returns a minimal 204 for POST and empty JSON for GET.
	"""
	if request.method == 'POST':
		return HttpResponse(status=204)
	return HttpResponse('{"ok": true}', content_type='application/json')


@csrf_exempt
def wp_json_stub(request):
	"""Local stub for WordPress REST API endpoints used by copied scripts."""
	return HttpResponse('{"name": "Local WP JSON Stub"}', content_type='application/json')
