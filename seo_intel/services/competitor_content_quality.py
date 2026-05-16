"""
seo_intel/services/competitor_content_quality.py
--------------------------------------------------
Content Quality Engine.

Scores each competitor page across multiple quality dimensions,
computes an aggregate quality_score (0-100), and identifies the
strongest and weakest competitor pages.

Public API
----------
    get_content_quality(domain: str) -> dict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Word-count quality tiers
_WC_EXCELLENT = 1200
_WC_GOOD = 800
_WC_AVERAGE = 500
_WC_THIN = 300


def _word_count_score(wc: int) -> int:
    if wc >= _WC_EXCELLENT:
        return 100
    if wc >= _WC_GOOD:
        return 80
    if wc >= _WC_AVERAGE:
        return 60
    if wc >= _WC_THIN:
        return 35
    return 10


def _heading_score(page: dict) -> int:
    h1s = page.get("h1", [])
    h2s = page.get("h2", [])
    if h1s and len(h2s) >= 5:
        return 100
    if h1s and len(h2s) >= 3:
        return 80
    if h1s and len(h2s) >= 1:
        return 60
    if h1s:
        return 40
    return 15


def _schema_score(page: dict) -> int:
    types = page.get("schema_types", [])
    n = len(types)
    if n >= 3:
        return 100
    if n == 2:
        return 75
    if n == 1:
        return 50
    return 0


def _link_score(page: dict) -> int:
    n = len(page.get("internal_links", []))
    if n >= 8:
        return 100
    if n >= 5:
        return 75
    if n >= 3:
        return 55
    if n >= 1:
        return 30
    return 0


def _keyword_richness_score(page: dict) -> int:
    hits = page.get("keyword_hits", {})
    total = sum(len(v) for v in hits.values())
    if total >= 10:
        return 100
    if total >= 6:
        return 75
    if total >= 3:
        return 55
    if total >= 1:
        return 30
    return 0


def _page_quality_score(page: dict) -> int:
    """Compute an aggregate 0-100 quality score for a single page."""
    return round(
        0.35 * _word_count_score(page.get("word_count", 0))
        + 0.25 * _heading_score(page)
        + 0.15 * _schema_score(page)
        + 0.15 * _link_score(page)
        + 0.10 * _keyword_richness_score(page)
    )


def _quality_css(score: int) -> str:
    if score >= 70:
        return "score-high"
    if score >= 45:
        return "score-mid"
    return "score-low"


def get_content_quality(domain: str) -> dict:
    """Return content quality analysis for a crawled competitor domain.

    Returns dict with keys:
        domain          str
        has_data        bool
        pages           list[dict]  – all pages scored, sorted best→worst
        summary         dict        – aggregate stats
        strong_pages    list[dict]  – top 15 scoring pages (threats)
        weak_pages      list[dict]  – bottom 15 scoring pages (opportunities)
    """
    from seo_intel.services.competitor_crawler import get_cached_crawl

    pages_raw = get_cached_crawl(domain) or []
    if not pages_raw:
        return {
            "domain": domain,
            "has_data": False,
            "pages": [],
            "summary": {},
            "strong_pages": [],
            "weak_pages": [],
        }

    scored: list[dict] = []
    for p in pages_raw:
        wc = p.get("word_count", 0)
        qs = _page_quality_score(p)
        scored.append({
            "url": p.get("url", ""),
            "title": p.get("title", "") or p.get("url", ""),
            "word_count": wc,
            "h1": (p.get("h1") or [])[:1],
            "h2_count": len(p.get("h2") or []),
            "schema_types": p.get("schema_types") or [],
            "internal_link_count": len(p.get("internal_links") or []),
            "keyword_hit_count": sum(len(v) for v in (p.get("keyword_hits") or {}).values()),
            "quality_score": qs,
            "word_count_score": _word_count_score(wc),
            "heading_score": _heading_score(p),
            "schema_score": _schema_score(p),
            "link_score": _link_score(p),
            "keyword_score": _keyword_richness_score(p),
            "quality_css": _quality_css(qs),
        })

    scored.sort(key=lambda p: p["quality_score"], reverse=True)

    n = len(scored)
    avg_quality = round(sum(p["quality_score"] for p in scored) / n)
    avg_words = round(sum(p["word_count"] for p in scored) / n)
    strong_count = sum(1 for p in scored if p["quality_score"] >= 70)
    weak_count = sum(1 for p in scored if p["quality_score"] < 45)

    return {
        "domain": domain,
        "has_data": True,
        "pages": scored,
        "summary": {
            "page_count": n,
            "avg_quality_score": avg_quality,
            "avg_word_count": avg_words,
            "strong_page_count": strong_count,
            "weak_page_count": weak_count,
            "quality_css": _quality_css(avg_quality),
        },
        "strong_pages": scored[:15],
        "weak_pages": list(reversed(scored))[:15],
    }
