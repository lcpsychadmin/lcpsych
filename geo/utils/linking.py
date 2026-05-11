"""
Internal linking utilities for geographic location pages.

Provides:
  get_related_links(state_slug, location_slug=None) -> dict

The returned dict contains:
  sibling_cities   – other cities in the same state  (excludes current location)
  sibling_counties – other counties in the same state (excludes current location)
  all_cities       – all cities in the same state (regardless of current location)
  all_counties     – all counties in the same state (regardless of current location)
  parent_state     – the state hub link {"name", "url"}
  tri_state_hubs   – list of state hub links for all OTHER states in the DB
  all_state_hubs   – list of state hub links for ALL active states in the DB

All data is read from the GeoState / GeoLocation database tables.
"""

from __future__ import annotations
from typing import Optional


def get_related_links(
    state_slug: str,
    location_slug: Optional[str] = None,
) -> dict:
    """
    Generate all internal linking data for a location page.

    Usage in a view::

        links = get_related_links("kentucky", "florence")
        context["links"] = links

    Template usage::

        {% for link in links.sibling_cities %}
          <a href="{{ link.url }}">{{ link.name }}</a>
        {% endfor %}
    """
    from geo.models import GeoState, GeoLocation

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return {}

    locations = list(
        GeoLocation.objects.filter(state=state, is_active=True)
        .select_related("county")
        .order_by("name")
    )
    cities = [loc for loc in locations if loc.location_type == GeoLocation.CITY]
    counties = [loc for loc in locations if loc.location_type == GeoLocation.COUNTY]

    def _loc_link(loc: GeoLocation) -> dict:
        return {"name": loc.name, "url": loc.get_url_path()}

    def _state_hub(s: GeoState) -> dict:
        return {"name": s.name, "abbreviation": s.abbreviation, "url": f"/{s.slug}/"}

    all_active_states = list(GeoState.objects.filter(is_active=True).order_by("name"))

    # Build county_cities: other cities in same county (city pages) or
    # all cities belonging to this county (county pages).
    county_cities: list = []
    if location_slug:
        current = next((l for l in locations if l.slug == location_slug), None)
        if current:
            if current.location_type == GeoLocation.CITY and current.county_id:
                county_cities = [
                    _loc_link(c) for c in cities
                    if c.county_id == current.county_id and c.id != current.id
                ]
            elif current.location_type == GeoLocation.COUNTY:
                county_cities = [
                    _loc_link(c) for c in cities
                    if c.county_id == current.id
                ]

    return {
        "sibling_cities": [_loc_link(c) for c in cities if c.slug != location_slug],
        "sibling_counties": [_loc_link(c) for c in counties if c.slug != location_slug],
        "all_cities": [_loc_link(c) for c in cities],
        "all_counties": [_loc_link(c) for c in counties],
        "parent_state": {"name": state.name, "url": f"/{state_slug}/"},
        "tri_state_hubs": [_state_hub(s) for s in all_active_states if s.slug != state_slug],
        "all_state_hubs": [_state_hub(s) for s in all_active_states],
        "county_cities": county_cities,
    }
