"""
Availability utilities for geo location pages.

Services are assigned only to therapists.
Locations inherit services from their therapists.
Areas (states / cities / counties) inherit services from locations that serve them.

Public API
----------
  get_therapists_for_location(location)  -> QuerySet[TherapistProfile]
  get_locations_for_therapist(therapist) -> QuerySet[GeoLocation]
  get_services_for_location(location)    -> QuerySet[Service]
  get_locations_serving_area(area)       -> QuerySet[GeoLocation]
  get_services_for_area(area)            -> QuerySet[Service]
  is_service_available_in_area(area, service) -> bool

Each function accepts either a model instance or a slug string (or state_slug +
optional location_slug pair) for convenience.
"""

from __future__ import annotations
from typing import Union


def get_therapists_for_location(location):
    """
    Return all published therapists associated with *location*, either via:
    - direct TherapistProfile.locations M2M, or
    - an OfficeLocation whose geo_locations M2M includes this location.

    Parameters
    ----------
    location : GeoLocation instance or int (pk)
    """
    from profiles.models import TherapistProfile
    from core.models import OfficeLocation

    # Therapists directly linked to this geo location
    direct_ids = TherapistProfile.objects.filter(
        locations=location,
        is_published=True,
    ).values_list("id", flat=True)

    # Therapists at an office that serves this geo location
    office_ids = TherapistProfile.objects.filter(
        offices__geo_locations=location,
        is_published=True,
    ).values_list("id", flat=True)

    all_ids = set(direct_ids) | set(office_ids)

    return TherapistProfile.objects.filter(id__in=all_ids, is_published=True).distinct()


def get_locations_for_therapist(therapist):
    """
    Return all active GeoLocations assigned to *therapist*, via either:
    - direct TherapistProfile.locations M2M, or
    - an OfficeLocation whose therapists M2M includes this therapist.

    Parameters
    ----------
    therapist : TherapistProfile instance or int (pk)
    """
    from geo.models import GeoLocation

    direct_ids = GeoLocation.objects.filter(
        therapists=therapist,
        is_active=True,
    ).values_list("id", flat=True)

    office_ids = GeoLocation.objects.filter(
        offices__therapists=therapist,
        is_active=True,
    ).values_list("id", flat=True)

    all_ids = set(direct_ids) | set(office_ids)
    return GeoLocation.objects.filter(id__in=all_ids, is_active=True).select_related("state").distinct()


def get_services_for_location(location):
    """
    Return all Services offered by any published therapist at *location*.
    Therapists are found via direct location assignment OR via an office
    whose geo_locations includes this location.

    Parameters
    ----------
    location : GeoLocation instance or int (pk)
    """
    from core.models import Service

    therapist_ids = get_therapists_for_location(location).values_list("id", flat=True)

    return Service.objects.filter(
        therapists__id__in=therapist_ids,
    ).distinct()


def get_locations_serving_area(area):
    """
    Return all active GeoLocations that "serve" the given area.

    Interpretation of *area*:
      - GeoState  → all active locations in that state
      - GeoLocation (county) → the county itself + all cities in that county
      - GeoLocation (city)   → just that city

    Parameters
    ----------
    area : GeoState or GeoLocation instance
    """
    from geo.models import GeoState, GeoLocation

    if isinstance(area, GeoState):
        return GeoLocation.objects.filter(state=area, is_active=True).distinct()

    if isinstance(area, GeoLocation):
        if area.location_type == GeoLocation.COUNTY:
            from django.db.models import Q
            return GeoLocation.objects.filter(
                Q(pk=area.pk) | Q(county=area),
                is_active=True,
            ).distinct()
        # city — only the city itself
        return GeoLocation.objects.filter(pk=area.pk, is_active=True)

    raise TypeError(f"Expected GeoState or GeoLocation, got {type(area)}")


def get_services_for_area(area):
    """
    Return all Services available in the given area, derived from therapists
    at locations that serve it.

    Parameters
    ----------
    area : GeoState or GeoLocation instance
    """
    from core.models import Service
    from geo.models import GeoState, GeoLocation

    if isinstance(area, GeoState):
        return Service.objects.filter(
            therapists__locations__state=area,
            therapists__locations__is_active=True,
            therapists__is_published=True,
        ).distinct()

    if isinstance(area, GeoLocation):
        if area.location_type == GeoLocation.COUNTY:
            from django.db.models import Q
            location_filter = Q(therapists__locations__pk=area.pk) | Q(
                therapists__locations__county=area
            )
            return Service.objects.filter(
                location_filter,
                therapists__locations__is_active=True,
                therapists__is_published=True,
            ).distinct()
        # city
        return Service.objects.filter(
            therapists__locations=area,
            therapists__locations__is_active=True,
            therapists__is_published=True,
        ).distinct()

    raise TypeError(f"Expected GeoState or GeoLocation, got {type(area)}")


