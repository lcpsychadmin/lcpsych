"""
core/slug_validation.py
-----------------------
Reusable slug validators for geo, service, and therapist objects.

Each function returns the matching model instance when the slug is valid,
or None when it is not (never raises).  The caller decides whether to
continue or return a 410 / 404 response.

Usage in a view::

    from core.slug_validation import validate_state, validate_service

    state = validate_state(state_slug)
    if state is None:
        return HttpResponse("Gone", status=410)
"""

from __future__ import annotations
from typing import Optional


def validate_state(state_slug: str) -> Optional["geo.models.GeoState"]:
    """Return the active GeoState for *state_slug*, or None."""
    from geo.models import GeoState
    try:
        return GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return None


def validate_location(
    state_slug: str,
    location_slug: str,
) -> Optional["geo.models.GeoLocation"]:
    """
    Return the active GeoLocation (city or county) for the given state + slug pair,
    or None.  Requires the state to be active too.
    """
    from geo.models import GeoState, GeoLocation
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return None
    try:
        return GeoLocation.objects.get(state=state, slug=location_slug, is_active=True)
    except GeoLocation.DoesNotExist:
        return None


def validate_county(
    state_slug: str,
    county_slug: str,
) -> Optional["geo.models.GeoLocation"]:
    """Return the active county GeoLocation, or None."""
    from geo.models import GeoState, GeoLocation
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return None
    try:
        return GeoLocation.objects.get(
            state=state,
            slug=county_slug,
            location_type=GeoLocation.COUNTY,
            is_active=True,
        )
    except GeoLocation.DoesNotExist:
        return None


def validate_city(
    state_slug: str,
    county_slug: str,
    city_slug: str,
) -> Optional["geo.models.GeoLocation"]:
    """
    Return the active city GeoLocation nested under the given county, or None.
    """
    from geo.models import GeoState, GeoLocation
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return None
    try:
        county = GeoLocation.objects.get(
            state=state,
            slug=county_slug,
            location_type=GeoLocation.COUNTY,
            is_active=True,
        )
    except GeoLocation.DoesNotExist:
        return None
    try:
        return GeoLocation.objects.get(
            state=state,
            slug=city_slug,
            county=county,
            is_active=True,
        )
    except GeoLocation.DoesNotExist:
        return None


def validate_region(region_slug: str) -> Optional["geo.models.GeoRegion"]:
    """Return the active GeoRegion for *region_slug*, or None."""
    from geo.models import GeoRegion
    try:
        return GeoRegion.objects.get(slug=region_slug, is_active=True)
    except GeoRegion.DoesNotExist:
        return None


def validate_service(service_slug: str) -> Optional["core.models.Service"]:
    """Return the Service for *service_slug* (any status), or None."""
    from core.models import Service
    try:
        return Service.objects.get(slug=service_slug)
    except Service.DoesNotExist:
        return None


def validate_therapist(therapist_slug: str) -> Optional["profiles.models.TherapistProfile"]:
    """Return the published TherapistProfile for *therapist_slug*, or None."""
    from profiles.models import TherapistProfile
    try:
        return TherapistProfile.objects.get(slug=therapist_slug, is_published=True)
    except TherapistProfile.DoesNotExist:
        return None
