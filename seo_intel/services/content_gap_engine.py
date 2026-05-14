"""
seo_intel/services/content_gap_engine.py
-----------------------------------------
Content gap analysis engine.

Compares what competitors rank for (CompetitorSERPResult) with what
LC Psych ranks for (SearchConsoleQuery) and what the site already has
(Service, Page, GeoState, GeoLocation) to surface actionable content gaps.

Public API
----------
    run_gap_analysis()  -> GapSummary

    GapSummary.created  — new ContentGapRecord rows written
    GapSummary.updated  — existing rows refreshed
    GapSummary.total    — total rows in this run
    GapSummary.by_action — dict mapping action label → count
    GapSummary.keywords — list of GapKeyword dataclass instances

Internal pipeline
-----------------
1. Build site catalog:  Service slugs/titles, Page paths/titles,
   GeoState names/slugs, GeoLocation names/slugs
2. Aggregate SearchConsoleQuery by keyword:
   total impressions (volume proxy), set of LC Psych pages that rank
3. Collect CompetitorSERPResult keywords
4. Form keyword universe = union of GSC keywords + competitor keywords
5. For each keyword:
   a. lcpsych_presence  = keyword in GSC data (we rank for it)
   b. competitor_presence = keyword in CompetitorSERPResult
   c. search_volume      = total impressions from GSC (0 if not in GSC)
   d. recommended_action = classify() — see rules below

Recommended action classification (first match wins)
------------------------------------------------------
"Optimize existing page"   — LC Psych already ranks AND content catalog
                              contains a strong keyword match
"Create new location page" — keyword contains a known location term or
                              geo signals ("near me", "in [state/city]")
"Add modality page"        — keyword contains a therapy modality signal
"Add testing page"         — keyword contains assessment/testing signals
"Create new service page"  — everything else (new topic for LC Psych)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import DefaultDict

from django.db.models import Sum
from django.utils import timezone


# ---------------------------------------------------------------------------
# Domain vocabulary — keyword signal dictionaries
# ---------------------------------------------------------------------------

# Therapy modalities / treatment approaches
_MODALITY_SIGNALS: frozenset[str] = frozenset(
    {
        "emdr", "cbt", "dbt", "act", "eft", "mbsr", "mbct", "pcit", "tfcbt",
        "cognitive behavioral", "dialectical behavior", "acceptance commitment",
        "exposure therapy", "somatic", "mindfulness", "narrative therapy",
        "psychodynamic", "humanistic", "integrative", "solution focused",
        "motivational interviewing", "play therapy", "art therapy",
        "sand tray", "gottman", "internal family systems", "ifs therapy",
        "brainspotting", "havening", "neurofeedback",
    }
)

# Psychological testing / assessment signals
_TESTING_SIGNALS: frozenset[str] = frozenset(
    {
        "testing", "assessment", "evaluation", "neuropsychological",
        "psychoeducational", "iq test", "adhd test", "adhd evaluation",
        "autism assessment", "autism evaluation", "learning disability",
        "cognitive assessment", "psychological evaluation",
        "educational testing", "gifted testing", "gifted evaluation",
        "intelligence test", "memory test", "executive function",
    }
)

# Geographic signal words (beyond named places)
_GEO_SIGNAL_WORDS: frozenset[str] = frozenset(
    {"near me", "nearby", "local", "in kentucky", "in ohio", "in indiana",
     "in tennessee", "ky", "therapist near"}
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GapKeyword:
    keyword: str
    search_volume: int
    lcpsych_presence: bool
    competitor_presence: bool
    recommended_action: str


@dataclass
class GapSummary:
    created: int = 0
    updated: int = 0
    by_action: DefaultDict[str, int] = field(
        default_factory=lambda: DefaultDict(int)
    )
    keywords: list[GapKeyword] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated


# ---------------------------------------------------------------------------
# Site catalog builder
# ---------------------------------------------------------------------------

def _build_site_catalog() -> dict:
    """
    Return a dict with sets of normalised terms that describe existing
    LC Psych content.  All strings are lowercased.

    Keys
    ----
    service_terms  — set of individual words + full titles from Service
    page_terms     — set of path segments + full titles from Page
    geo_terms      — set of city/county/state names and their slug tokens
    """
    from core.models import Page, Service
    from geo.models import GeoLocation, GeoState

    service_terms: set[str] = set()
    for s in Service.objects.values_list("title", "slug"):
        title, slug = s
        service_terms.add(title.lower())
        service_terms.update(title.lower().split())
        service_terms.update(slug.lower().replace("-", " ").split())

    page_terms: set[str] = set()
    for title, path in Page.objects.values_list("title", "path"):
        page_terms.add(title.lower())
        for segment in path.lower().replace("-", " ").split("/"):
            page_terms.update(segment.split())

    geo_terms: set[str] = set()
    for name, slug in GeoState.objects.values_list("name", "slug"):
        geo_terms.add(name.lower())
        geo_terms.update(slug.lower().replace("-", " ").split())
    for name, slug in GeoLocation.objects.values_list("name", "slug"):
        geo_terms.add(name.lower())
        geo_terms.update(slug.lower().replace("-", " ").split())
    # Always include the state abbreviations for KY / OH / IN / TN
    geo_terms.update({"kentucky", "ky", "ohio", "oh", "indiana", "in",
                      "tennessee", "tn", "lexington", "louisville",
                      "cincinnati", "covington", "florence", "bowling green"})

    return {
        "service_terms": service_terms,
        "page_terms": page_terms,
        "geo_terms": geo_terms,
    }


# ---------------------------------------------------------------------------
# Keyword classifier
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _contains_any(text: str, signals: frozenset[str]) -> bool:
    for signal in signals:
        if signal in text:
            return True
    return False


def _keyword_touches_catalog(keyword: str, catalog_terms: set[str]) -> bool:
    """True if any word in keyword appears in the catalog term set."""
    for word in keyword.split():
        if len(word) > 3 and word in catalog_terms:  # skip tiny stop-words
            return True
    # Also check the full phrase
    return keyword in catalog_terms


def classify_keyword(
    keyword: str,
    lcpsych_presence: bool,
    catalog: dict,
) -> str:
    """
    Return a recommended_action string for the keyword.

    Priority order (first matching rule wins):
    1. Already ranked + existing service/page match → "Optimize existing page"
    2. Geo signals → "Create new location page"
    3. Modality signals → "Add modality page"
    4. Testing signals → "Add testing page"
    5. Default → "Create new service page"
    """
    kw = _normalise(keyword)

    # Rule 1 — already ranking and content exists
    if lcpsych_presence and (
        _keyword_touches_catalog(kw, catalog["service_terms"])
        or _keyword_touches_catalog(kw, catalog["page_terms"])
    ):
        return "Optimize existing page"

    # Rule 2 — geographic intent
    if (
        _contains_any(kw, _GEO_SIGNAL_WORDS)
        or _keyword_touches_catalog(kw, catalog["geo_terms"])
        # "therapist in X", "therapy near me", etc.
        or re.search(r"\b(therapist|therapy|counselor|psychologist)\s+\w*\s*(near|in)\b", kw)
        or re.search(r"\bnear me\b", kw)
    ):
        return "Create new location page"

    # Rule 3 — therapy modality
    if _contains_any(kw, _MODALITY_SIGNALS):
        return "Add modality page"

    # Rule 4 — testing / assessment
    if _contains_any(kw, _TESTING_SIGNALS):
        return "Add testing page"

    # Rule 1 fallback — has presence but doesn't match above patterns
    if lcpsych_presence:
        return "Optimize existing page"

    # Default
    return "Create new service page"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run_gap_analysis(min_impressions: int = 0) -> GapSummary:
    """
    Run the full content gap analysis pipeline.

    Parameters
    ----------
    min_impressions:
        Exclude keywords with total impressions below this threshold when
        sourced from GSC.  Competitor-sourced keywords always pass through
        (they have 0 impressions in our GSC data by definition).

    Returns
    -------
    GapSummary with counts and full keyword list.
    """
    from seo_intel.models import (
        CompetitorSERPResult,
        ContentGapRecord,
        SearchConsoleQuery,
    )

    now = timezone.now()
    catalog = _build_site_catalog()

    # ---- Step 1: aggregate GSC by keyword --------------------------------
    # Sum impressions across all dates/pages for each query
    gsc_agg: dict[str, int] = {}  # keyword -> total impressions
    for row in (
        SearchConsoleQuery.objects
        .values("query")
        .annotate(total_impressions=Sum("impressions"))
        .order_by()
    ):
        keyword = _normalise(row["query"])
        if keyword:
            gsc_agg[keyword] = gsc_agg.get(keyword, 0) + (row["total_impressions"] or 0)

    # ---- Step 2: collect competitor keywords ------------------------------
    competitor_keywords: set[str] = set()
    for kw in CompetitorSERPResult.objects.values_list("keyword", flat=True).distinct():
        normalised = _normalise(kw)
        if normalised:
            competitor_keywords.add(normalised)

    # ---- Step 3: build keyword universe -----------------------------------
    # GSC keywords passing the impression threshold + all competitor keywords
    universe: dict[str, int] = {}  # keyword -> impressions

    for kw, impressions in gsc_agg.items():
        if impressions >= min_impressions:
            universe[kw] = impressions

    for kw in competitor_keywords:
        if kw not in universe:
            universe[kw] = 0  # competitor only; no GSC volume

    # ---- Step 4: analyse each keyword ------------------------------------
    summary = GapSummary()

    for keyword, impressions in universe.items():
        lcpsych_presence = keyword in gsc_agg
        competitor_presence = keyword in competitor_keywords
        recommended_action = classify_keyword(keyword, lcpsych_presence, catalog)

        gap_kw = GapKeyword(
            keyword=keyword,
            search_volume=impressions,
            lcpsych_presence=lcpsych_presence,
            competitor_presence=competitor_presence,
            recommended_action=recommended_action,
        )
        summary.keywords.append(gap_kw)
        summary.by_action[recommended_action] += 1

        # Upsert: one record per keyword (latest run wins)
        obj, created = ContentGapRecord.objects.update_or_create(
            keyword=keyword,
            defaults={
                "search_volume": impressions,
                "lcpsych_presence": lcpsych_presence,
                "competitor_presence": competitor_presence,
                "recommended_action": recommended_action,
                "timestamp": now,
            },
        )
        if created:
            summary.created += 1
        else:
            summary.updated += 1

    return summary