def is_service_available_in_area(area, service) -> bool:
    """
    Return True if *service* is available in *area*.

    Parameters
    ----------
    area    : GeoState or GeoLocation instance
    service : Service instance or int (pk)
    """
    return get_services_for_area(area).filter(
        pk=service if isinstance(service, int) else service.pk
    ).exists()


def get_therapists_for_area(area):
    """
    Return all published therapists who have at least one active location in *area*,
    via either direct TherapistProfile.locations M2M or via an OfficeLocation.

    Parameters
    ----------
    area : GeoState or GeoLocation instance
    """
    from profiles.models import TherapistProfile
    from geo.models import GeoState, GeoLocation

    if isinstance(area, GeoState):
        direct_ids = TherapistProfile.objects.filter(
            locations__state=area,
            locations__is_active=True,
            is_published=True,
        ).values_list("id", flat=True)
        office_loc_ids = TherapistProfile.objects.filter(
            offices__geo_locations__state=area,
            offices__geo_locations__is_active=True,
            is_published=True,
        ).values_list("id", flat=True)
        office_state_ids = TherapistProfile.objects.filter(
            offices__geo_states=area,
            is_published=True,
        ).values_list("id", flat=True)
        all_ids = set(direct_ids) | set(office_loc_ids) | set(office_state_ids)
        return TherapistProfile.objects.filter(id__in=all_ids, is_published=True).distinct()

    if isinstance(area, GeoLocation):
        if area.location_type == GeoLocation.COUNTY:
            from django.db.models import Q
            direct_ids = TherapistProfile.objects.filter(
                Q(locations__pk=area.pk) | Q(locations__county=area),
                locations__is_active=True,
                is_published=True,
            ).values_list("id", flat=True)
            office_ids = TherapistProfile.objects.filter(
                Q(offices__geo_locations__pk=area.pk) | Q(offices__geo_locations__county=area),
                offices__geo_locations__is_active=True,
                is_published=True,
            ).values_list("id", flat=True)
            all_ids = set(direct_ids) | set(office_ids)
            return TherapistProfile.objects.filter(id__in=all_ids, is_published=True).distinct()
        # city
        direct_ids = TherapistProfile.objects.filter(
            locations=area,
            locations__is_active=True,
            is_published=True,
        ).values_list("id", flat=True)
        office_ids = TherapistProfile.objects.filter(
            offices__geo_locations=area,
            is_published=True,
        ).values_list("id", flat=True)
        all_ids = set(direct_ids) | set(office_ids)
        return TherapistProfile.objects.filter(id__in=all_ids, is_published=True).distinct()

    raise TypeError(f"Expected GeoState or GeoLocation, got {type(area)}")


def get_therapists_for_area_and_service(area, service):
    """
    Return all published therapists in *area* who also offer *service*.

    Parameters
    ----------
    area    : GeoState or GeoLocation instance
    service : Service instance
    """
    return get_therapists_for_area(area).filter(services=service).distinct()


# ---------------------------------------------------------------------------
# Region helpers
# ---------------------------------------------------------------------------

def get_therapists_for_region(region):
    """
    Return all published therapists available in *region*.

    Availability = union of therapists across all associated states and
    individual locations.

    Parameters
    ----------
    region : GeoRegion instance
    """
    from profiles.models import TherapistProfile

    ids: set[int] = set()

    for state in region.states.filter(is_active=True):
        ids |= set(get_therapists_for_area(state).values_list("id", flat=True))

    for location in region.locations.filter(is_active=True):
        ids |= set(get_therapists_for_location(location).values_list("id", flat=True))

    return TherapistProfile.objects.filter(id__in=ids, is_published=True).distinct()


def get_services_for_region(region):
    """
    Return all Services available in *region*.

    Availability = union of services across all associated states and locations.

    Parameters
    ----------
    region : GeoRegion instance
    """
    from core.models import Service

    therapist_ids = get_therapists_for_region(region).values_list("id", flat=True)
    return Service.objects.filter(therapists__id__in=therapist_ids).distinct()


def get_therapists_for_region_and_service(region, service):
    """
    Return all published therapists in *region* who also offer *service*.

    Parameters
    ----------
    region  : GeoRegion instance
    service : Service instance or int (pk)
    """
    return get_therapists_for_region(region).filter(services=service).distinct()
