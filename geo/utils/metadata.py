"""
Metadata utilities for geographic location pages.

Provides:
  get_location_metadata(state_slug, location_slug=None) -> dict
  get_breadcrumbs(state_slug, location_slug=None)       -> list[dict]

Both functions read from the GeoState / GeoLocation database tables.
"""

from __future__ import annotations
from typing import Optional
from django.conf import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _site_base() -> str:
    return (getattr(settings, "BASE_URL", "") or "").rstrip("/")


def _default_og_image(base: str) -> str:
    return (
        f"{base}/static/vendor/lcpsych/wp-content/uploads/2017/08/LC_logo_color.png"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_location_metadata(
    state_slug: str,
    location_slug: Optional[str] = None,
) -> dict:
    """
    Return a context dict suitable for passing directly to a Django view:

      seo_title       – <title> tag value
      seo_description – meta description
      canonical_url   – absolute canonical URL
      og_image_url    – Open Graph image URL
    """
    from geo.models import GeoState, GeoLocation

    base = _site_base()
    default_og = _default_og_image(base)

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return {}

    if location_slug is None:
        return {
            "seo_title": state.seo_title
            or f"Therapists in {state.name} | L+C Psychological Services",
            "seo_description": state.seo_description or "",
            "canonical_url": f"{base}/{state_slug}/",
            "og_image_url": state.og_image_url or default_og,
        }

    try:
        location = GeoLocation.objects.get(
            state=state, slug=location_slug, is_active=True
        )
    except GeoLocation.DoesNotExist:
        return {}

    return {
        "seo_title": location.seo_title
        or f"Therapists in {location.name}, {state.abbreviation} | L+C Psychological Services",
        "seo_description": location.seo_description or "",
        "canonical_url": f"{base}/{state_slug}/{location_slug}/",
        "og_image_url": location.og_image_url or default_og,
    }


def get_region_metadata(region_slug: str) -> dict:
    """
    Return a context dict for a GeoRegion page:

      seo_title       – <title> tag value
      seo_description – meta description
      canonical_url   – absolute canonical URL
      og_image_url    – Open Graph image URL
    """
    from geo.models import GeoRegion

    base = _site_base()
    default_og = _default_og_image(base)

    try:
        region = GeoRegion.objects.get(slug=region_slug, is_active=True)
    except GeoRegion.DoesNotExist:
        return {}

    return {
        "seo_title": region.seo_title
        or f"Therapists in {region.name} | L+C Psychological Services",
        "seo_description": region.seo_description or "",
        "canonical_url": f"{base}/regions/{region_slug}/",
        "og_image_url": region.og_image_url or default_og,
    }


def get_breadcrumbs(
    state_slug: str,
    location_slug: Optional[str] = None,
) -> list[dict]:
    """
    Return an ordered list of breadcrumb dicts:

      [{"label": "Home", "url": "/"}, {"label": "Kentucky", "url": "/kentucky/"}, ...]
    """
    from geo.models import GeoState, GeoLocation

    crumbs: list[dict] = [{"label": "Home", "url": "/"}]

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return crumbs

    crumbs.append({"label": state.name, "url": f"/{state_slug}/"})

    if location_slug:
        try:
            location = GeoLocation.objects.get(
                state=state, slug=location_slug, is_active=True
            )
            crumbs.append(
                {"label": location.name, "url": f"/{state_slug}/{location_slug}/"}
            )
        except GeoLocation.DoesNotExist:
            pass

    return crumbs

