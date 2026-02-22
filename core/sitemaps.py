from django.contrib.sitemaps import Sitemap
from django.conf import settings
from django.urls import reverse, NoReverseMatch
from .models import Page
from blog.models import Post as BlogPost


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"
    protocol = 'https'

    def items(self):
        # Add named URL patterns for static views if any
        return [
            'home',
            'post_list',  # blog index
            'our_team',
            'about_us',
            'insurance',
            'contact_us',
            'faq',
        ]

    def location(self, item):
        try:
            return reverse(item)
        except NoReverseMatch:
            # Allow either namespaced or non-namespaced core URLs
            return reverse(f"core:{item}")

    def get_urls(self, page=1, site=None, protocol=None):
        urls = super().get_urls(page=page, site=site, protocol=protocol)
        base = getattr(settings, 'BASE_URL', '').rstrip('/')
        if base:
            for u in urls:
                u['location'] = f"{base}{u['location']}"
        return urls


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Page.objects.filter(status='publish')

    def location(self, obj):
        # Pages are routed by path in core.urls -> page_detail
        if not obj.path:
            return '/'
        return f"/{obj.path.strip('/')}" if obj.path else '/'

    def lastmod(self, obj):
        return obj.modified_at or obj.published_at

    def get_urls(self, page=1, site=None, protocol=None):
        urls = super().get_urls(page=page, site=site, protocol=protocol)
        base = getattr(settings, 'BASE_URL', '').rstrip('/')
        if base:
            for u in urls:
                u['location'] = f"{base}{u['location']}"
        return urls


class PostSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return BlogPost.published.all()

    def location(self, obj):
        return f"/blog/{obj.slug}/"

    def lastmod(self, obj):
        return obj.updated_at or obj.publish_at or obj.created_at

    def get_urls(self, page=1, site=None, protocol=None):
        urls = super().get_urls(page=page, site=site, protocol=protocol)
        base = getattr(settings, 'BASE_URL', '').rstrip('/')
        if base:
            for u in urls:
                u['location'] = f"{base}{u['location']}"
        return urls
