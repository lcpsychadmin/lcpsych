"""
seo_intel/views/analytics_hub.py
----------------------------------
Analytics Hub — unified dashboard with Chart.js charts for:

  • Search Console: impressions and clicks over the last 30 days
  • Internal Search: top 10 terms by count (all-time)
  • Dead URLs:       top 10 hit paths by count (all-time)
  • Competitor SERPs: ranking distribution across rank buckets
  • Keyword Scores:  priority-score distribution in 20-point buckets
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import redirect, render

from seo_intel.models import (
    CompetitorHit,
    DeadURLHit,
    InternalSearchQuery,
    KeywordScore,
    SearchConsoleQuery,
)

logger = logging.getLogger(__name__)

_DAYS = 30


# ---------------------------------------------------------------------------
# Auth helper (same pattern as other seo_intel views)
# ---------------------------------------------------------------------------

def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?{REDIRECT_FIELD_NAME}={request.path}')
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(obj):
    """Compact JSON string for embedding in a template."""
    return json.dumps(obj)


def _sc_time_series(cutoff: date):
    """Return (labels, impressions_data, clicks_data) for the last _DAYS days."""
    rows = (
        SearchConsoleQuery.objects
        .filter(date__gte=cutoff)
        .values('date')
        .annotate(impressions=Sum('impressions'), clicks=Sum('clicks'))
        .order_by('date')
    )
    labels = [r['date'].strftime('%b %-d') for r in rows]
    impressions = [r['impressions'] for r in rows]
    clicks = [r['clicks'] for r in rows]
    return labels, impressions, clicks


def _top_internal_searches(limit: int = 10):
    """Return (terms, counts) for the most frequent internal search terms."""
    rows = (
        InternalSearchQuery.objects
        .values('term')
        .annotate(count=Count('id'))
        .order_by('-count')[:limit]
    )
    terms = [r['term'] for r in rows]
    counts = [r['count'] for r in rows]
    return terms, counts


def _top_dead_urls(limit: int = 10):
    """Return (urls, counts) for the most-hit dead URL paths."""
    rows = (
        DeadURLHit.objects
        .values('url')
        .annotate(count=Count('id'))
        .order_by('-count')[:limit]
    )
    # Truncate long URLs for display
    urls = [r['url'][:80] + ('…' if len(r['url']) > 80 else '') for r in rows]
    counts = [r['count'] for r in rows]
    return urls, counts


def _competitor_rank_distribution():
    """Return (labels, counts) bucketed by rank range."""
    buckets = [
        ('Top 3', 1, 3),
        ('4–10', 4, 10),
        ('11–20', 11, 20),
        ('21+', 21, 9999),
    ]
    labels = [b[0] for b in buckets]
    counts = [
        CompetitorHit.objects.filter(rank__gte=lo, rank__lte=hi).count()
        for _, lo, hi in buckets
    ]
    return labels, counts


def _keyword_priority_distribution():
    """Return (labels, counts) bucketed by priority_score in 20-point increments."""
    buckets = [
        ('0–20', 0, 20),
        ('21–40', 21, 40),
        ('41–60', 41, 60),
        ('61–80', 61, 80),
        ('81–100', 81, 100),
    ]
    labels = [b[0] for b in buckets]
    counts = [
        KeywordScore.objects.filter(priority_score__gte=lo, priority_score__lte=hi).count()
        for _, lo, hi in buckets
    ]
    return labels, counts


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@_staff_required
def analytics_hub(request):
    cutoff = date.today() - timedelta(days=_DAYS)

    # --- Summary stats ---
    total_impressions = (
        SearchConsoleQuery.objects
        .filter(date__gte=cutoff)
        .aggregate(total=Sum('impressions'))['total'] or 0
    )
    total_clicks = (
        SearchConsoleQuery.objects
        .filter(date__gte=cutoff)
        .aggregate(total=Sum('clicks'))['total'] or 0
    )
    internal_search_count = InternalSearchQuery.objects.filter(
        timestamp__date__gte=cutoff
    ).count()
    dead_url_count = DeadURLHit.objects.filter(
        timestamp__date__gte=cutoff
    ).count()
    competitor_hit_count = CompetitorHit.objects.count()
    scored_keyword_count = KeywordScore.objects.count()

    # --- Chart data ---
    sc_labels, sc_impressions, sc_clicks = _sc_time_series(cutoff)
    search_terms, search_counts = _top_internal_searches()
    dead_urls, dead_counts = _top_dead_urls()
    rank_labels, rank_counts = _competitor_rank_distribution()
    priority_labels, priority_counts = _keyword_priority_distribution()

    context = {
        'active_page': 'analytics_hub',
        'days': _DAYS,

        # Summary stats
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'internal_search_count': internal_search_count,
        'dead_url_count': dead_url_count,
        'competitor_hit_count': competitor_hit_count,
        'scored_keyword_count': scored_keyword_count,

        # Chart.js JSON payloads
        'sc_labels_json': _json(sc_labels),
        'sc_impressions_json': _json(sc_impressions),
        'sc_clicks_json': _json(sc_clicks),

        'search_terms_json': _json(search_terms),
        'search_counts_json': _json(search_counts),

        'dead_urls_json': _json(dead_urls),
        'dead_counts_json': _json(dead_counts),

        'rank_labels_json': _json(rank_labels),
        'rank_counts_json': _json(rank_counts),

        'priority_labels_json': _json(priority_labels),
        'priority_counts_json': _json(priority_counts),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'seo_intel/partials/_analytics_content.html', context)
    return render(request, 'seo_intel/analytics_hub.html', context)
