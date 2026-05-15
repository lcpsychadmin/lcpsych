"""
seo_intel/api.py
-----------------
Staff-only JSON data endpoints for the SEO Intelligence portal.

All endpoints:
  • Require authenticated staff / superuser (401 / 403 JSON on failure)
  • Accept GET only (405 JSON otherwise)
  • Return Content-Type: application/json

URL summary (registered in seo_intel/urls.py under api/seo/ prefix):
  GET api/seo/keyword-scores/     → KeywordScore rows with sub-scores
  GET api/seo/competitor-hits/    → CompetitorHit rows (filterable by keyword / domain)
  GET api/seo/lc-hits/            → LCPsychHit rows (filterable by keyword)
  GET api/seo/content-gaps/       → Enriched ContentGapRecord rows
  GET api/seo/search-console/     → GSC time-series + top queries + summary
  GET api/seo/internal-search/    → InternalSearchQuery term frequencies
  GET api/seo/dead-urls/          → DeadURLHit path frequencies

Consumers
---------
Analytics Hub      — search-console, internal-search, dead-urls, competitor-hits,
                     keyword-scores (for priority distribution)
SERP Explorer      — competitor-hits, lc-hits, keyword-scores
Keyword Universe   — keyword-scores, competitor-hits (?best_only=1), lc-hits (?best_only=1)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import wraps

from django.db.models import Avg, Count, Min, Sum
from django.http import JsonResponse

from seo_intel.models import (
    CompetitorHit,
    ContentGapRecord,
    DeadURLHit,
    InternalSearchQuery,
    KeywordScore,
    LCPsychHit,
    SearchConsoleQuery,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def _staff_required(view_func):
    """Enforce authenticated-staff + GET-only; return JSON on failure."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Login required"}, status=401)
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)
        if request.method != "GET":
            return JsonResponse({"status": "error", "message": "GET required"}, status=405)
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clamp(raw, default: int, lo: int, hi: int) -> int:
    """Parse an integer query-param, clamp to [lo, hi], fall back to default."""
    try:
        return max(lo, min(int(raw), hi))
    except (TypeError, ValueError):
        return default


def _cutoff(days: int) -> date:
    return date.today() - timedelta(days=days)


# ---------------------------------------------------------------------------
# 1. Keyword Scores
# ---------------------------------------------------------------------------

@_staff_required
def keyword_scores(request):
    """
    GET /api/seo/keyword-scores/

    Query params:
      keyword    — exact keyword filter
      cat        — category filter (service | testing | modality | location)
      min_score  — minimum priority_score (0–100)
      limit      — max rows returned (default 200, max 500)

    Response:
      {"count": N, "results": [{keyword, category, priority_score,
        search_demand_score, competitor_pressure_score,
        lcpsych_presence_score, local_intent_score,
        commercial_intent_score, scored_at}]}
    """
    kw_filter = request.GET.get("keyword", "").strip()
    cat_filter = request.GET.get("cat", "").strip()
    limit = _clamp(request.GET.get("limit"), 200, 1, 500)

    qs = KeywordScore.objects.all()

    if kw_filter:
        qs = qs.filter(keyword=kw_filter)

    min_score_raw = request.GET.get("min_score", "")
    if min_score_raw:
        try:
            qs = qs.filter(priority_score__gte=int(min_score_raw))
        except ValueError:
            pass

    # Category filter — join against KeywordSeed
    if cat_filter:
        from seo_settings.models import KeywordSeed
        seed_kws = set(
            KeywordSeed.objects
            .filter(category=cat_filter)
            .values_list("keyword", flat=True)
        )
        qs = qs.filter(keyword__in=seed_kws)

    qs = qs.order_by("-priority_score")[:limit]

    # Annotate with category
    from seo_settings.models import KeywordSeed
    cat_map: dict[str, str] = dict(
        KeywordSeed.objects.values_list("keyword", "category")
    )

    results = [
        {
            "keyword": s.keyword,
            "category": cat_map.get(s.keyword, ""),
            "priority_score": s.priority_score,
            "search_demand_score": s.search_demand_score,
            "competitor_pressure_score": s.competitor_pressure_score,
            "lcpsych_presence_score": s.lcpsych_presence_score,
            "local_intent_score": s.local_intent_score,
            "commercial_intent_score": s.commercial_intent_score,
            "scored_at": s.timestamp.isoformat(),
        }
        for s in qs
    ]

    return JsonResponse({"count": len(results), "results": results})


