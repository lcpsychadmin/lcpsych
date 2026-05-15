"""
seo_intel/views/content_gaps.py
---------------------------------
Enhanced Content Gaps view.

Enriches ContentGapRecord rows with:
  • keyword_type  — from KeywordSeed.category (if the keyword is a seed)
  • priority_score — from KeywordScore (if scored)

Supports GET filters:
  • keyword_type       — 'service' | 'testing' | 'modality' | 'location' | 'unseed'
  • recommended_action — exact match against ContentGapRecord.recommended_action
  • priority_score     — minimum priority_score (int 0–100)
  • has_lc             — '1' = only gaps where lcpsych_presence=True, '0' = only False
  • has_competitor     — '1' = only gaps where competitor_presence=True
  • resolved           — '1' = show resolved only; default shows unresolved

CSV export: append ?export=csv to any filtered URL.
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

# Fixed recommended_action values produced by content_gap_engine.py
RECOMMENDED_ACTIONS = [
    'Optimize existing page',
    'Create new location page',
    'Add modality page',
    'Add testing page',
    'Create new service page',
]

CATEGORY_CHOICES = [
    ('service', 'Service'),
    ('testing', 'Testing'),
    ('modality', 'Modality'),
    ('location', 'Location'),
]
CATEGORY_LABELS = dict(CATEGORY_CHOICES)


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
def content_gaps(request):
    from seo_intel.models import ContentGapRecord, KeywordScore
    from seo_settings.models import KeywordSeed

    # ── Filter params ──────────────────────────────────────────────────────
    get = request.GET
    kw_type = get.get('keyword_type', '')
    action_filter = get.get('recommended_action', '')
    min_score_raw = get.get('priority_score', '')
    has_lc = get.get('has_lc', '')
    has_competitor = get.get('has_competitor', '')
    show_resolved = get.get('resolved', '0')

    # ── Base DB-level queryset ─────────────────────────────────────────────
    if show_resolved == '1':
        qs = ContentGapRecord.objects.filter(resolved=True)
    else:
        qs = ContentGapRecord.objects.filter(resolved=False, ignored=False)

    if has_lc == '1':
        qs = qs.filter(lcpsych_presence=True)
    elif has_lc == '0':
        qs = qs.filter(lcpsych_presence=False)

    if has_competitor == '1':
        qs = qs.filter(competitor_presence=True)
    elif has_competitor == '0':
        qs = qs.filter(competitor_presence=False)

    if action_filter and action_filter in RECOMMENDED_ACTIONS:
        qs = qs.filter(recommended_action=action_filter)

    # ── Enrichment lookups ─────────────────────────────────────────────────
    seed_categories: dict[str, str] = dict(
        KeywordSeed.objects.values_list('keyword', 'category')
    )
    scores: dict[str, int] = dict(
        KeywordScore.objects.values_list('keyword', 'priority_score')
    )

    # ── Build enriched rows (Python-level keyword_type + score filters) ───
    records = list(qs.order_by('-search_volume', 'keyword')[:1000])

    # Validate min_score
    min_score: int | None = None
    if min_score_raw:
        try:
            min_score = int(min_score_raw)
        except ValueError:
            min_score_raw = ''

    rows = []
    for rec in records:
        kw = rec.keyword
        cat = seed_categories.get(kw, '')
        score = scores.get(kw, 0)

        # Keyword type filter
        if kw_type:
            if kw_type == 'unseed' and cat:
                continue
            elif kw_type != 'unseed' and cat != kw_type:
                continue

        # Priority score filter
        if min_score is not None and score < min_score:
            continue

        rows.append({
            'id': rec.pk,
            'keyword': kw,
            'keyword_type': cat,
            'keyword_type_display': CATEGORY_LABELS.get(cat, '—') if cat else '—',
            'priority_score': score,
            'has_score': kw in scores,
            'lc_presence': rec.lcpsych_presence,
            'competitor_presence': rec.competitor_presence,
            'recommended_action': rec.recommended_action,
            'search_volume': rec.search_volume,
            'resolved': rec.resolved,
            'timestamp': rec.timestamp,
        })

    # Sort by priority_score desc, then search_volume desc
    rows.sort(key=lambda r: (-r['priority_score'], -r['search_volume']))

    # ── CSV export ─────────────────────────────────────────────────────────
    if get.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="content_gaps.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Keyword', 'Keyword Type', 'Priority Score', 'Search Volume',
            'LC Psych Presence', 'Competitor Presence', 'Recommended Action', 'Resolved',
        ])
        for r in rows:
            writer.writerow([
                r['keyword'],
                r['keyword_type_display'],
                r['priority_score'],
                r['search_volume'],
                'Yes' if r['lc_presence'] else 'No',
                'Yes' if r['competitor_presence'] else 'No',
                r['recommended_action'],
                'Yes' if r['resolved'] else 'No',
            ])
        return response

    # ── Summary stats ──────────────────────────────────────────────────────
    total_unresolved = ContentGapRecord.objects.filter(resolved=False, ignored=False).count()
    total_resolved = ContentGapRecord.objects.filter(resolved=True).count()

    # Build export URL preserving current filters
    export_params = get.copy()
    export_params['export'] = 'csv'

    context = {
        'seo_title': 'SEO Intelligence — Content Gaps | L+C Psych',
        'robots': 'noindex, nofollow',
        'active_page': 'content_gaps',
        'rows': rows,
        'row_count': len(rows),
        'total_unresolved': total_unresolved,
        'total_resolved': total_resolved,
        # Filter values
        'kw_type': kw_type,
        'action_filter': action_filter,
        'min_score_raw': min_score_raw,
        'has_lc': has_lc,
        'has_competitor': has_competitor,
        'show_resolved': show_resolved,
        # Filter options
        'category_choices': CATEGORY_CHOICES,
        'recommended_actions': RECOMMENDED_ACTIONS,
        'export_url': '?' + export_params.urlencode(),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'seo_intel/partials/_gaps_table.html', context)
    return render(request, 'seo_intel/content_gaps.html', context)
