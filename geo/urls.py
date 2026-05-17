"""
URL patterns for the geo app.

A custom path converter (StateSlugConverter) is registered so that
/<state>/ only matches slugs that are valid keys in AREAS_SERVED.
This prevents the geo patterns from shadowing other URL patterns
(e.g. /about-us/, /blog/) even though geo URLs are registered first.
"""

from django.urls import path, register_converter

from . import views


class StateSlugConverter:
    """
    URL converter that matches only slugs present in the GeoState table.

    Any other value causes Django to skip this URL pattern and try the
    next one — this is the mechanism that prevents geo routes from
    eating unrelated single-segment URLs like /about-us/.
    """

    regex = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"

    def to_python(self, value: str) -> str:
        from geo.models import GeoState

        if GeoState.objects.filter(slug=value, is_active=True).exists():
            return value
        raise ValueError(f"Not a known state slug: {value!r}")

    def to_url(self, value: str) -> str:
        return str(value)


# Guard against double-registration when Django reloads this module
try:
    register_converter(StateSlugConverter, "state")
except ValueError:
    pass  # already registered

app_name = "geo"

urlpatterns = [
    # Areas served search/browse page — e.g. /areas-served/
    path("areas-served/", views.areas_served_list, name="areas_served_list"),
    # ---------------------------------------------------------------------------
    # Region pages — /regions/<slug>/
    # A region is a flexible named grouping of states and/or locations.
    # These must come before state patterns because they have a fixed "regions/"
    # prefix and therefore cannot conflict with state slugs.
    # ---------------------------------------------------------------------------
    path("regions/<slug:region_slug>/", views.region_page, name="region"),
    path(
        "regions/<slug:region_slug>/services/<slug:service_slug>/",
        views.region_service_page,
        name="region_service",
    ),
    path(
        "regions/<slug:region_slug>/therapists/<slug:therapist_slug>/",
        views.region_therapist_page,
        name="region_therapist",
    ),
    path(
        "regions/<slug:region_slug>/modalities/<slug:modality_slug>/",
        views.region_modality_page,
        name="region_modality",
    ),
    path(
        "regions/<slug:region_slug>/conditions/<slug:condition_slug>/",
        views.region_condition_page,
        name="region_condition",
    ),
    # Intersectional service pages (must come before state/location pages to avoid shadowing)
    path(
        "<state:state_slug>/services/<slug:service_slug>/",
        views.state_service_page,
        name="state_service",
    ),
    path(
        "<state:state_slug>/<slug:location_slug>/services/<slug:service_slug>/",
        views.location_service_page,
        name="location_service",
    ),
    # City under county with service — e.g. /ohio/hamilton-county/cincinnati/services/anxiety/
    path(
        "<state:state_slug>/<slug:county_slug>/<slug:city_slug>/services/<slug:service_slug>/",
        views.city_county_service_page,
        name="city_county_service",
    ),
    # Intersectional modality pages
    path(
        "<state:state_slug>/modalities/<slug:modality_slug>/",
        views.state_modality_page,
        name="state_modality",
    ),
    path(
        "<state:state_slug>/<slug:location_slug>/modalities/<slug:modality_slug>/",
        views.location_modality_page,
        name="location_modality",
    ),
    path(
        "<state:state_slug>/<slug:county_slug>/<slug:city_slug>/modalities/<slug:modality_slug>/",
        views.city_county_modality_page,
        name="city_county_modality",
    ),
    # Intersectional condition pages
    path(
        "<state:state_slug>/conditions/<slug:condition_slug>/",
        views.state_condition_page,
        name="state_condition",
    ),
    path(
        "<state:state_slug>/<slug:location_slug>/conditions/<slug:condition_slug>/",
        views.location_condition_page,
        name="location_condition",
    ),
    path(
        "<state:state_slug>/<slug:county_slug>/<slug:city_slug>/conditions/<slug:condition_slug>/",
        views.city_county_condition_page,
        name="city_county_condition",
    ),
    # State hub page — e.g. /kentucky/
    path("<state:state_slug>/", views.state_page, name="state"),
    # County or unassigned city — e.g. /kentucky/boone-county/ or /kentucky/florence/
    path(
        "<state:state_slug>/<slug:location_slug>/",
        views.location_page,
        name="location",
    ),
    # City under county — e.g. /kentucky/boone-county/florence/
    path(
        "<state:state_slug>/<slug:county_slug>/<slug:city_slug>/",
        views.city_under_county_page,
        name="city_under_county",
    ),
]
