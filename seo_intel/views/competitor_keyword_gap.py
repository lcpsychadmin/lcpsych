"""
seo_intel/views/competitor_keyword_gap.py
------------------------------------------
Keyword Gap Dashboard view.

Shows per-keyword SERP rank comparisons between LC Psych and a selected
competitor, with gap classification, priority scoring, and CSV export.
"""
from __future__ import annotations

import csv
import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
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
def competitor_keyword_gap(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.models import CompetitorCrawl
    from seo_intel.services.competitor_keyword_gap import get_keyword_gaps

    competitors = list(CompetitorDomain.objects.filter(active=True).order_by("domain"))
    selected_domain = request.GET.get("competitor", "").strip()
    if not selected_domain and competitors:
        selected_domain = competitors[0].domain

    selected = next((c for c in competitors if c.domain == selected_domain), None)

    # Attach last_crawled_at
    crawl_map = {
        c.domain: c.crawled_at
        for c in CompetitorCrawl.objects.filter(
            domain__in=[c.domain for c in competitors]
        )
    }
    for comp in competitors:
        comp.last_crawled_at = crawl_map.get(comp.domain)

    # Filter by gap type
    gap_filter = request.GET.get("gap_type", "all")

    data = get_keyword_gaps(selected_domain) if selected_domain else {}
    keyword_gaps = data.get("keyword_gaps", [])

    # CSV export
    if request.GET.get("export") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="keyword-gaps-{selected_domain}.csv"'
        )
        writer = csv.writer(resp)
        writer.writerow([
            "Keyword", "Gap Type", "Competitor Rank", "Competitor URL",
            "LC Psych Rank", "LC Psych URL", "Priority Score", "Recommended Action",
        ])
        for row in keyword_gaps:
            writer.writerow([
                row["keyword"],
                row["gap_type"],
                row["comp_rank"],
                row["comp_url"],
                row.get("lc_rank", ""),
                row.get("lc_url", ""),
                row["priority_score"],
                row["recommended_action"],
            ])
        return resp

    # Client-side gap filter
    if gap_filter != "all":
        keyword_gaps = [r for r in keyword_gaps if r["gap_type"] == gap_filter]

    ctx = {
        "seo_title": "Keyword Gaps",
        "active_page": "competitor_keyword_gap",
        "competitors": competitors,
        "selected": selected,
        "selected_domain": selected_domain,
        "last_crawled_at": crawl_map.get(selected_domain),
        "has_data": data.get("has_data", False),
        "keyword_gaps": keyword_gaps,
        "summary": data.get("summary", {}),
        "gap_filter": gap_filter,
    }
    return render(request, "seo_intel/competitor_keyword_gap.html", ctx)
