"""
Views for geographic location pages.

Routes
------
  /areas-served/             → areas_served_list
  /[state]/                  → state_page
  /[state]/[city-or-county]/ → location_page

Both views read from the GeoState / GeoLocation database tables and raise
Http404 for any slug not present or marked inactive.
"""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from geo.models import GeoState, GeoLocation, GeoRegion
from geo.utils.metadata import get_location_metadata, get_breadcrumbs, get_region_metadata
from geo.utils.schema import get_location_schema
from geo.utils.linking import get_related_links
from geo.utils.availability import (
    get_therapists_for_location,
    get_therapists_for_area,
    get_services_for_location,
    get_services_for_area,
    get_locations_serving_area,
    get_therapists_for_region,
    get_therapists_for_region_and_service,
)
from core.models import HeroSettings, InsuranceProvider, OfficeLocation, PublishStatus, Service
from core.utils import get_offices
from django.db import models
from django.db.models import Case, IntegerField, Q, When


def state_page(request: HttpRequest, state_slug: str) -> HttpResponse:
    """
    Render the hub page for a state, e.g. /kentucky/

    The StateSlugConverter in geo/urls.py guarantees state_slug is valid before
    this view is called, but we defensively check anyway.
    """
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    content_blocks = list(
        state.content_blocks.filter(state=state).order_by("order").values("heading", "body")
    )

    metadata = get_location_metadata(state_slug)
    schema_json = get_location_schema(state_slug)
    breadcrumbs = get_breadcrumbs(state_slug)
    links = get_related_links(state_slug)

    from core.views import _build_therapist_cards, _published_therapists_queryset

    therapists = _build_therapist_cards(_published_therapists_queryset())
    services = list(
        Service.objects.filter(status=PublishStatus.PUBLISH)
        .select_related('page')
        .order_by('order', 'title')
    )
    accepted_providers = list(
        InsuranceProvider.objects.filter(is_active=True).order_by('order', 'name', 'id')
    )
    hero_settings = (
        HeroSettings.objects
        .prefetch_related('content_blocks')
        .filter(pk=1)
        .first()
    )
    home_offices = list(get_offices())

    context = {
        # SEO/meta (override context-processor defaults)
        **metadata,
        # Location data
        "state": state,
        "state_slug": state_slug,
        "location": None,
        "location_slug": None,
        "location_type": "state",
        # Content
        "content_blocks": content_blocks,
        "hero_heading": state.hero_heading or "Mental Health Services",
        "hero_subheading": state.hero_subheading,
        "hero_image_url": state.hero_image.url if state.hero_image else None,
        # Schema / linking
        "location_schema_json": schema_json,
        "breadcrumbs": breadcrumbs,
        "links": links,
        # Homepage partials context
        "therapists": therapists,
        "services": services,
        "accepted_providers": accepted_providers,
        "hero_settings": hero_settings,
        "home_offices": home_offices,
    }
    return render(request, "geo/location.html", context)


def _location_page_impl(
    request: HttpRequest,
    state: "GeoState",
    state_slug: str,
    location: "GeoLocation",
    location_slug: str,
) -> HttpResponse:
    """Shared implementation for location_page and city_under_county_page."""
    content_blocks = list(
        location.content_blocks.order_by("order").values("heading", "body")
    )

    metadata = get_location_metadata(state_slug, location_slug)
    schema_json = get_location_schema(state_slug, location_slug)
    breadcrumbs = get_breadcrumbs(state_slug, location_slug)
    links = get_related_links(state_slug, location_slug)

    location_type = location.location_type
    default_heading = "Mental Health Services"

    from core.views import _build_therapist_cards, _published_therapists_queryset

    therapists = _build_therapist_cards(_published_therapists_queryset())
    services = list(
        Service.objects.filter(status=PublishStatus.PUBLISH)
        .select_related('page')
        .order_by('order', 'title')
    )
    accepted_providers = list(
        InsuranceProvider.objects.filter(is_active=True).order_by('order', 'name', 'id')
    )
    hero_settings = (
        HeroSettings.objects
        .prefetch_related('content_blocks')
        .filter(pk=1)
        .first()
    )
    home_offices = list(get_offices())

    context = {
        # SEO/meta
        **metadata,
        # Location data
        "state": state,
        "state_slug": state_slug,
        "location": location,
        "location_slug": location_slug,
        "location_type": location_type,
        # Content
        "content_blocks": content_blocks,
        "hero_heading": location.hero_heading or default_heading,
        "hero_subheading": location.hero_subheading,
        "hero_image_url": location.hero_image.url if location.hero_image else (state.hero_image.url if state.hero_image else None),
        # Schema / linking
        "location_schema_json": schema_json,
        "breadcrumbs": breadcrumbs,
        "links": links,
        # Homepage partials context
        "therapists": therapists,
        "services": services,
        "accepted_providers": accepted_providers,
        "hero_settings": hero_settings,
        "home_offices": home_offices,
    }
    return render(request, "geo/location.html", context)


