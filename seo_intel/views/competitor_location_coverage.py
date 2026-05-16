"""
seo_intel/views/competitor_location_coverage.py
-------------------------------------------------
Location Coverage Dashboard view.

Shows which geographic markets a competitor targets vs LC Psych,
with a full coverage comparison table.
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
def competitor_location_coverage(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.models import CompetitorCrawl
    from seo_intel.services.competitor_location_coverage import get_location_coverage

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

    status_filter = request.GET.get("status", "all")

    data = get_location_coverage(selected_domain) if selected_domain else {}
    location_rows = data.get("location_rows", [])

    if status_filter != "all":
        location_rows = [r for r in location_rows if r["status"] == status_filter]

    ctx = {
        "seo_title": "Location Coverage",
        "active_page": "competitor_location_coverage",
        "competitors": competitors,
        "selected": selected,
        "selected_domain": selected_domain,
        "last_crawled_at": crawl_map.get(selected_domain),
        "has_data": data.get("has_data", False),
        "location_rows": location_rows,
        "summary": data.get("summary", {}),
        "missing_from_lc": data.get("missing_from_lc", []),
        "lcpsych_exclusive": data.get("lcpsych_exclusive", []),
        "overlap": data.get("overlap", []),
        "status_filter": status_filter,
    }
    return render(request, "seo_intel/competitor_location_coverage.html", ctx)
