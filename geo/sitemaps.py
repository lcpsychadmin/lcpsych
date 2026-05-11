"""
Sitemaps for geographic location pages.

Three separate sitemap classes let search engines discover all geo pages:
  GeoStateSitemap          — one entry per active state  (e.g. /kentucky/)
  GeoCitySitemap           — one entry per active city   (e.g. /kentucky/florence/)
  GeoCountySitemap         — one entry per active county (e.g. /kentucky/boone-county/)
  GeoStateServiceSitemap   — state × service intersectional pages
  GeoLocationServiceSitemap — city/county × service intersectional pages

All data is read live from the GeoState / GeoLocation database tables so that
adding a location in the admin automatically adds it to the sitemap.

Register all five in lcpsych/urls.py under the 'sitemaps' dict that is
passed to Django's built-in sitemap view.
"""

from django.contrib.sitemaps import Sitemap
from geo.models import GeoLocation, GeoRegion, GeoState
from geo.utils.availability import get_therapists_for_area_and_service


class GeoStateSitemap(Sitemap):
    priority = 0.7
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return GeoState.objects.filter(is_active=True).order_by("name")

    def location(self, item: GeoState) -> str:
        return f"/{item.slug}/"


class GeoCitySitemap(Sitemap):
    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return (
            GeoLocation.objects.filter(
                is_active=True, location_type=GeoLocation.CITY
            )
            .select_related("state", "county")
            .order_by("state__slug", "slug")
        )

    def location(self, item: GeoLocation) -> str:
        return item.get_url_path()


class GeoCountySitemap(Sitemap):
    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return (
            GeoLocation.objects.filter(
                is_active=True, location_type=GeoLocation.COUNTY
            )
            .select_related("state")
            .order_by("state__slug", "slug")
        )

    def location(self, item: GeoLocation) -> str:
        return f"/{item.state.slug}/{item.slug}/"


class GeoStateServiceSitemap(Sitemap):
    """One entry per (state, service) pair where at least one therapist offers that service in the state."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Service

        pairs = []
        states = GeoState.objects.filter(is_active=True).order_by("slug")
        services = Service.objects.all().order_by("slug")
        for state in states:
            for service in services:
                if get_therapists_for_area_and_service(state, service).exists():
                    pairs.append((state, service))
        return pairs

    def location(self, item):
        state, service = item
        return f"/{state.slug}/services/{service.slug}/"


class GeoLocationServiceSitemap(Sitemap):
    """One entry per (city/county, service) pair where at least one therapist offers that service there."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Service

        pairs = []
        locations = (
            GeoLocation.objects.filter(is_active=True)
            .select_related("state", "county")
            .order_by("state__slug", "slug")
        )
        services = Service.objects.all().order_by("slug")
        for location in locations:
            for service in services:
                if get_therapists_for_area_and_service(location, service).exists():
                    pairs.append((location, service))
        return pairs

    def location(self, item):
        location, service = item
        return f"{location.get_url_path()}services/{service.slug}/"


class GeoRegionSitemap(Sitemap):
    """One entry per active region."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return GeoRegion.objects.filter(is_active=True).order_by("name")

    def location(self, item: GeoRegion) -> str:
        return item.get_url_path()


class GeoRegionServiceSitemap(Sitemap):
    """One entry per (region, service) pair where at least one therapist offers that service in the region."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Service
        from profiles.models import TherapistProfile

        pairs = []
        regions = GeoRegion.objects.filter(is_active=True).order_by("slug")
        services = Service.objects.filter(
            therapists__is_published=True
        ).distinct().order_by("slug")
        for region in regions:
            for service in services:
                pairs.append((region, service))
        return pairs

    def location(self, item):
        region, service = item
        return f"/regions/{region.slug}/services/{service.slug}/"


class GeoRegionTherapistSitemap(Sitemap):
    """One entry per (region, therapist) pair where the therapist is in the region."""

    priority = 0.55
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from profiles.models import TherapistProfile

        pairs = []
        regions = GeoRegion.objects.filter(is_active=True).order_by("slug")
        therapists = TherapistProfile.objects.filter(is_published=True).order_by("slug")
        for region in regions:
            for therapist in therapists:
                pairs.append((region, therapist))
        return pairs

    def location(self, item):
        region, therapist = item
        return f"/regions/{region.slug}/therapists/{therapist.slug}/"