def location_page(
    request: HttpRequest, state_slug: str, location_slug: str
) -> HttpResponse:
    """
    Render a county or unassigned city page, e.g. /kentucky/boone-county/ or /kentucky/florence/
    Returns 404 if the location slug is not found or inactive.
    """
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    try:
        location = GeoLocation.objects.select_related("county").get(
            state=state, slug=location_slug, is_active=True
        )
    except GeoLocation.DoesNotExist:
        raise Http404

    # If this city has a county parent, redirect to the canonical 3-segment URL
    if location.location_type == GeoLocation.CITY and location.county_id:
        from django.shortcuts import redirect
        return redirect(location.get_url_path(), permanent=True)

    return _location_page_impl(request, state, state_slug, location, location_slug)


def city_under_county_page(
    request: HttpRequest, state_slug: str, county_slug: str, city_slug: str
) -> HttpResponse:
    """
    Render a city page nested under its county, e.g. /kentucky/boone-county/florence/
    Returns 404 if the county or city is not found / inactive.
    """
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    try:
        county = GeoLocation.objects.get(
            state=state, slug=county_slug,
            location_type=GeoLocation.COUNTY, is_active=True,
        )
    except GeoLocation.DoesNotExist:
        raise Http404

    try:
        location = GeoLocation.objects.get(
            state=state, slug=city_slug, county=county, is_active=True
        )
    except GeoLocation.DoesNotExist:
        raise Http404

    return _location_page_impl(request, state, state_slug, location, city_slug)


def areas_served_list(request: HttpRequest) -> HttpResponse:
    """
    Browse/search page listing all active states and their active locations.
    Client-side JS handles real-time filtering by name.
    URL: /areas-served/
    """
    states = (
        GeoState.objects.filter(is_active=True)
        .prefetch_related(
            models.Prefetch(
                "locations",
                queryset=GeoLocation.objects.select_related("county").filter(is_active=True),
            )
        )
        .order_by("name")
    )

    state_groups = []
    for state in states:
        active_locations = sorted(
            [loc for loc in state.locations.all() if loc.is_active],
            key=lambda l: l.name,
        )

        # Build county → cities mapping
        counties_dict: dict = {}
        for loc in active_locations:
            if loc.location_type == "county":
                counties_dict[loc.pk] = {"county": loc, "cities": []}

        # Assign cities to their county or to standalone
        standalone_cities: list = []
        for loc in active_locations:
            if loc.location_type == "city":
                if loc.county_id and loc.county_id in counties_dict:
                    counties_dict[loc.county_id]["cities"].append(loc)
                else:
                    standalone_cities.append(loc)

        county_groups = sorted(counties_dict.values(), key=lambda cg: cg["county"].name)
        location_count = (
            len(county_groups)
            + sum(len(cg["cities"]) for cg in county_groups)
            + len(standalone_cities)
        )

        state_groups.append({
            "state": state,
            "county_groups": county_groups,
            "standalone_cities": standalone_cities,
            "location_count": location_count,
        })

    context = {
        "seo_title": "Areas Served | L+C Psychological Services",
        "seo_description": (
            "Find L+C Psychological Services therapists near you. "
            "Browse all locations we serve across Kentucky and beyond."
        ),
        "state_groups": state_groups,
    }
    return render(request, "geo/areas_served.html", context)


