"""
seo_intel/services/keyword_trends_analyzer.py
----------------------------------------------
Keyword Seeds Intelligence Analyzer.

Aggregates data that has already been stored in the database (GSC, SERP,
CompetitorHit, LCPsychHit, KeywordSuggestion, KeywordScore) into a single
intelligence report per keyword seed.

No live SerpAPI calls are made here — all source data comes from the local DB.
Results are cached for 15 minutes to keep page loads fast.

Public API
----------
    analyze_seeds(seeds) -> list[dict]
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Min, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 15  # 15 minutes

# ---------------------------------------------------------------------------
# Local/commercial intent vocabulary (mirrors keyword_scoring.py)
# ---------------------------------------------------------------------------

_LOCAL_TERMS: frozenset[str] = frozenset(
    {
        "florence", "covington", "newport", "erlanger", "lexington",
        "cincinnati", "northern kentucky", "nky", "kentucky", "ohio",
        "bellevue", "dayton", "fort mitchell", "fort thomas",
        "highland heights", "independence", "union", "burlington",
        "boone county", "campbell county", "kenton county", "ky", "oh",
        "near me",
    }
)

_COMMERCIAL_TERMS: frozenset[str] = frozenset(
    {
        "therapy", "therapist", "counseling", "counselor",
        "psychologist", "psychiatrist", "psychiatric",
        "testing", "evaluation", "assessment", "diagnosis",
        "treatment", "adhd", "autism", "anxiety", "depression",
        "trauma", "ocd", "ptsd", "telehealth", "neurodivergent",
        "executive functioning", "somatic", "perinatal", "postpartum",
        "burnout", "ketamine",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_local_intent(kw: str) -> bool:
    kw_lower = kw.lower()
    return any(term in kw_lower for term in _LOCAL_TERMS)


def _has_commercial_intent(kw: str) -> bool:
    kw_lower = kw.lower()
    return any(term in kw_lower for term in _COMMERCIAL_TERMS)


def _trend_score(impressions_recent: int, impressions_prior: int) -> int:
    """
    0-100 trend score based on impression delta between two equal-length
    windows.  50 = flat, >50 = growing, <50 = declining.
    """
    if impressions_prior == 0 and impressions_recent == 0:
        return 0
    if impressions_prior == 0:
        return 80  # new traffic signal
    delta_pct = (impressions_recent - impressions_prior) / impressions_prior
    # Map [-1, +2] → [0, 100], clamp
    raw = 50 + (delta_pct * 25)
    return max(0, min(100, int(raw)))


def _recommended_action(
    lc_rank: int | None,
    top_competitor_rank: int | None,
    has_local: bool,
) -> str:
    """Derive a human-readable recommended action."""
    if lc_rank is None:
        if top_competitor_rank is not None and top_competitor_rank <= 3:
            return "Create new page — urgent (competitors dominate top 3)"
        if not has_local:
            return "Add local landing page"
        return "Create new page"
    if lc_rank <= 3:
        return "Strengthen content"
    if lc_rank <= 10:
        if top_competitor_rank is not None and top_competitor_rank < lc_rank:
            return "Optimize existing page — competitors ahead"
        return "Optimize existing page"
    return "Optimize existing page — low ranking"


def _action_css(action: str) -> str:
    """Map a recommended_action string to a CSS key used in the template."""
    action_l = action.lower()
    if "urgent" in action_l or "dominate" in action_l:
        return "red"
    if "create" in action_l:
        return "orange"
    if "local landing" in action_l:
        return "blue"
    if "strengthen" in action_l:
        return "green"
    if "optimize" in action_l:
        return "yellow"
    return "gray"


# ---------------------------------------------------------------------------
# Core analyzer
# ---------------------------------------------------------------------------

def _analyze_one(keyword: str, *, today: date, window: int = 30) -> dict:
    """Build the intelligence report for a single keyword string."""
    from seo_intel.models import (
        CompetitorHit,
        KeywordScore,
        KeywordSuggestion,
        LCPsychHit,
        SearchConsoleQuery,
    )

    kw_lower = keyword.lower()

    # ── Search Console impressions ─────────────────────────────────────────
    recent_start = today - timedelta(days=window)
    prior_start  = today - timedelta(days=window * 2)
    prior_end    = today - timedelta(days=window + 1)

    def _impressions(start: date, end: date) -> int:
        return (
            SearchConsoleQuery.objects.filter(
                query__iexact=keyword,
                date__gte=start,
                date__lte=end,
            ).aggregate(total=Sum("impressions"))["total"]
            or 0
        )

    impressions_recent = _impressions(recent_start, today)
    impressions_prior  = _impressions(prior_start, prior_end)
    impressions_90d    = _impressions(today - timedelta(days=90), today)
    clicks_90d = (
        SearchConsoleQuery.objects.filter(
            query__iexact=keyword,
            date__gte=today - timedelta(days=90),
        ).aggregate(total=Sum("clicks"))["total"]
        or 0
    )

    trend = _trend_score(impressions_recent, impressions_prior)

    # Impression delta label
    if impressions_prior == 0:
        delta_label = "no prior data"
        delta_direction = "neutral"
    else:
        pct = (impressions_recent - impressions_prior) / impressions_prior * 100
        sign = "+" if pct >= 0 else ""
        delta_label = f"{sign}{pct:.0f}% vs prior {window}d"
        delta_direction = "up" if pct > 5 else ("down" if pct < -5 else "neutral")

    # ── PAA / Related searches ─────────────────────────────────────────────
    suggestions_qs = KeywordSuggestion.objects.filter(
        source_keyword__iexact=keyword
    ).values("suggestion", "source_type", "used_as_seed")

    paa = []
    related = []
    for s in suggestions_qs:
        entry = {
            "text": s["suggestion"],
            "used_as_seed": s["used_as_seed"],
        }
        if s["source_type"] == KeywordSuggestion.PAA:
            paa.append(entry)
        else:
            related.append(entry)

    # ── Competitor hits ────────────────────────────────────────────────────
    cutoff_90 = timezone.now() - timedelta(days=90)
    competitor_qs = (
        CompetitorHit.objects.filter(
            keyword__iexact=keyword,
            timestamp__gte=cutoff_90,
        )
        .values("competitor_domain", "rank")
        .order_by("rank")
    )
    competitors: list[dict] = []
    seen_domains: set[str] = set()
    top_competitor_rank: int | None = None
    top3_domains: list[str] = []
    for hit in competitor_qs:
        domain = hit["competitor_domain"]
        rank   = hit["rank"]
        if domain not in seen_domains:
            seen_domains.add(domain)
            competitors.append({"domain": domain, "rank": rank})
            if top_competitor_rank is None:
                top_competitor_rank = rank
            if rank <= 3:
                top3_domains.append(domain)

    # Domain-level count
    competitor_domain_count = len(competitors)
    competitors_dominate_top3 = len(top3_domains) >= 2

    # ── LC Psych hits ──────────────────────────────────────────────────────
    lc_qs = (
        LCPsychHit.objects.filter(
            keyword__iexact=keyword,
            timestamp__gte=cutoff_90,
        )
        .order_by("rank")
        .values("url", "title", "rank")
        .first()
    )
    lc_rank: int | None = lc_qs["rank"] if lc_qs else None
    lc_url:  str | None = lc_qs["url"]  if lc_qs else None
    lc_title: str | None = lc_qs["title"] if lc_qs else None

    # ── Priority score ─────────────────────────────────────────────────────
    try:
        ks = KeywordScore.objects.get(keyword__iexact=keyword)
        priority_score            = ks.priority_score
        search_demand_score       = ks.search_demand_score
        competitor_pressure_score = ks.competitor_pressure_score
        lcpsych_presence_score    = ks.lcpsych_presence_score
        local_intent_score        = ks.local_intent_score
        commercial_intent_score   = ks.commercial_intent_score
    except KeywordScore.DoesNotExist:
        # Derive lightweight scores from available data
        local_intent_score      = 15 if _has_local_intent(keyword)      else 0
        commercial_intent_score = 10 if _has_commercial_intent(keyword) else 0
        lcpsych_presence_score  = (
            25 if lc_rank and lc_rank <= 3  else
            15 if lc_rank and lc_rank <= 10 else
             5 if lc_rank else 0
        )
        competitor_pressure_score = min(25, competitor_domain_count * 5)
        search_demand_score       = min(25, int((impressions_90d or 0) / 10))
        priority_score = (
            search_demand_score
            + competitor_pressure_score
            + lcpsych_presence_score
            + local_intent_score
            + commercial_intent_score
        )
        priority_score = min(100, priority_score)

    # ── Recommended action ─────────────────────────────────────────────────
    has_local = _has_local_intent(keyword)
    action = _recommended_action(lc_rank, top_competitor_rank, has_local)
    action_css = _action_css(action)

    # ── Priority score colour ──────────────────────────────────────────────
    if priority_score >= 70:
        score_css = "high"
    elif priority_score >= 40:
        score_css = "mid"
    elif priority_score > 0:
        score_css = "low"
    else:
        score_css = "none"

    # ── Trend badge ────────────────────────────────────────────────────────
    if trend >= 65:
        trend_css = "high"
    elif trend >= 35:
        trend_css = "mid"
    elif trend > 0:
        trend_css = "low"
    else:
        trend_css = "none"

    return {
        "keyword": keyword,
        # GSC
        "impressions_recent": impressions_recent,
        "impressions_prior": impressions_prior,
        "impressions_90d": impressions_90d,
        "clicks_90d": clicks_90d,
        "delta_label": delta_label,
        "delta_direction": delta_direction,
        "trend_score": trend,
        "trend_css": trend_css,
        # Expansion
        "paa": paa,
        "related": related,
        "has_expansion": bool(paa or related),
        # Competitors
        "competitors": competitors,
        "competitor_count": competitor_domain_count,
        "top_competitor_rank": top_competitor_rank,
        "top3_domains": top3_domains,
        "competitors_dominate_top3": competitors_dominate_top3,
        # LC Psych
        "lc_rank": lc_rank,
        "lc_url": lc_url,
        "lc_title": lc_title,
        # Scores
        "priority_score": priority_score,
        "score_css": score_css,
        "search_demand_score": search_demand_score,
        "competitor_pressure_score": competitor_pressure_score,
        "lcpsych_presence_score": lcpsych_presence_score,
        "local_intent_score": local_intent_score,
        "commercial_intent_score": commercial_intent_score,
        # Action
        "recommended_action": action,
        "action_css": action_css,
        # Intent flags
        "has_local_intent": has_local,
        "has_commercial_intent": _has_commercial_intent(keyword),
    }


def analyze_seeds(seeds) -> list[dict]:
    """
    Return an intelligence report for each seed.

    Parameters
    ----------
    seeds:
        Iterable of ``KeywordSeed`` instances (or any objects with a
        ``.keyword`` attribute).

    Returns
    -------
    List of report dicts, one per seed, sorted by priority_score descending.
    """
    seed_list = list(seeds)
    if not seed_list:
        return []

    # Build a stable cache key from the sorted keyword set
    kw_key = ",".join(sorted(s.keyword for s in seed_list))
    cache_key = "kw_intel_" + hashlib.md5(kw_key.encode()).hexdigest()

    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("keyword_trends_analyzer: cache hit (%d seeds)", len(seed_list))
        return cached

    today = date.today()
    results = []
    for seed in seed_list:
        try:
            report = _analyze_one(seed.keyword, today=today)
            report["category"] = seed.category
            report["seed_id"] = seed.pk
            report["active"] = seed.active
            results.append(report)
        except Exception:
            logger.exception("keyword_trends_analyzer: error analyzing %r", seed.keyword)

    # Sort by priority_score desc, then keyword alpha
    results.sort(key=lambda r: (-r["priority_score"], r["keyword"].lower()))

    cache.set(cache_key, results, _CACHE_TTL)
    logger.debug("keyword_trends_analyzer: computed + cached %d seeds", len(results))
    return results