# ---------------------------------------------------------------------------
# 2. Competitor Hits
# ---------------------------------------------------------------------------

@_staff_required
def competitor_hits(request):
    """
    GET /api/seo/competitor-hits/

    Query params:
      keyword    — filter by keyword
      domain     — filter by competitor_domain
      days       — restrict to last N days (default: all time)
      limit      — max rows / groups (default 100, max 500)
      summarize  — '1' → best rank + count per keyword×domain (good for distribution charts)

    Response (default):
      {"count": N, "results": [{keyword, competitor_domain, url, title, rank, timestamp}]}

    Response (summarize=1):
      {"count": N, "results": [{keyword, competitor_domain, best_rank, hit_count}]}
    """
    kw_filter = request.GET.get("keyword", "").strip()
    domain_filter = request.GET.get("domain", "").strip()
    limit = _clamp(request.GET.get("limit"), 100, 1, 500)
    summarize = request.GET.get("summarize") == "1"
    days_raw = request.GET.get("days", "")

    qs = CompetitorHit.objects.all()

    if kw_filter:
        qs = qs.filter(keyword=kw_filter)
    if domain_filter:
        qs = qs.filter(competitor_domain=domain_filter)
    if days_raw:
        try:
            qs = qs.filter(timestamp__date__gte=_cutoff(int(days_raw)))
        except ValueError:
            pass

    if summarize:
        rows = (
            qs.values("keyword", "competitor_domain")
            .annotate(best_rank=Min("rank"), hit_count=Count("id"))
            .order_by("keyword", "best_rank")[:limit]
        )
        results = [
            {
                "keyword": r["keyword"],
                "competitor_domain": r["competitor_domain"],
                "best_rank": r["best_rank"],
                "hit_count": r["hit_count"],
            }
            for r in rows
        ]
    else:
        hits = list(qs.order_by("-timestamp", "rank")[:limit])
        results = [
            {
                "keyword": h.keyword,
                "competitor_domain": h.competitor_domain,
                "url": h.url,
                "title": h.title,
                "rank": h.rank,
                "timestamp": h.timestamp.isoformat(),
            }
            for h in hits
        ]

    return JsonResponse({"count": len(results), "results": results})


# ---------------------------------------------------------------------------
# 3. LC Psych Hits
# ---------------------------------------------------------------------------

@_staff_required
def lc_hits(request):
    """
    GET /api/seo/lc-hits/

    Query params:
      keyword    — filter by keyword
      days       — restrict to last N days (default: all time)
      limit      — max rows / groups (default 100, max 500)
      best_only  — '1' → best rank per keyword only

    Response (default):
      {"count": N, "results": [{keyword, url, title, rank, timestamp}]}

    Response (best_only=1):
      {"count": N, "results": [{keyword, best_rank, hit_count}]}
    """
    kw_filter = request.GET.get("keyword", "").strip()
    limit = _clamp(request.GET.get("limit"), 100, 1, 500)
    days_raw = request.GET.get("days", "")
    best_only = request.GET.get("best_only") == "1"

    qs = LCPsychHit.objects.all()

    if kw_filter:
        qs = qs.filter(keyword=kw_filter)
    if days_raw:
        try:
            qs = qs.filter(timestamp__date__gte=_cutoff(int(days_raw)))
        except ValueError:
            pass

    if best_only:
        rows = (
            qs.values("keyword")
            .annotate(best_rank=Min("rank"), hit_count=Count("id"))
            .order_by("best_rank")[:limit]
        )
        results = [
            {
                "keyword": r["keyword"],
                "best_rank": r["best_rank"],
                "hit_count": r["hit_count"],
            }
            for r in rows
        ]
    else:
        hits = list(qs.order_by("-timestamp", "rank")[:limit])
        results = [
            {
                "keyword": h.keyword,
                "url": h.url,
                "title": h.title,
                "rank": h.rank,
                "timestamp": h.timestamp.isoformat(),
            }
            for h in hits
        ]

    return JsonResponse({"count": len(results), "results": results})


# ---------------------------------------------------------------------------
# 4. Content Gaps
# ---------------------------------------------------------------------------

