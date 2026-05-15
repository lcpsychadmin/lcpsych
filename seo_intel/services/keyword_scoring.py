"""
seo_intel/services/keyword_scoring.py
--------------------------------------
Scoring engine that ranks keywords by SEO priority for LC Psych.

Each keyword receives five sub-scores that sum to a ``priority_score`` of 0-100:

    Sub-score                   Max    Rationale
    ─────────────────────────── ───    ─────────────────────────────────────────
    search_demand_score          25    GSC impressions (log-scaled)
    competitor_pressure_score    25    # of competitor domains in top-10 SERP
    lcpsych_presence_score       25    LC Psych's best organic rank
    local_intent_score           15    Keyword contains a local geo term
    commercial_intent_score      10    Keyword contains a clinical/service term

Public API
----------
    load_geo_terms() -> frozenset[str]
    score_keyword(keyword, *, gsc_stats, competitor_ranks, lcpsych_ranks,
                  geo_terms) -> dict
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Commercial-intent vocabulary
# ---------------------------------------------------------------------------

_COMMERCIAL_TERMS: frozenset[str] = frozenset(
    {
        "therapy",
        "therapist",
        "counseling",
        "counselor",
        "psychologist",
        "psychiatrist",
        "psychiatric",
        "testing",
        "evaluation",
        "assessment",
        "diagnosis",
        "diagnose",
        "treatment",
        "adhd",
        "autism",
        "anxiety",
        "depression",
        "trauma",
        "ocd",
        "ptsd",
        "telehealth",
        "neurodivergent",
        "executive functioning",
        "somatic",
        "perinatal",
        "postpartum",
        "burnout",
        "ketamine",
    }
)

# Baseline local-intent terms (extended at runtime from the geo DB)
_DEFAULT_LOCAL_TERMS: frozenset[str] = frozenset(
    {
        "florence",
        "covington",
        "newport",
        "erlanger",
        "lexington",
        "cincinnati",
        "northern kentucky",
        "nky",
        "kentucky",
        "ohio",
        "bellevue",
        "dayton",
        "fort mitchell",
        "fort thomas",
        "highland heights",
        "independence",
        "union",
        "burlington",
        "boone county",
        "campbell county",
        "kenton county",
        "ky",
        "oh",
        "near me",
    }
)


# ---------------------------------------------------------------------------
# Geo-term loader
# ---------------------------------------------------------------------------


def load_geo_terms() -> frozenset[str]:
    """
    Return a frozenset of lowercase local geography strings to use in
    :func:`score_keyword`.

    Queries the active ``GeoLocation`` and ``GeoState`` records from the ``geo``
    app and merges them with :data:`_DEFAULT_LOCAL_TERMS`.  If the geo app is
    unavailable the defaults are returned unchanged.
    """
    terms: set[str] = set(_DEFAULT_LOCAL_TERMS)
    try:
        from geo.models import GeoLocation, GeoState  # noqa: PLC0415

        for name in GeoLocation.objects.filter(is_active=True).values_list(
            "name", flat=True
        ):
            if name:
                terms.add(name.lower())

        for name, abbr in GeoState.objects.filter(is_active=True).values_list(
            "name", "abbreviation"
        ):
            if name:
                terms.add(name.lower())
            if abbr:
                terms.add(abbr.lower())

    except Exception:
        logger.debug("load_geo_terms: geo app unavailable; using defaults.")

    return frozenset(terms)


# ---------------------------------------------------------------------------
# Sub-score helpers
# ---------------------------------------------------------------------------


def _search_demand_score(impressions: int) -> int:
    """
    0–25.  Log₁₀-scaled so that a keyword with 100 impressions ≈ 14 pts and
    one with 10 000 impressions ≈ 25 pts.
    """
    if impressions <= 0:
        return 0
    return min(25, int(math.log10(impressions + 1) * 7))


def _competitor_pressure_score(ranks: list[int]) -> int:
    """
    0–25.  Counts distinct competitor rank positions that fall in top 10;
    each adds 5 points (capped at 25 = 5 competitors).
    """
    top10 = [r for r in ranks if 1 <= r <= 10]
    return min(25, len(top10) * 5)


def _lcpsych_presence_score(ranks: list[int]) -> int:
    """
    0–25.  Reflects how visible LC Psych already is for this keyword.

    - Not in top 10 → 5   (low — not yet ranking)
    - Ranks 4–10    → 15  (medium — ranking but improvable)
    - Ranks 1–3     → 25  (high — already a top result)
    """
    if not ranks:
        return 5
    best = min(ranks)
    if best <= 3:
        return 25
    if best <= 10:
        return 15
    return 5


def _local_intent_score(keyword_lower: str, geo_terms: frozenset[str]) -> int:
    """
    0 or 15.  Returns 15 if any geo term appears as a substring of the keyword,
    0 otherwise.  Longer multi-word terms are naturally checked via substring
    match (e.g. "northern kentucky" will match before individual words do).
    """
    for term in geo_terms:
        if term in keyword_lower:
            return 15
    return 0


def _commercial_intent_score(keyword_lower: str) -> int:
    """
    0–10.  Each clinical/service term found in the keyword adds 5 points,
    capped at 10 (i.e. 1 match = 5 pts, 2+ matches = 10 pts).
    """
    hits = sum(1 for term in _COMMERCIAL_TERMS if term in keyword_lower)
    return min(10, hits * 5)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_keyword(
    keyword: str,
    *,
    gsc_stats: dict[str, dict],
    competitor_ranks: dict[str, list[int]],
    lcpsych_ranks: dict[str, list[int]],
    geo_terms: frozenset[str],
) -> dict:
    """
    Compute all sub-scores and the final ``priority_score`` for *keyword*.

    Parameters
    ----------
    keyword:
        The phrase to score (case-sensitive; matching is done in lower-case).
    gsc_stats:
        Mapping ``keyword → {"impressions": int, "clicks": int}``.
        Build with an aggregated ``SearchConsoleQuery`` query before calling
        this function for many keywords (avoid N+1 queries).
    competitor_ranks:
        Mapping ``keyword → [rank, rank, …]`` listing every organic position
        where a competitor domain was detected.
    lcpsych_ranks:
        Mapping ``keyword → [rank, rank, …]`` listing every organic position
        where LC Psych was detected.
    geo_terms:
        Lowercase geography strings; call :func:`load_geo_terms` once and
        pass the result here.

    Returns
    -------
    dict with keys: ``keyword``, ``search_demand_score``,
    ``competitor_pressure_score``, ``lcpsych_presence_score``,
    ``local_intent_score``, ``commercial_intent_score``, ``priority_score``.
    ``priority_score`` is always in the range 0–100.
    """
    kw_lower = keyword.lower()

    stats = gsc_stats.get(keyword, {})
    impressions: int = stats.get("impressions", 0)

    sd = _search_demand_score(impressions)
    cp = _competitor_pressure_score(competitor_ranks.get(keyword, []))
    lp = _lcpsych_presence_score(lcpsych_ranks.get(keyword, []))
    li = _local_intent_score(kw_lower, geo_terms)
    ci = _commercial_intent_score(kw_lower)

    priority = sd + cp + lp + li + ci  # 0–100

    return {
        "keyword": keyword,
        "search_demand_score": sd,
        "competitor_pressure_score": cp,
        "lcpsych_presence_score": lp,
        "local_intent_score": li,
        "commercial_intent_score": ci,
        "priority_score": priority,
    }
