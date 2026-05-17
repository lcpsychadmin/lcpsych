"""
Sitemaps for therapist profile pages.

  TherapistSitemap         — /therapists/<slug>/
  TherapistServiceSitemap  — /therapists/<slug>/services/<service_slug>/
  TherapistStateSitemap    — /therapists/<slug>/<state_slug>/
  TherapistAreaSitemap     — /therapists/<slug>/<state_slug>/<location_slug>/
                             /therapists/<slug>/<state_slug>/<county_slug>/<city_slug>/
"""

from django.contrib.sitemaps import Sitemap
from profiles.models import TherapistProfile
from geo.utils.availability import get_locations_for_therapist


class TherapistSitemap(Sitemap):
    priority = 0.7
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return TherapistProfile.objects.filter(is_published=True).order_by("slug")

    def location(self, item):
        return f"/therapists/{item.slug}/"

    def lastmod(self, item):
        return item.updated_at


class TherapistServiceSitemap(Sitemap):
    """One entry per (therapist, service) pair."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        pairs = []
        therapists = TherapistProfile.objects.filter(is_published=True).prefetch_related("services").order_by("slug")
        for therapist in therapists:
            for service in therapist.services.all():
                pairs.append((therapist, service))
        return pairs

    def location(self, item):
        therapist, service = item
        return f"/therapists/{therapist.slug}/services/{service.slug}/"


class TherapistStateSitemap(Sitemap):
    """One entry per (therapist, state) pair where therapist has a location in that state."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        pairs = []
        therapists = TherapistProfile.objects.filter(is_published=True).order_by("slug")
        for therapist in therapists:
            locations = get_locations_for_therapist(therapist).select_related("state")
            seen_states = set()
            for loc in locations:
                if loc.state.slug not in seen_states:
                    seen_states.add(loc.state.slug)
                    pairs.append((therapist, loc.state))
        return pairs

    def location(self, item):
        therapist, state = item
        return f"/therapists/{therapist.slug}/{state.slug}/"

    def lastmod(self, item):
        therapist, _state = item
        return therapist.updated_at


class TherapistAreaSitemap(Sitemap):
    """One entry per (therapist, geo_location) pair."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        pairs = []
        therapists = TherapistProfile.objects.filter(is_published=True).order_by("slug")
        for therapist in therapists:
            locations = get_locations_for_therapist(therapist).select_related("state", "county")
            for loc in locations:
                pairs.append((therapist, loc))
        return pairs

    def location(self, item):
        therapist, loc = item
        if loc.location_type == "city" and loc.county_id:
            return f"/therapists/{therapist.slug}/{loc.state.slug}/{loc.county.slug}/{loc.slug}/"
        return f"/therapists/{therapist.slug}/{loc.state.slug}/{loc.slug}/"

    def lastmod(self, item):
        therapist, _loc = item
        return therapist.updated_at
