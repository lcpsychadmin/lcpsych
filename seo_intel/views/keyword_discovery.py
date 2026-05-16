"""
seo_intel/views/keyword_discovery.py
--------------------------------------
Keyword Discovery view.

Renders the full discovery panel and supports HTMX partial refresh.
Filters: source, action, sort.
"""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)

VALID_SOURCES = {
    "search_console", "paa", "related", "competitor", "internal", "dead_url",
}
VALID_SORTS = {"priority", "trend", "keyword", "source"}


def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as django_settings
            login_url = getattr(django_settings, "LOGIN_URL", "/accounts/login/")
            return redirect(f"{login_url}?{REDIRECT_FIELD_NAME}={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


@_staff_required
def keyword_discovery(request):
    from seo_intel.services.keyword_discovery import SOURCE_LABELS, run_discovery

    # ── Filters ──────────────────────────────────────────────────────────
    source_filter  = request.GET.get("source", "")
    action_filter  = request.GET.get("action", "")
    sort_by        = request.GET.get("sort", "priority")
    force_refresh  = request.GET.get("refresh") == "1"

    if source_filter not in VALID_SOURCES:
        source_filter = ""
    if sort_by not in VALID_SORTS:
        sort_by = "priority"

    # ── Run discovery ─────────────────────────────────────────────────────
    all_results = run_discovery(force=force_refresh)

    # ── Source filter ─────────────────────────────────────────────────────
    if source_filter:
        results = [r for r in all_results if source_filter in r["sources"]]
    else:
        results = list(all_results)

    # ── Action filter ─────────────────────────────────────────────────────
    if action_filter:
        results = [
            r for r in results
            if action_filter.lower() in r["recommended_action"].lower()
        ]

    # ── Sort ──────────────────────────────────────────────────────────────
    if sort_by == "trend":
        results.sort(key=lambda r: (
            0 if r["trend_direction"] == "up" else
            1 if r["trend_direction"] == "neutral" else 2,
            -abs(r["trend_pct"]),
        ))
    elif sort_by == "keyword":
        results.sort(key=lambda r: r["keyword"].lower())
    elif sort_by == "source":
        results.sort(key=lambda r: (r["source"], -r["priority_score"]))
    # default: priority already sorted

    # ── Summary stats ─────────────────────────────────────────────────────
    total         = len(all_results)
    rising        = sum(1 for r in all_results if r["trend_direction"] == "up")
    competitor_gap = sum(1 for r in all_results if "competitor" in r["sources"])
    high_priority = sum(1 for r in all_results if r["priority_score"] >= 70)

    # Per-source counts (for tabs)
    source_counts: dict[str, int] = {}
    for r in all_results:
        for s in r["sources"]:
            source_counts[s] = source_counts.get(s, 0) + 1

    source_tabs = [
        {"key": k, "label": SOURCE_LABELS[k], "count": source_counts.get(k, 0)}
        for k in ("search_console", "paa", "related", "competitor", "internal", "dead_url")
        if source_counts.get(k, 0) > 0
    ]

    # ── All unique actions for action filter dropdown ──────────────────────
    all_actions = sorted(
        {r["recommended_action"] for r in all_results},
        key=str.lower,
    )

    # ── HTMX partial ──────────────────────────────────────────────────────
    is_htmx  = request.headers.get("HX-Request") == "true"
    template = (
        "seo_intel/partials/keyword_discovery_panel.html"
        if is_htmx
        else "seo_intel/keyword_discovery.html"
    )

    ctx = {
        "seo_title":     "Keyword Discovery",
        "active_page":   "keyword_discovery",
        "results":       results,
        "total":         total,
        "rising":        rising,
        "competitor_gap": competitor_gap,
        "high_priority": high_priority,
        "source_filter":       source_filter,
        "source_filter_label": SOURCE_LABELS.get(source_filter, source_filter),
        "action_filter": action_filter,
        "sort_by":       sort_by,
        "source_tabs":   source_tabs,
        "all_actions":   all_actions,
        "source_labels": SOURCE_LABELS,
        "displayed":     len(results),
    }
    return render(request, template, ctx)