def _area_service_context(request, state, location, service, therapist_cards):
    """Shared context builder for state_service_page / location_service_page."""
    if location:
        area_name = f"{location.name}, {state.abbreviation}"
        breadcrumbs = [
            {"label": "Home", "url": "/"},
            {"label": state.name, "url": f"/{state.slug}/"},
            {"label": location.name, "url": location.get_url_path()},
            {"label": service.title, "url": ""},
        ]
    else:
        area_name = state.name
        breadcrumbs = [
            {"label": "Home", "url": "/"},
            {"label": state.name, "url": f"/{state.slug}/"},
            {"label": service.title, "url": ""},
        ]

    location_type = location.location_type if location else "state"
    links = get_related_links(state.slug, location.slug if location else None)

    from core.models import Service as ServiceModel, PublishStatus
    other_services = list(ServiceModel.objects.filter(status=PublishStatus.PUBLISH).exclude(pk=service.pk).order_by("order", "title")[:6])

    from core.models import OfficeLocation as OfficeLocationModel
    office_locations = list(OfficeLocationModel.objects.filter(is_active=True, is_virtual=False).order_by("order", "name"))

    return {
        "seo_title": f"{service.title} for {area_name} | L+C Psychological Services",
        "seo_description": (
            f"Find licensed therapists offering {service.title.lower()} for {area_name}. "
            f"L+C Psychological Services offers in-person and telehealth options."
        ),
        "hero_heading": service.title,
        "hero_subheading": service.hero_intro or (
            f"Connect with a licensed therapist specializing in {service.title.lower()}. "
            f"We offer flexible scheduling and most major insurance plans are accepted."
        ),
        "state": state,
        "location": location,
        "location_type": location_type,
        "area_name": area_name,
        "service": service,
        "other_services": other_services,
        "office_locations": office_locations,
        "therapist_cards": therapist_cards,
        "breadcrumbs": breadcrumbs,
        "links": links,
    }


def state_service_page(request: HttpRequest, state_slug: str, service_slug: str) -> HttpResponse:
    """
    Intersectional page: a service offered in a specific state.
    URL: /<state_slug>/services/<service_slug>/
    Returns 404 if no published therapist in this state offers the service.
    """
    from core.models import Service
    from geo.utils.availability import get_therapists_for_area_and_service

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    try:
        service = Service.objects.get(slug=service_slug)
    except Service.DoesNotExist:
        raise Http404

    therapists_qs = get_therapists_for_area_and_service(state, service)
    if not therapists_qs.exists():
        raise Http404

    from core.views import _build_therapist_cards
    therapist_cards = _build_therapist_cards(therapists_qs)

    context = _area_service_context(request, state, None, service, therapist_cards)
    return render(request, "geo/area_service.html", context)


def location_service_page(
    request: HttpRequest, state_slug: str, location_slug: str, service_slug: str
) -> HttpResponse:
    """
    Intersectional page: a service offered in a specific city/county.
    URL: /<state_slug>/<location_slug>/services/<service_slug>/
    Returns 404 if no published therapist in this location offers the service.
    """
    from core.models import Service
    from geo.utils.availability import get_therapists_for_area_and_service

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    try:
        location = GeoLocation.objects.get(state=state, slug=location_slug, is_active=True)
    except GeoLocation.DoesNotExist:
        raise Http404

    try:
        service = Service.objects.get(slug=service_slug)
    except Service.DoesNotExist:
        raise Http404

    therapists_qs = get_therapists_for_area_and_service(location, service)
    if not therapists_qs.exists():
        raise Http404

    from core.views import _build_therapist_cards
    therapist_cards = _build_therapist_cards(therapists_qs)

    context = _area_service_context(request, state, location, service, therapist_cards)
    return render(request, "geo/area_service.html", context)


def city_county_service_page(
    request: HttpRequest, state_slug: str, county_slug: str, city_slug: str, service_slug: str
) -> HttpResponse:
    """
    Intersectional page: a service offered in a city nested under a county.
    URL: /<state_slug>/<county_slug>/<city_slug>/services/<service_slug>/
    """
    from core.models import Service
    from geo.utils.availability import get_therapists_for_area_and_service

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        raise Http404

    try:
        county = GeoLocation.objects.get(
            state=state, slug=county_slug,
            location_type=GeoLocation.COUNTY, is_active=True,
        )
    except GeoLocation.DoesNotExist:
        raise Http404

    try:
        location = GeoLocation.objects.get(
            state=state, slug=city_slug, county=county, is_active=True
        )
    except GeoLocation.DoesNotExist:
        raise Http404

    try:
        service = Service.objects.get(slug=service_slug)
    except Service.DoesNotExist:
        raise Http404

    therapists_qs = get_therapists_for_area_and_service(location, service)
    if not therapists_qs.exists():
        raise Http404

    from core.views import _build_therapist_cards
    therapist_cards = _build_therapist_cards(therapists_qs)

    context = _area_service_context(request, state, location, service, therapist_cards)
    return render(request, "geo/area_service.html", context)



# ---------------------------------------------------------------------------
# Region views
# ---------------------------------------------------------------------------

