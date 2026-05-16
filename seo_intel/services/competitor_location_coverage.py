"""
seo_intel/services/competitor_location_coverage.py
----------------------------------------------------
Location Coverage Engine.

Parses competitor crawled pages to identify which geographic markets
they target, then compares against LC Psych's geo pages and location seeds.

Public API
----------
    get_location_coverage(domain: str) -> dict
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _extract_url_locations(url: str, known_locations: frozenset[str]) -> set[str]:
    """Return location keywords that appear as path segments in *url*."""
    path = urlparse(url).path.lower()
    # Split on hyphens and slashes; keep alpha-only tokens of length > 3
    segments = set(re.split(r"[-/]", path))
    hits: set[str] = set()
    for seg in segments:
        if len(seg) <= 3 or not seg.isalpha():
            continue
        for kw in known_locations:
            if seg == kw or (len(seg) >= 5 and seg in kw):
                hits.add(kw)
    return hits


def get_location_coverage(domain: str) -> dict:
    """Return location coverage comparison: competitor vs LC Psych.

    Returns dict with keys:
        domain                str
        has_data              bool
        competitor_locations  list[str]
        lcpsych_locations     list[str]
        missing_from_lc       list[str]   – competitor has, LC Psych lacks
        lcpsych_exclusive     list[str]   – LC Psych has, competitor lacks
        overlap               list[str]   – both cover
        summary               dict
        location_rows         list[dict]  – full comparison table
    """
    from seo_intel.services.competitor_crawler import get_cached_crawl, LOCATION_KW

    pages = get_cached_crawl(domain) or []
    if not pages:
        return {
            "domain": domain,
            "has_data": False,
            "competitor_locations": [],
            "lcpsych_locations": [],
            "missing_from_lc": [],
            "lcpsych_exclusive": [],
            "overlap": [],
            "summary": {},
            "location_rows": [],
        }

    # ── LC Psych locations (geo DB + regions + location seeds) ───────────
    lc_locs: set[str] = set()
    try:
        from geo.models import GeoLocation, GeoRegion, GeoState
        for loc in GeoLocation.objects.filter(is_active=True).values("name", "slug"):
            lc_locs.add(loc["name"].lower())
            lc_locs.add(loc["slug"].replace("-", " ").lower())
        for state in GeoState.objects.filter(is_active=True).values("name"):
            lc_locs.add(state["name"].lower())
        for region in GeoRegion.objects.filter(is_active=True).values("name", "slug"):
            lc_locs.add(region["name"].lower())
            lc_locs.add(region["slug"].replace("-", " ").lower())
    except Exception:
        logger.debug("location_coverage: could not load geo models", exc_info=True)

    try:
        from seo_settings.models import KeywordSeed
        for kw in KeywordSeed.objects.filter(active=True, category="location").values_list(
            "keyword", flat=True
        ):
            lc_locs.add(kw.lower())
    except Exception:
        logger.debug("location_coverage: could not load KeywordSeed", exc_info=True)

    # Expand taxonomy to include all DB-sourced LC Psych locations (counties,
    # cities, regions, states) so they survive filtering and are also detectable
    # in competitor content.
    loc_taxonomy = LOCATION_KW | lc_locs

    # ── Competitor locations (from keyword_hits + URL path matching) ──────
    comp_locs: set[str] = set()
    for page in pages:
        kw_locs = page.get("keyword_hits", {}).get("locations", [])
        comp_locs.update(kw.lower() for kw in kw_locs)
        comp_locs.update(_extract_url_locations(page.get("url", ""), loc_taxonomy))

    # Filter competitor locations to expanded taxonomy; LC Psych locations are
    # authoritative (from DB) so use them directly.
    comp_locs = comp_locs & loc_taxonomy
    lc_locs_filtered = lc_locs

    # ── Sets ──────────────────────────────────────────────────────────────
    missing = sorted(comp_locs - lc_locs_filtered)
    exclusive = sorted(lc_locs_filtered - comp_locs)
    shared = sorted(comp_locs & lc_locs_filtered)

    # Full comparison table rows
    all_locs = sorted(comp_locs | lc_locs_filtered)
    location_rows = []
    for loc in all_locs:
        in_comp = loc in comp_locs
        in_lc = loc in lc_locs_filtered
        if in_comp and in_lc:
            status, css = "shared", "score-high"
        elif in_comp:
            status, css = "gap", "score-low"
        else:
            status, css = "lc-only", "score-mid"
        location_rows.append({
            "location": loc,
            "competitor": in_comp,
            "lcpsych": in_lc,
            "status": status,
            "status_css": css,
        })

    comp_count = len(comp_locs)
    lc_count = len(lc_locs_filtered)

    return {
        "domain": domain,
        "has_data": True,
        "competitor_locations": sorted(comp_locs),
        "lcpsych_locations": sorted(lc_locs_filtered),
        "missing_from_lc": missing,
        "lcpsych_exclusive": exclusive,
        "overlap": shared,
        "summary": {
            "competitor_count": comp_count,
            "lcpsych_count": lc_count,
            "missing_count": len(missing),
            "exclusive_count": len(exclusive),
            "overlap_count": len(shared),
        },
        "location_rows": location_rows,
    }
