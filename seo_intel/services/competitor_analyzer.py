"""
seo_intel/services/competitor_analyzer.py
-------------------------------------------
Competitor Analysis Engine.

Compares crawled competitor pages against LC Psych's own page structure
to identify content, keyword, location, modality, and testing gaps.

Public API
----------
    analyze_competitor(domain, pages=None) -> dict

Return dict keys:
    domain          str
    page_count      int
    crawled         bool
    overview        dict   — high-level metrics
    lc_coverage     dict   — {category: sorted_list_of_keywords}
    comp_coverage   dict   — {category: sorted_list_of_keywords}
    gaps            dict   — {category: sorted list of gap keywords}
    gap_scores      dict   — {score_name: 0-100 int}
    top_pages       dict   — {category: [page_dict, ...]}
    recommendations list   — [{action, description, category, priority, priority_css}, ...]
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

_CATEGORIES = ("services", "modalities", "testing", "conditions", "locations")


# ---------------------------------------------------------------------------
# LC Psych coverage helpers
# ---------------------------------------------------------------------------

def _lc_psych_coverage() -> dict[str, set[str]]:
    """Build LC Psych's keyword coverage from its own pages, geo data, and seeds."""
    from seo_intel.services.competitor_crawler import (
        SERVICES_KW, MODALITIES_KW, TESTING_KW, CONDITIONS_KW, LOCATION_KW,
        _extract_keyword_hits,
    )
    from seo_settings.models import KeywordSeed

    coverage: dict[str, set[str]] = {cat: set() for cat in _CATEGORIES}

    # Scan Page titles + paths
    try:
        from core.models import Page
        for page in Page.objects.filter(status="publish").values("title", "path"):
            text = f"{page['title']} {page['path']}".lower()
            hits = _extract_keyword_hits(text)
            for cat, kws in hits.items():
                coverage[cat].update(kws)
    except Exception:
        logger.debug("competitor_analyzer: could not load core.Page", exc_info=True)

    # Scan GeoLocation + GeoState names
    try:
        from geo.models import GeoLocation, GeoState
        for loc in GeoLocation.objects.filter(is_active=True).values("name", "slug"):
            coverage["locations"].add(loc["name"].lower())
            coverage["locations"].add(loc["slug"].replace("-", " ").lower())
        for state in GeoState.objects.filter(is_active=True).values("name"):
            coverage["locations"].add(state["name"].lower())
    except Exception:
        logger.debug("competitor_analyzer: could not load geo models", exc_info=True)

    # Seed keywords as coverage signal by category
    cat_map = {
        "service": "services",
        "testing": "testing",
        "modality": "modalities",
        "location": "locations",
    }
    for seed in KeywordSeed.objects.filter(active=True).values("keyword", "category"):
        dest = cat_map.get(seed["category"])
        if dest:
            coverage[dest].add(seed["keyword"].lower())

    return coverage


def _competitor_coverage(pages: list[dict]) -> dict[str, set[str]]:
    """Union of all keyword hits across all competitor pages."""
    coverage: dict[str, set[str]] = {cat: set() for cat in _CATEGORIES}
    for page in pages:
        for cat, kws in page.get("keyword_hits", {}).items():
            if cat in coverage:
                coverage[cat].update(kws)
    return coverage


def _gap_score(lc: set, comp: set) -> int:
    """Return 0-100 gap score: percentage of competitor coverage LC Psych lacks."""
    if not comp:
        return 0
    missing = comp - lc
    return round(100 * len(missing) / len(comp))


# ---------------------------------------------------------------------------
# Page classification
# ---------------------------------------------------------------------------

