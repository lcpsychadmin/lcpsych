"""
seo_intel/views/serp_explorer.py
----------------------------------
SERP Explorer — inspect raw organic results, competitor hits, and LC Psych
hits for any tracked keyword, and trigger a fresh SERP fetch.
"""
from __future__ import annotations

import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as django_settings
            login_url = getattr(django_settings, 'LOGIN_URL', '/accounts/login/')
            return redirect(f'{login_url}?{REDIRECT_FIELD_NAME}={request.path}')
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@_staff_required
@ensure_csrf_cookie
def serp_explorer(request):
    from seo_intel.models import CompetitorHit, LCPsychHit, SerpRawResult
    from seo_settings.models import KeywordSeed

    # ── Build keyword list ─────────────────────────────────────────────────
    # Union of: active seeds + any keyword with SERP history
    seed_keywords = set(
        KeywordSeed.objects.filter(active=True).values_list('keyword', flat=True)
    )
    serp_keywords = set(
        SerpRawResult.objects.values_list('keyword', flat=True).distinct()
    )
    all_keywords = sorted(seed_keywords | serp_keywords, key=str.lower)

    # ── Selected keyword ───────────────────────────────────────────────────
    selected_kw = request.GET.get('kw', '').strip()
    if not selected_kw and all_keywords:
        # Default: first keyword that has SERP data, otherwise first seed
        keywords_with_data = sorted(serp_keywords, key=str.lower)
        selected_kw = keywords_with_data[0] if keywords_with_data else all_keywords[0]

    # ── Load SERP data for selected keyword ────────────────────────────────
    serp_raw = None
    organic_results: list[dict] = []
    paa: list[str] = []
    related_searches: list[str] = []

    if selected_kw:
        serp_raw = (
            SerpRawResult.objects
            .filter(keyword=selected_kw)
            .order_by('-timestamp')
            .first()
        )
        if serp_raw:
            parsed = serp_raw.payload.get('parsed', {})
            organic_results = parsed.get('organic', [])
            paa = parsed.get('people_also_ask', [])
            related_searches = parsed.get('related_searches', [])

    competitor_hits = []
    lc_hits = []

    if selected_kw:
        competitor_hits = list(
            CompetitorHit.objects
            .filter(keyword=selected_kw)
            .order_by('-timestamp', 'rank')
            .select_related()
        )
        lc_hits = list(
            LCPsychHit.objects
            .filter(keyword=selected_kw)
            .order_by('-timestamp', 'rank')
        )

    # ── History: last 5 SERP runs for this keyword ─────────────────────────
    serp_history = list(
        SerpRawResult.objects
        .filter(keyword=selected_kw)
        .order_by('-timestamp')[:5]
    ) if selected_kw else []

    context = {
        'seo_title': 'SEO Intelligence — SERP Explorer | L+C Psych',
        'robots': 'noindex, nofollow',
        'active_page': 'serp_explorer',
        'all_keywords': all_keywords,
        'selected_kw': selected_kw,
        'serp_raw': serp_raw,
        'organic_results': organic_results,
        'competitor_hits': competitor_hits,
        'lc_hits': lc_hits,
        'paa': paa,
        'related_searches': related_searches,
        'serp_history': serp_history,
        'organic_count': len(organic_results),
        'competitor_hit_count': len(competitor_hits),
        'lc_hit_count': len(lc_hits),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'seo_intel/partials/_serp_results.html', context)
    return render(request, 'seo_intel/serp_explorer.html', context)
