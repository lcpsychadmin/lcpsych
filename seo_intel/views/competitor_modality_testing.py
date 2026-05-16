"""
seo_intel/views/competitor_modality_testing.py
------------------------------------------------
Modality & Testing Dashboard view.

Shows a matrix of therapy modalities and testing services comparing
competitor coverage vs LC Psych, with gap recommendations.
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
            from django.conf import settings as _s
            login_url = getattr(_s, "LOGIN_URL", "/accounts/login/")
            return redirect(f"{login_url}?{REDIRECT_FIELD_NAME}={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


@_staff_required
def competitor_modality_testing(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.models import CompetitorCrawl
    from seo_intel.services.competitor_modality_testing import get_modality_testing

    competitors = list(CompetitorDomain.objects.filter(active=True).order_by("domain"))
    selected_domain = request.GET.get("competitor", "").strip()
    if not selected_domain and competitors:
        selected_domain = competitors[0].domain

    selected = next((c for c in competitors if c.domain == selected_domain), None)

    crawl_map = {
        c.domain: c.crawled_at
        for c in CompetitorCrawl.objects.filter(
            domain__in=[c.domain for c in competitors]
        )
    }
    for comp in competitors:
        comp.last_crawled_at = crawl_map.get(comp.domain)

    data = get_modality_testing(selected_domain) if selected_domain else {}

    # Filter to gaps only if requested
    show_gaps_only = request.GET.get("gaps_only") == "1"
    modality_matrix = data.get("modality_matrix", [])
    testing_matrix = data.get("testing_matrix", [])
    if show_gaps_only:
        modality_matrix = [r for r in modality_matrix if r["status"] == "competitor-only"]
        testing_matrix = [r for r in testing_matrix if r["status"] == "competitor-only"]

    ctx = {
        "seo_title": "Modalities & Testing",
        "active_page": "competitor_modality_testing",
        "competitors": competitors,
        "selected": selected,
        "selected_domain": selected_domain,
        "last_crawled_at": crawl_map.get(selected_domain),
        "has_data": data.get("has_data", False),
        "modality_matrix": modality_matrix,
        "testing_matrix": testing_matrix,
        "modality_summary": data.get("modality_summary", {}),
        "testing_summary": data.get("testing_summary", {}),
        "recommendations": data.get("recommendations", []),
        "show_gaps_only": show_gaps_only,
    }
    return render(request, "seo_intel/competitor_modality_testing.html", ctx)
