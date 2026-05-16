"""
seo_intel/views/keyword_seeds_intel.py
----------------------------------------
Keyword Seeds Intelligence view.

Aggregates per-seed SEO intelligence (trend, competitors, LC Psych presence,
keyword expansion, priority scores) and renders the full intelligence panel.

Supports HTMX partial refresh:
    hx-get="<url>"
    hx-target="#keyword-seeds-intel-panel"
"""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@_staff_required
def keyword_seeds_intel(request):
    from seo_settings.models import KeywordSeed
    from seo_intel.services.keyword_trends_analyzer import analyze_seeds

    # ── Filters ───────────────────────────────────────────────────────────
    category_filter = request.GET.get("category", "")
    action_filter   = request.GET.get("action", "")
    sort_by         = request.GET.get("sort", "priority")   # priority | trend | keyword

    VALID_CATEGORIES = {"service", "testing", "modality", "location"}
    VALID_SORTS      = {"priority", "trend", "keyword"}

    if category_filter not in VALID_CATEGORIES:
        category_filter = ""
    if sort_by not in VALID_SORTS:
        sort_by = "priority"

    # ── Load seeds ────────────────────────────────────────────────────────
    seeds_qs = KeywordSeed.objects.filter(active=True)
    if category_filter:
        seeds_qs = seeds_qs.filter(category=category_filter)

    seeds = list(seeds_qs)

    # ── Analyze ───────────────────────────────────────────────────────────
    intel = analyze_seeds(seeds)

    # ── Action filter (post-analysis) ─────────────────────────────────────
    if action_filter:
        intel = [r for r in intel if action_filter.lower() in r["recommended_action"].lower()]

    # ── Sort ──────────────────────────────────────────────────────────────
    if sort_by == "trend":
        intel.sort(key=lambda r: -r["trend_score"])
    elif sort_by == "keyword":
        intel.sort(key=lambda r: r["keyword"].lower())
    # default (priority) already sorted by analyzer

    # ── Summary stats ─────────────────────────────────────────────────────
    total = len(intel)
    trending_up   = sum(1 for r in intel if r["delta_direction"] == "up")
    trending_down = sum(1 for r in intel if r["delta_direction"] == "down")
    needs_page    = sum(1 for r in intel if "create" in r["recommended_action"].lower())
    high_priority = sum(1 for r in intel if r["priority_score"] >= 70)

    # ── Collect all unique actions for filter dropdown ─────────────────────
    all_actions = sorted(
        {r["recommended_action"] for r in intel},
        key=lambda a: a.lower(),
    )

    # ── HTMX partial ──────────────────────────────────────────────────────
    is_htmx = request.headers.get("HX-Request") == "true"
    template = (
        "seo_intel/partials/keyword_seeds_intel_panel.html"
        if is_htmx
        else "seo_intel/keyword_seeds_intel.html"
    )

    ctx = {
        "seo_title": "Keyword Seeds Intelligence",
        "active_page": "keyword_seeds_intel",
        "intel": intel,
        "total": total,
        "trending_up": trending_up,
        "trending_down": trending_down,
        "needs_page": needs_page,
        "high_priority": high_priority,
        "category_filter": category_filter,
        "action_filter": action_filter,
        "sort_by": sort_by,
        "all_actions": all_actions,
        "category_choices": [
            ("", "All Categories"),
            ("service", "Service"),
            ("testing", "Testing"),
            ("modality", "Modality"),
            ("location", "Location"),
        ],
    }
    return render(request, template, ctx)