def region_page(request: HttpRequest, region_slug: str) -> HttpResponse:
    """
    Hub page for a named region, e.g. /regions/greater-cincinnati/
    Displays the same full-homepage layout as state/location pages.
    Returns 404 if the region slug is not found or inactive.
    """
    try:
        region = GeoRegion.objects.get(slug=region_slug, is_active=True)
    except GeoRegion.DoesNotExist:
        raise Http404

    metadata = get_region_metadata(region_slug)

    from core.views import _build_therapist_cards, _published_therapists_queryset

    therapists = _build_therapist_cards(_published_therapists_queryset())
    services = list(
        Service.objects.filter(status=PublishStatus.PUBLISH)
        .select_related("page")
        .order_by("order", "title")
    )
    accepted_providers = list(
        InsuranceProvider.objects.filter(is_active=True).order_by("order", "name", "id")
    )
    hero_settings = (
        HeroSettings.objects
        .prefetch_related("content_blocks")
        .filter(pk=1)
        .first()
    )
    home_offices = list(get_offices())

    context = {
        **metadata,
        "region": region,
        "region_slug": region_slug,
        "location_type": "region",
        "breadcrumbs": [
            {"label": "Home", "url": "/"},
            {"label": region.name, "url": ""},
        ],
        "hero_image_url": region.hero_image.url if region.hero_image else None,
        # Homepage partials context
        "therapists": therapists,
        "services": services,
        "accepted_providers": accepted_providers,
        "hero_settings": hero_settings,
        "home_offices": home_offices,
    }
    return render(request, "geo/region.html", context)


def region_service_page(request: HttpRequest, region_slug: str, service_slug: str) -> HttpResponse:
    """
    Intersectional page: a service offered in a region.
    URL: /regions/<region_slug>/services/<service_slug>/
    Returns 404 if no published therapist in this region offers the service.
    """
    try:
        region = GeoRegion.objects.get(slug=region_slug, is_active=True)
    except GeoRegion.DoesNotExist:
        raise Http404

    try:
        service = Service.objects.get(slug=service_slug)
    except Service.DoesNotExist:
        raise Http404

    from profiles.models import TherapistProfile
    therapists_qs = TherapistProfile.objects.filter(
        is_published=True, services=service
    ).distinct()
    if not therapists_qs.exists():
        raise Http404

    from core.views import _build_therapist_cards
    therapist_cards = _build_therapist_cards(therapists_qs)

    area_name = region.name
    other_services = list(
        Service.objects.filter(status=PublishStatus.PUBLISH)
        .exclude(pk=service.pk)
        .order_by("order", "title")[:6]
    )
    office_locations = list(
        OfficeLocation.objects.filter(is_active=True, is_virtual=False).order_by("order", "name")
    )

    context = {
        "seo_title": f"{service.title} in {area_name} | L+C Psychological Services",
        "seo_description": (
            f"Find licensed therapists offering {service.title.lower()} in {area_name}. "
            f"L+C Psychological Services offers in-person and telehealth options."
        ),
        "hero_heading": service.title,
        "hero_subheading": service.hero_intro or (
            f"Connect with a licensed therapist specializing in {service.title.lower()} in {area_name}. "
            f"We offer flexible scheduling and most major insurance plans are accepted."
        ),
        "area_name": area_name,
        "service": service,
        "other_services": other_services,
        "office_locations": office_locations,
        "therapist_cards": therapist_cards,
        "breadcrumbs": [
            {"label": "Home", "url": "/"},
            {"label": region.name, "url": f"/regions/{region_slug}/"},
            {"label": service.title, "url": ""},
        ],
        "region": region,
        "region_slug": region_slug,
    }
    return render(request, "geo/area_service.html", context)


def region_therapist_page(
    request: HttpRequest, region_slug: str, therapist_slug: str
) -> HttpResponse:
    """
    Intersectional page: a specific therapist serving a region.
    URL: /regions/<region_slug>/therapists/<therapist_slug>/
    Returns 404 if the therapist is not in this region.
    """
    from profiles.models import TherapistProfile
    from core.models import OfficeLocation as OfficeLocationModel

    try:
        region = GeoRegion.objects.get(slug=region_slug, is_active=True)
    except GeoRegion.DoesNotExist:
        raise Http404

    try:
        profile = TherapistProfile.objects.get(slug=therapist_slug, is_published=True)
    except TherapistProfile.DoesNotExist:
        raise Http404

    area_name = region.name
    all_services = profile.services.all()
    offices = OfficeLocationModel.objects.filter(therapists=profile, is_active=True).order_by("order", "name")

    context = {
        "profile": profile,
        "area_name": area_name,
        "all_services": all_services,
        "offices": offices,
        "region": region,
        "region_slug": region_slug,
        "seo_title": f"{profile.display_name} | Therapist in {area_name}",
        "seo_description": (
            f"{profile.display_name} offers therapy services in {area_name} "
            f"at L+C Psychological Services. Schedule an appointment today."
        ),
    }
    return render(request, "profiles/therapist_area.html", context)