_VALID_RECOMMENDED_ACTIONS = frozenset({
    "Optimize existing page",
    "Create new location page",
    "Add modality page",
    "Add testing page",
    "Create new service page",
})

_VALID_CATEGORIES = frozenset({"service", "testing", "modality", "location"})

_CATEGORY_LABELS = {
    "service": "Service",
    "testing": "Testing",
    "modality": "Modality",
    "location": "Location",
}


@_staff_required
def content_gaps(request):
    """
    GET /api/seo/content-gaps/

    Query params:
      keyword_type    — category filter (service | testing | modality | location | unseed)
      action          — recommended_action exact match
      min_score       — minimum priority_score (0–100)
      has_lc          — '1' only LC-present, '0' only LC-absent
      has_competitor  — '1' only competitor-present
      resolved        — '1' show resolved only; default shows unresolved
      limit           — max rows (default 200, max 1000)

    Response:
      {
        "count": N,
        "unresolved_total": N,
        "resolved_total": N,
        "results": [{id, keyword, keyword_type, keyword_type_display,
                     priority_score, search_volume, lc_presence,
                     competitor_presence, recommended_action,
                     resolved, timestamp}]
      }
    """
    get = request.GET
    kw_type = get.get("keyword_type", "").strip()
    action_filter = get.get("action", "").strip()
    min_score_raw = get.get("min_score", "").strip()
    has_lc = get.get("has_lc", "")
    has_competitor = get.get("has_competitor", "")
    show_resolved = get.get("resolved", "0")
    limit = _clamp(get.get("limit"), 200, 1, 1000)

    # DB-level filters
    if show_resolved == "1":
        qs = ContentGapRecord.objects.filter(resolved=True)
    else:
        qs = ContentGapRecord.objects.filter(resolved=False, ignored=False)

    if has_lc == "1":
        qs = qs.filter(lcpsych_presence=True)
    elif has_lc == "0":
        qs = qs.filter(lcpsych_presence=False)

    if has_competitor == "1":
        qs = qs.filter(competitor_presence=True)

    if action_filter and action_filter in _VALID_RECOMMENDED_ACTIONS:
        qs = qs.filter(recommended_action=action_filter)

    # Enrichment lookups
    from seo_settings.models import KeywordSeed
    seed_categories: dict[str, str] = dict(
        KeywordSeed.objects.values_list("keyword", "category")
    )
    scores: dict[str, int] = dict(
        KeywordScore.objects.values_list("keyword", "priority_score")
    )

    records = list(qs.order_by("-search_volume", "keyword")[:limit])

    min_score: int | None = None
    if min_score_raw:
        try:
            min_score = int(min_score_raw)
        except ValueError:
            pass

    results = []
    for rec in records:
        kw = rec.keyword
        cat = seed_categories.get(kw, "")
        score = scores.get(kw, 0)

        # Python-level category filter
        if kw_type:
            if kw_type == "unseed" and cat:
                continue
            elif kw_type != "unseed" and cat != kw_type:
                continue

        if min_score is not None and score < min_score:
            continue

        results.append({
            "id": rec.pk,
            "keyword": kw,
            "keyword_type": cat,
            "keyword_type_display": _CATEGORY_LABELS.get(cat, "—") if cat else "—",
            "priority_score": score,
            "search_volume": rec.search_volume,
            "lc_presence": rec.lcpsych_presence,
            "competitor_presence": rec.competitor_presence,
            "recommended_action": rec.recommended_action,
            "resolved": rec.resolved,
            "timestamp": rec.timestamp.isoformat(),
        })

    results.sort(key=lambda r: (-r["priority_score"], -r["search_volume"]))

    unresolved_total = ContentGapRecord.objects.filter(resolved=False, ignored=False).count()
    resolved_total = ContentGapRecord.objects.filter(resolved=True).count()

    return JsonResponse({
        "count": len(results),
        "unresolved_total": unresolved_total,
        "resolved_total": resolved_total,
        "results": results,
    })


# ---------------------------------------------------------------------------
# 5. Search Console Metrics
# ---------------------------------------------------------------------------

