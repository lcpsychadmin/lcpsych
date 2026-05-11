"""
JSON-LD schema utilities for geographic location pages.

Provides:
  get_location_schema(state_slug, location_slug=None) -> str
    Returns a JSON-LD string ready to drop into a <script type="application/ld+json"> tag.

Reads from GeoState / GeoLocation database tables.
"""

from __future__ import annotations
import json
from typing import Optional
from django.conf import settings
from geo.utils.metadata import get_breadcrumbs


def _site_base() -> str:
    return (getattr(settings, "BASE_URL", "") or "").rstrip("/")


def get_location_schema(
    state_slug: str,
    location_slug: Optional[str] = None,
) -> str:
    """
    Build and return a JSON-LD @graph payload for the given location page.

    Graph nodes:
      - BreadcrumbList
      - Service (areaServed with Place node)
      - WebPage
    """
    from geo.models import GeoState, GeoLocation

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        return ""

    base = _site_base()
    canonical = (
        f"{base}/{state_slug}/"
        if not location_slug
        else f"{base}/{state_slug}/{location_slug}/"
    )

    # Resolve the display name and schema type for this location
    location_name = state.name
    location_type_schema = "State"
    if location_slug:
        try:
            loc = GeoLocation.objects.get(
                state=state, slug=location_slug, is_active=True
            )
            location_name = loc.name
            location_type_schema = (
                "City" if loc.location_type == GeoLocation.CITY else "AdministrativeArea"
            )
        except GeoLocation.DoesNotExist:
            pass

    # Breadcrumb list
    breadcrumbs = get_breadcrumbs(state_slug, location_slug)
    breadcrumb_list = {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": crumb["label"],
                "item": f"{base}{crumb['url']}",
            }
            for i, crumb in enumerate(breadcrumbs)
        ],
    }

    # Service node
    area_served: dict = {
        "@type": location_type_schema,
        "name": location_name,
    }
    if location_slug:
        area_served["containedInPlace"] = {
            "@type": "State",
            "name": state.name,
        }

    service_node = {
        "@type": "Service",
        "@id": f"{canonical}#service",
        "serviceType": "Mental Health Therapy",
        "name": f"Therapy in {location_name}",
        "description": (
            f"Individual therapy, couples counseling, and psychological services "
            f"for {location_name} residents from L+C Psychological Services."
        ),
        "areaServed": area_served,
        "provider": {"@id": f"{base}/#organization"},
        "url": canonical,
    }

    # WebPage node
    webpage_node = {
        "@type": "WebPage",
        "@id": f"{canonical}#webpage",
        "url": canonical,
        "name": f"Therapists in {location_name} | L+C Psychological Services",
        "isPartOf": {"@id": f"{base}/#website"},
        "breadcrumb": {"@id": f"{canonical}#breadcrumb"},
    }

    graph = {
        "@context": "https://schema.org",
        "@graph": [breadcrumb_list, service_node, webpage_node],
    }
    return json.dumps(graph, indent=2, ensure_ascii=False)
