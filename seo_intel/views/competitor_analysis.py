"""
seo_intel/views/competitor_analysis.py
----------------------------------------
Competitor Analysis Dashboard view.

Shows gap analysis between LC Psych and a selected competitor domain,
using pre-crawled data from the cache (populated via the crawl_competitor
management command or the "Run Crawl" action endpoint).

Supports HTMX partial swap for seamless competitor switching.
"""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


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
def competitor_analysis(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.services.competitor_analyzer import analyze_competitor

    # ── Competitor selection ──────────────────────────────────────────────
    competitors = list(CompetitorDomain.objects.filter(active=True).order_by("domain"))
    selected_domain = request.GET.get("competitor", "").strip()

    if not selected_domain and competitors:
        selected_domain = competitors[0].domain

    selected = next((c for c in competitors if c.domain == selected_domain), None)

    # ── Analysis ──────────────────────────────────────────────────────────
    analysis: dict = {}
    if selected_domain:
        analysis = analyze_competitor(selected_domain)

    # ── HTMX partial ──────────────────────────────────────────────────────
    is_htmx = request.headers.get("HX-Request") == "true"
    template = (
        "seo_intel/partials/competitor_analysis_panel.html"
        if is_htmx
        else "seo_intel/competitor_analysis.html"
    )

    # Build per-category comparison rows for the side-by-side table
    lc_cov = analysis.get("lc_coverage", {})
    comp_cov = analysis.get("comp_coverage", {})
    gaps = analysis.get("gaps", {})
    gap_scores = analysis.get("gap_scores", {})

    category_rows = []
    labels = {
        "services": "Services",
        "modalities": "Modalities",
        "testing": "Testing",
        "conditions": "Conditions",
        "locations": "Locations",
    }
    score_map = {
        "services": gap_scores.get("content_gap_score", 0),
        "modalities": gap_scores.get("modality_gap_score", 0),
        "testing": gap_scores.get("testing_gap_score", 0),
        "conditions": 0,  # no dedicated score; derive below
        "locations": gap_scores.get("location_gap_score", 0),
    }
    # Inline conditions gap score
    lc_cond = set(lc_cov.get("conditions", []))
    comp_cond = set(comp_cov.get("conditions", []))
    if comp_cond:
        score_map["conditions"] = round(
            100 * len(comp_cond - lc_cond) / len(comp_cond)
        )

    for cat, label in labels.items():
        lc_list = lc_cov.get(cat, [])
        comp_list = comp_cov.get(cat, [])
        gap_list = gaps.get(cat, [])
        score = score_map.get(cat, 0)
        if score == 0:
            score_css = "score-high"
        elif score <= 30:
            score_css = "score-mid"
        else:
            score_css = "score-low"
        category_rows.append({
            "category": cat,
            "label": label,
            "lc_count": len(lc_list),
            "comp_count": len(comp_list),
            "gap_count": len(gap_list),
            "gap_keywords": gap_list[:10],
            "score": score,
            "score_css": score_css,
        })

    ctx = {
        "seo_title": "Competitor Analysis",
        "active_page": "competitor_analysis",
        "competitors": competitors,
        "selected": selected,
        "selected_domain": selected_domain,
        "analysis": analysis,
        "crawled": analysis.get("crawled", False),
        "overview": analysis.get("overview", {}),
        "gap_scores": gap_scores,
        "top_pages": analysis.get("top_pages", {}),
        "recommendations": analysis.get("recommendations", []),
        "category_rows": category_rows,
    }
    return render(request, template, ctx)