def _classify_page(page: dict) -> str:
    """Assign a primary category to a competitor page."""
    hits = page.get("keyword_hits", {})
    title = page.get("title", "").lower()
    url = page.get("url", "").lower()

    if hits.get("testing") or any(
        w in title for w in ("testing", "evaluation", "assessment", "neuropsych")
    ):
        return "testing"
    if hits.get("modalities") or any(
        w in title for w in ("cbt", "dbt", "emdr", "approach", "technique")
    ):
        return "modality"
    if hits.get("locations") or any(
        seg in url for seg in ("/location", "/area", "/serving", "/near")
    ):
        return "location"
    if hits.get("conditions") or any(
        w in title for w in ("anxiety", "depression", "adhd", "ptsd", "ocd", "trauma")
    ):
        return "condition"
    if hits.get("services"):
        return "service"
    return "general"


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _build_recommendations(
    gaps: dict[str, list[str]],
    gap_scores: dict[str, int],
    pages_by_cat: Counter,
    avg_word_count: float,
) -> list[dict]:
    recs: list[dict] = []

    # Testing gaps — highest clinical value, so check first
    if gap_scores.get("testing_gap_score", 0) >= 30:
        for kw in gaps.get("testing", [])[:3]:
            recs.append({
                "action": "Create testing page",
                "description": f"Competitor covers \"{kw}\" — LC Psych has no matching testing page.",
                "category": "testing",
                "priority": "High",
                "priority_css": "action-red",
            })

    if gap_scores.get("modality_gap_score", 0) >= 30:
        for kw in gaps.get("modalities", [])[:3]:
            recs.append({
                "action": "Add modality page",
                "description": f"Competitor covers \"{kw}\" — no corresponding approach page found.",
                "category": "modality",
                "priority": "High",
                "priority_css": "action-red",
            })

    if gap_scores.get("content_gap_score", 0) >= 25:
        for kw in gaps.get("services", [])[:3]:
            recs.append({
                "action": "Create service page",
                "description": f"Competitor covers \"{kw}\" — consider adding coverage for this service.",
                "category": "service",
                "priority": "Medium",
                "priority_css": "action-yellow",
            })

    if gap_scores.get("location_gap_score", 0) >= 25:
        for kw in gaps.get("locations", [])[:3]:
            recs.append({
                "action": "Add location page",
                "description": f"Competitor targets \"{kw}\" — LC Psych lacks a location page for this area.",
                "category": "location",
                "priority": "Medium",
                "priority_css": "action-yellow",
            })

    for kw in gaps.get("conditions", [])[:3]:
        recs.append({
            "action": "Add condition page",
            "description": f"Competitor covers the condition \"{kw}\" — a dedicated page may help.",
            "category": "condition",
            "priority": "Low",
            "priority_css": "action-gray",
        })

    if avg_word_count > 700:
        recs.append({
            "action": "Deepen existing content",
            "description": (
                f"Competitor pages average {round(avg_word_count):,} words. "
                "Expanding thin LC Psych pages can improve rankings."
            ),
            "category": "content",
            "priority": "Medium",
            "priority_css": "action-yellow",
        })

    return recs[:20]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_competitor(domain: str, pages: list[dict] | None = None) -> dict:
    """Run full competitor gap analysis and return a structured report.

    Args:
        domain: Competitor domain (e.g. ``"psychologytoday.com"``).
        pages:  Pre-crawled page list. If None, loads from cache automatically.

    Returns a dict with keys: domain, page_count, crawled, overview,
    lc_coverage, comp_coverage, gaps, gap_scores, top_pages, recommendations.
    """
    from seo_intel.services.competitor_crawler import get_cached_crawl

    if pages is None:
        pages = get_cached_crawl(domain) or []

    if not pages:
        return {
            "domain": domain,
            "page_count": 0,
            "crawled": False,
            "overview": {},
            "lc_coverage": {},
            "comp_coverage": {},
            "gaps": {},
            "gap_scores": {},
            "top_pages": {},
            "recommendations": [],
        }

    lc_cov = _lc_psych_coverage()
    comp_cov = _competitor_coverage(pages)

    # ── Gaps ──────────────────────────────────────────────────────────────
    gaps: dict[str, list[str]] = {}
    for cat in _CATEGORIES:
        gaps[cat] = sorted(comp_cov.get(cat, set()) - lc_cov.get(cat, set()))

    gap_scores = {
        "content_gap_score": _gap_score(
            lc_cov.get("services", set()), comp_cov.get("services", set())
        ),
        "keyword_gap_score": _gap_score(
            lc_cov.get("services", set())
            | lc_cov.get("modalities", set())
            | lc_cov.get("testing", set()),
            comp_cov.get("services", set())
            | comp_cov.get("modalities", set())
            | comp_cov.get("testing", set()),
        ),
        "location_gap_score": _gap_score(
            lc_cov.get("locations", set()), comp_cov.get("locations", set())
        ),
        "modality_gap_score": _gap_score(
            lc_cov.get("modalities", set()), comp_cov.get("modalities", set())
        ),
        "testing_gap_score": _gap_score(
            lc_cov.get("testing", set()), comp_cov.get("testing", set())
        ),
    }

    # ── Top pages per category (by word count) ────────────────────────────
    top_pages: dict[str, list[dict]] = defaultdict(list)
    for page in pages:
        cat = _classify_page(page)
        top_pages[cat].append(page)
    for cat in top_pages:
        top_pages[cat] = sorted(
            top_pages[cat], key=lambda p: p.get("word_count", 0), reverse=True
        )[:5]

    # ── Overview ──────────────────────────────────────────────────────────
    pages_by_cat = Counter(_classify_page(p) for p in pages)
    avg_word_count = sum(p.get("word_count", 0) for p in pages) / len(pages) if pages else 0

    overview = {
        "page_count": len(pages),
        "avg_word_count": round(avg_word_count),
        "service_pages": pages_by_cat.get("service", 0),
        "testing_pages": pages_by_cat.get("testing", 0),
        "modality_pages": pages_by_cat.get("modality", 0),
        "location_pages": pages_by_cat.get("location", 0),
        "condition_pages": pages_by_cat.get("condition", 0),
        "general_pages": pages_by_cat.get("general", 0),
        "service_coverage": len(comp_cov.get("services", set())),
        "location_coverage": len(comp_cov.get("locations", set())),
        "modality_coverage": len(comp_cov.get("modalities", set())),
        "testing_coverage": len(comp_cov.get("testing", set())),
    }

    recommendations = _build_recommendations(gaps, gap_scores, pages_by_cat, avg_word_count)

    return {
        "domain": domain,
        "page_count": len(pages),
        "crawled": True,
        "overview": overview,
        "lc_coverage": {k: sorted(v) for k, v in lc_cov.items()},
        "comp_coverage": {k: sorted(v) for k, v in comp_cov.items()},
        "gaps": gaps,
        "gap_scores": gap_scores,
        "top_pages": dict(top_pages),
        "recommendations": recommendations,
    }
