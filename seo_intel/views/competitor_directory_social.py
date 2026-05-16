"""
seo_intel/views/competitor_directory_social.py
-----------------------------------------------
Directory & Social Competitor Analysis dashboard.

Shows:
  • Directory comparison (GBP, Psychology Today, TherapyDen, ZocDoc, Alma)
  • Social comparison (Facebook, Instagram, TikTok, YouTube)
  • Review strength panel
  • Gap analysis & recommendations
  • Visibility score panel

Scan buttons trigger background jobs via action endpoints:
  POST seo/actions/run-directory-scan/  → job_id
  POST seo/actions/run-social-scan/     → job_id
"""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as s
            return redirect(f"{getattr(s, 'LOGIN_URL', '/accounts/login/')}?{REDIRECT_FIELD_NAME}={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


@_staff_required
def competitor_directory_social(request):
    from seo_settings.models import CompetitorDomain
    from seo_intel.models import DirectoryProfile, SocialProfile
    from seo_intel.services.directory_social_comparison import (
        get_directory_social_comparison,
        LC_PSYCH_DOMAIN,
    )
    from seo_intel.services.directory_scraper import PLATFORM_LABELS as DIR_LABELS
    from seo_intel.services.social_scraper import SOCIAL_PLATFORM_LABELS as SOC_LABELS

    # ── Competitor selection ──────────────────────────────────────────────
    competitors = list(CompetitorDomain.objects.filter(active=True).order_by("domain"))
    selected_domain = request.GET.get("competitor", "").strip()
    if not selected_domain and competitors:
        selected_domain = competitors[0].domain

    # Attach last-scan timestamps
    dir_scan_map = {
        r.competitor_domain: r.crawled_at
        for r in DirectoryProfile.objects.filter(
            competitor_domain__in=[c.domain for c in competitors]
        ).order_by("competitor_domain", "platform").distinct("competitor_domain")
    } if competitors else {}

    soc_scan_map = {
        r.competitor_domain: r.crawled_at
        for r in SocialProfile.objects.filter(
            competitor_domain__in=[c.domain for c in competitors]
        ).order_by("competitor_domain", "platform").distinct("competitor_domain")
    } if competitors else {}

    for comp in competitors:
        comp.last_dir_scan = dir_scan_map.get(comp.domain)
        comp.last_soc_scan = soc_scan_map.get(comp.domain)

    # LC Psych scan timestamps
    lc_last_dir = DirectoryProfile.objects.filter(
        competitor_domain=LC_PSYCH_DOMAIN
    ).order_by("-crawled_at").values_list("crawled_at", flat=True).first()
    lc_last_soc = SocialProfile.objects.filter(
        competitor_domain=LC_PSYCH_DOMAIN
    ).order_by("-crawled_at").values_list("crawled_at", flat=True).first()

    # ── Comparison data ───────────────────────────────────────────────────
    comparison: dict = {}
    if selected_domain:
        comparison = get_directory_social_comparison(selected_domain)

    context = {
        "seo_title": "Directory & Social Analysis",
        "active_page": "competitor_directory_social",
        "competitors": competitors,
        "selected_domain": selected_domain,
        "lc_domain": LC_PSYCH_DOMAIN,
        "lc_last_dir": lc_last_dir,
        "lc_last_soc": lc_last_soc,
        "dir_labels": DIR_LABELS,
        "soc_labels": SOC_LABELS,
        **comparison,
    }

    return render(request, "seo_intel/competitor_directory_social.html", context)