@_staff_required
def search_console(request):
    """
    GET /api/seo/search-console/

    Query params:
      days   — lookback window in days (default 30, max 365)
      top    — number of top queries to return (default 10, max 50)

    Response:
      {
        "days": N,
        "summary": {total_impressions, total_clicks, avg_ctr, avg_position},
        "time_series": {
          "labels": ["YYYY-MM-DD", ...],
          "impressions": [...],
          "clicks": [...]
        },
        "top_queries": [{query, clicks, impressions, avg_ctr, avg_position}]
      }
    """
    days = _clamp(request.GET.get("days"), 30, 1, 365)
    top = _clamp(request.GET.get("top"), 10, 1, 50)
    cutoff = _cutoff(days)

    period_qs = SearchConsoleQuery.objects.filter(date__gte=cutoff)

    # Aggregate summary
    agg = period_qs.aggregate(
        total_impressions=Sum("impressions"),
        total_clicks=Sum("clicks"),
        avg_ctr=Avg("ctr"),
        avg_position=Avg("position"),
    )

    # Daily time series
    ts_rows = (
        period_qs
        .values("date")
        .annotate(impressions=Sum("impressions"), clicks=Sum("clicks"))
        .order_by("date")
    )
    time_series = {
        "labels": [r["date"].strftime("%Y-%m-%d") for r in ts_rows],
        "impressions": [r["impressions"] for r in ts_rows],
        "clicks": [r["clicks"] for r in ts_rows],
    }

    # Top queries by clicks
    top_rows = (
        period_qs
        .values("query")
        .annotate(
            clicks=Sum("clicks"),
            impressions=Sum("impressions"),
            avg_ctr=Avg("ctr"),
            avg_position=Avg("position"),
        )
        .order_by("-clicks")[:top]
    )
    top_queries = [
        {
            "query": r["query"],
            "clicks": r["clicks"],
            "impressions": r["impressions"],
            "avg_ctr": round(r["avg_ctr"] or 0.0, 4),
            "avg_position": round(r["avg_position"] or 0.0, 1),
        }
        for r in top_rows
    ]

    return JsonResponse({
        "days": days,
        "summary": {
            "total_impressions": agg["total_impressions"] or 0,
            "total_clicks": agg["total_clicks"] or 0,
            "avg_ctr": round(agg["avg_ctr"] or 0.0, 4),
            "avg_position": round(agg["avg_position"] or 0.0, 1),
        },
        "time_series": time_series,
        "top_queries": top_queries,
    })


# ---------------------------------------------------------------------------
# 6. Internal Search Metrics
# ---------------------------------------------------------------------------

@_staff_required
def internal_search(request):
    """
    GET /api/seo/internal-search/

    Query params:
      days   — lookback window (default 30, max 365; 0 = all time)
      limit  — number of top terms (default 20, max 100)

    Response:
      {"days": N, "total_queries": N, "top_terms": [{term, count}]}
    """
    days = _clamp(request.GET.get("days"), 30, 0, 365)
    limit = _clamp(request.GET.get("limit"), 20, 1, 100)

    qs = InternalSearchQuery.objects.all()
    if days > 0:
        qs = qs.filter(timestamp__date__gte=_cutoff(days))

    total = qs.count()

    top_rows = (
        qs.values("term")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )
    top_terms = [{"term": r["term"], "count": r["count"]} for r in top_rows]

    return JsonResponse({
        "days": days,
        "total_queries": total,
        "top_terms": top_terms,
    })


# ---------------------------------------------------------------------------
# 7. Dead URL Metrics
# ---------------------------------------------------------------------------

@_staff_required
def dead_urls(request):
    """
    GET /api/seo/dead-urls/

    Query params:
      days   — lookback window (default 30, max 365; 0 = all time)
      limit  — number of top paths (default 20, max 100)

    Response:
      {"days": N, "total_hits": N, "top_urls": [{url, count}]}
    """
    days = _clamp(request.GET.get("days"), 30, 0, 365)
    limit = _clamp(request.GET.get("limit"), 20, 1, 100)

    qs = DeadURLHit.objects.all()
    if days > 0:
        qs = qs.filter(timestamp__date__gte=_cutoff(days))

    total = qs.count()

    top_rows = (
        qs.values("url")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )
    top_urls = [{"url": r["url"], "count": r["count"]} for r in top_rows]

    return JsonResponse({
        "days": days,
        "total_hits": total,
        "top_urls": top_urls,
    })
