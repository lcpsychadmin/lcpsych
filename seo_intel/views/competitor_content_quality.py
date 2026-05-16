"""
seo_intel/views/competitor_content_quality.py
----------------------------------------------
Content Quality Dashboard view.

Shows per-page quality scores for a crawled competitor, highlights
strong pages (threats) and weak pages (opportunities).
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
def competitor_content_quality(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.models import CompetitorCrawl
    from seo_intel.services.competitor_content_quality import get_content_quality

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

    # Quality tier filter
    quality_filter = request.GET.get("quality", "all")

    data = get_content_quality(selected_domain) if selected_domain else {}
    pages = data.get("pages", [])

    if quality_filter == "strong":
        pages = [p for p in pages if p["quality_score"] >= 70]
    elif quality_filter == "weak":
        pages = [p for p in pages if p["quality_score"] < 45]

    ctx = {
        "seo_title": "Content Quality",
        "active_page": "competitor_content_quality",
        "competitors": competitors,
        "selected": selected,
        "selected_domain": selected_domain,
        "last_crawled_at": crawl_map.get(selected_domain),
        "has_data": data.get("has_data", False),
        "pages": pages,
        "summary": data.get("summary", {}),
        "strong_pages": data.get("strong_pages", []),
        "weak_pages": data.get("weak_pages", []),
        "quality_filter": quality_filter,
    }
    return render(request, "seo_intel/competitor_content_quality.html", ctx)
