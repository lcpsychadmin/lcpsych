"""Utilities for OfficeLocation queries."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import OfficeLocation


def get_offices():
    """Return all active *physical* OfficeLocation objects ordered by `order`, then `name`."""
    from core.models import OfficeLocation
    return OfficeLocation.objects.filter(is_active=True, is_virtual=False).order_by("order", "name")


def get_office_by_slug(slug: str) -> "OfficeLocation":
    """Return an active OfficeLocation by slug, or raise OfficeLocation.DoesNotExist."""
    from core.models import OfficeLocation
    return OfficeLocation.objects.get(slug=slug, is_active=True)


def get_therapists_for_office(office: "OfficeLocation"):
    """Return published TherapistProfiles assigned to this office."""
    return office.therapists.filter(is_published=True).order_by("last_name", "first_name")


def get_services_for_office(office: "OfficeLocation"):
    """Return Services offered by any therapist at this office."""
    from core.models import Service, PublishStatus
    therapist_ids = office.therapists.filter(is_published=True).values_list("id", flat=True)
    return (
        Service.objects.filter(
            status=PublishStatus.PUBLISH,
            therapists__id__in=therapist_ids,
        )
        .distinct()
        .order_by("order", "title")
    )


def get_areas_served_by_office(office: "OfficeLocation") -> dict:
    """Return a dict with 'states', 'counties', 'cities', and 'locations' querysets for this office."""
    locations = office.geo_locations.filter(is_active=True).order_by("state__name", "name")
    return {
        "states": office.geo_states.filter(is_active=True).order_by("name"),
        "counties": locations.filter(location_type="county"),
        "cities": locations.filter(location_type="city"),
        "locations": locations,
    }


def get_office_schema(office: "OfficeLocation", request=None) -> dict:
    """Return a LocalBusiness JSON-LD schema dict for this office."""
    from django.conf import settings

    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    if request and not base_url:
        base_url = request.build_absolute_uri("/").rstrip("/")

    schema: dict = {
        "@context": "https://schema.org",
        "@type": "MedicalBusiness",
        "name": "L+C Psychological Services",
        "description": "Outpatient mental health therapy serving Cincinnati and Northern Kentucky.",
        "url": base_url or "https://lcpsych.com",
        "branchOf": {"@type": "LocalBusiness", "name": "L+C Psychological Services"},
        "location": {
            "@type": "Place",
            "name": office.name,
            "address": office.schema_address,
        },
    }

    if office.phone_number:
        schema["telephone"] = office.phone_number
    if office.email_address:
        schema["email"] = office.email_address
    if office.office_hours:
        # Convert "Mon – Thurs: 8AM – 9PM" lines into schema hours spec where possible.
        schema["openingHours"] = [line.strip() for line in office.office_hours.splitlines() if line.strip()]
    if base_url:
        schema["url"] = f"{base_url}/contact-us/{office.slug}/"

    return schema


# ---------------------------------------------------------------------------
# Telehealth helpers
# ---------------------------------------------------------------------------

def get_telehealth_office():
    """Return the active Telehealth OfficeLocation, or raise OfficeLocation.DoesNotExist."""
    from core.models import OfficeLocation
    return (
        OfficeLocation.objects
        .prefetch_related("therapists", "geo_states")
        .get(slug="telehealth", is_active=True, is_virtual=True)
    )


def get_therapists_for_telehealth(office=None):
    """Return published TherapistProfiles assigned to the telehealth office."""
    if office is None:
        office = get_telehealth_office()
    return office.therapists.filter(is_published=True).select_related("license_type").order_by("last_name", "first_name")


def get_services_for_telehealth(office=None):
    """Return Services offered by any therapist at the telehealth office."""
    from core.models import Service, PublishStatus
    if office is None:
        office = get_telehealth_office()
    therapist_ids = office.therapists.filter(is_published=True).values_list("id", flat=True)
    return (
        Service.objects.filter(
            status=PublishStatus.PUBLISH,
            therapists__id__in=therapist_ids,
        )
        .distinct()
        .order_by("order", "title")
    )


def get_telehealth_schema(office, request=None) -> dict:
    """Return a JSON-LD schema dict for the Telehealth virtual location."""
    from django.conf import settings

    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    if request and not base_url:
        base_url = request.build_absolute_uri("/").rstrip("/")

    schema: dict = {
        "@context": "https://schema.org",
        "@type": "MedicalBusiness",
        "name": "L+C Psychological Services — Telehealth",
        "description": "Online therapy available throughout Kentucky, Ohio, and Indiana via telehealth.",
        "url": f"{base_url}/telehealth/" if base_url else "https://lcpsych.com/telehealth/",
        "branchOf": {"@type": "LocalBusiness", "name": "L+C Psychological Services"},
    }
    if office.phone_number:
        schema["telephone"] = office.phone_number
    if office.email_address:
        schema["email"] = office.email_address
    return schema

