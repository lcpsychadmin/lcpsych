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

from functools import lru_cache

from django.contrib.sitemaps import Sitemap
from geo.models import GeoLocation, GeoRegion, GeoState
from geo.utils.availability import get_therapists_for_area_and_service


@lru_cache(maxsize=1)
def _latest_therapist_date():
    """Return the most recent TherapistProfile.updated_at, cached per process lifetime.

    Geo models don't have their own timestamps, so we use the latest therapist
    update as a proxy for 'something on these pages changed'. Google uses this
    to decide whether to re-crawl a sitemap section.
    """
    from profiles.models import TherapistProfile

    return (
        TherapistProfile.objects.filter(is_published=True)
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )


class GeoStateSitemap(Sitemap):
    priority = 0.7
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return GeoState.objects.filter(is_active=True).order_by("name")

    def location(self, item: GeoState) -> str:
        return f"/{item.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoRegionSitemap(Sitemap):
    """One entry per active region."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return GeoRegion.objects.filter(is_active=True).order_by("name")

    def location(self, item: GeoRegion) -> str:
        return item.get_url_path()

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        return _latest_therapist_date()


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

    def lastmod(self, item):
        _region, therapist = item
        return therapist.updated_at


class GeoRegionModalitySitemap(Sitemap):
    """One entry per (region, modality) pair where at least one active office in the region offers that modality."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Modality

        pairs = []
        regions = GeoRegion.objects.filter(is_active=True).prefetch_related(
            "offices"
        ).order_by("slug")
        modalities = Modality.objects.filter(active=True).order_by("slug")
        for region in regions:
            offices_in_region = region.offices.filter(
                is_active=True,
                therapists__is_published=True,
            ).distinct()
            for modality in modalities:
                if offices_in_region.filter(modalities=modality).exists():
                    pairs.append((region, modality))
        return pairs

    def location(self, item):
        region, modality = item
        return f"/regions/{region.slug}/modalities/{modality.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoRegionConditionSitemap(Sitemap):
    """One entry per (region, condition) pair where at least one active office in the region treats that condition."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Condition

        pairs = []
        regions = GeoRegion.objects.filter(is_active=True).prefetch_related(
            "offices"
        ).order_by("slug")
        conditions = Condition.objects.filter(active=True).order_by("slug")
        for region in regions:
            offices_in_region = region.offices.filter(
                is_active=True,
                therapists__is_published=True,
            ).distinct()
            for condition in conditions:
                if offices_in_region.filter(conditions=condition).exists():
                    pairs.append((region, condition))
        return pairs

    def location(self, item):
        region, condition = item
        return f"/regions/{region.slug}/conditions/{condition.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoStateModalitySitemap(Sitemap):
    """One entry per (state, modality) pair where at least one published therapist offers that modality in the state."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Modality
        from geo.utils.availability import get_therapists_for_area_and_modality

        pairs = []
        states = GeoState.objects.filter(is_active=True).order_by("slug")
        modalities = Modality.objects.filter(active=True).order_by("slug")
        for state in states:
            for modality in modalities:
                if get_therapists_for_area_and_modality(state, modality).exists():
                    pairs.append((state, modality))
        return pairs

    def location(self, item):
        state, modality = item
        return f"/{state.slug}/modalities/{modality.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoStateConditionSitemap(Sitemap):
    """One entry per (state, condition) pair where at least one published therapist treats that condition in the state."""

    priority = 0.65
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Condition
        from geo.utils.availability import get_therapists_for_area_and_condition

        pairs = []
        states = GeoState.objects.filter(is_active=True).order_by("slug")
        conditions = Condition.objects.filter(active=True).order_by("slug")
        for state in states:
            for condition in conditions:
                if get_therapists_for_area_and_condition(state, condition).exists():
                    pairs.append((state, condition))
        return pairs

    def location(self, item):
        state, condition = item
        return f"/{state.slug}/conditions/{condition.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoLocationModalitySitemap(Sitemap):
    """One entry per (location, modality) pair where at least one published therapist offers that modality there."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Modality
        from geo.utils.availability import get_therapists_for_area_and_modality

        pairs = []
        locations = (
            GeoLocation.objects.filter(is_active=True)
            .select_related("state", "county")
            .order_by("state__slug", "slug")
        )
        modalities = Modality.objects.filter(active=True).order_by("slug")
        for location in locations:
            for modality in modalities:
                if get_therapists_for_area_and_modality(location, modality).exists():
                    pairs.append((location, modality))
        return pairs

    def location(self, item):
        loc, modality = item
        return f"{loc.get_url_path()}modalities/{modality.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()


class GeoLocationConditionSitemap(Sitemap):
    """One entry per (location, condition) pair where at least one published therapist treats that condition there."""

    priority = 0.6
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        from core.models import Condition
        from geo.utils.availability import get_therapists_for_area_and_condition

        pairs = []
        locations = (
            GeoLocation.objects.filter(is_active=True)
            .select_related("state", "county")
            .order_by("state__slug", "slug")
        )
        conditions = Condition.objects.filter(active=True).order_by("slug")
        for location in locations:
            for condition in conditions:
                if get_therapists_for_area_and_condition(location, condition).exists():
                    pairs.append((location, condition))
        return pairs

    def location(self, item):
        loc, condition = item
        return f"{loc.get_url_path()}conditions/{condition.slug}/"

    def lastmod(self, item):
        return _latest_therapist_date()
