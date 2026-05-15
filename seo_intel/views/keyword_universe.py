"""
seo_intel/views/keyword_universe.py
-------------------------------------
Unified Keyword Universe view.

Joins KeywordSeed × KeywordScore × LCPsychHit × CompetitorHit into a single
ranked table.  Supports URL-based filtering and CSV export.
"""
from __future__ import annotations

import csv
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.db.models import Min
from django.http import HttpResponse
from django.shortcuts import redirect, render


# ---------------------------------------------------------------------------
# Auth decorator (mirrors other seo_intel views)
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
# Constants
# ---------------------------------------------------------------------------

CATEGORY_CHOICES = [
    ('service', 'Service'),
    ('testing', 'Testing'),
    ('modality', 'Modality'),
    ('location', 'Location'),
]
VALID_CATEGORIES = {v for v, _ in CATEGORY_CHOICES}
CATEGORY_LABELS = dict(CATEGORY_CHOICES)


def _suggested_action(lc_rank, comp_rank, priority_score):
    """Derive a suggested action label and CSS colour key from SERP data."""
    if priority_score == 0 and lc_rank is None:
        return 'Research', 'gray'
    if lc_rank is None:
        if comp_rank is not None and comp_rank <= 5:
            return 'Create Page — High Priority', 'red'
        return 'Create Page', 'orange'
    if lc_rank <= 3:
        return 'Maintain', 'green'
    if lc_rank <= 10:
        return 'Optimize', 'yellow'
    return 'Improve Ranking', 'amber'


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@_staff_required
def keyword_universe(request):
    from seo_intel.models import CompetitorHit, KeywordScore, KeywordSuggestion, LCPsychHit
    from seo_settings.models import KeywordSeed

    # ── Bulk data loads ────────────────────────────────────────────────────
    scores = {s.keyword: s for s in KeywordScore.objects.all()}

    lc_ranks: dict[str, int] = dict(
        LCPsychHit.objects
        .values('keyword')
        .annotate(best=Min('rank'))
        .values_list('keyword', 'best')
    )

    comp_ranks: dict[str, int] = dict(
        CompetitorHit.objects
        .values('keyword')
        .annotate(best=Min('rank'))
        .values_list('keyword', 'best')
    )

    seeds = KeywordSeed.objects.order_by('category', 'keyword')

    # ── Build row list ─────────────────────────────────────────────────────
    rows = []
    for seed in seeds:
        kw = seed.keyword
        score_obj = scores.get(kw)
        lc_rank = lc_ranks.get(kw)
        comp_rank = comp_ranks.get(kw)
        priority = score_obj.priority_score if score_obj else 0
        action_label, action_color = _suggested_action(lc_rank, comp_rank, priority)

        rows.append({
            'seed_id': seed.pk,
            'keyword': kw,
            'category': seed.category,
            'category_display': CATEGORY_LABELS.get(seed.category, seed.category),
            'active': seed.active,
            'priority_score': priority,
            'lc_rank': lc_rank,
            'comp_rank': comp_rank,
            'action_label': action_label,
            'action_color': action_color,
            'has_score': score_obj is not None,
            # Sub-scores for tooltip / detail
            'search_demand': score_obj.search_demand_score if score_obj else None,
            'competitor_pressure': score_obj.competitor_pressure_score if score_obj else None,
            'lc_presence': score_obj.lcpsych_presence_score if score_obj else None,
            'local_intent': score_obj.local_intent_score if score_obj else None,
            'commercial_intent': score_obj.commercial_intent_score if score_obj else None,
        })

    # ── Apply filters ──────────────────────────────────────────────────────
    get = request.GET
    active_cat = get.get('cat', '')
    min_score_raw = get.get('min_score', '')
    has_lcpsych = get.get('has_lcpsych', '')
    has_competitor = get.get('has_competitor', '')
    only_unscored = get.get('unscored', '')

    if active_cat and active_cat in VALID_CATEGORIES:
        rows = [r for r in rows if r['category'] == active_cat]

    if min_score_raw:
        try:
            min_s = int(min_score_raw)
            rows = [r for r in rows if r['priority_score'] >= min_s]
        except ValueError:
            min_score_raw = ''

    if has_lcpsych == '1':
        rows = [r for r in rows if r['lc_rank'] is not None]

    if has_competitor == '1':
        rows = [r for r in rows if r['comp_rank'] is not None]

    if only_unscored == '1':
        rows = [r for r in rows if not r['has_score']]

    # ── Sort ───────────────────────────────────────────────────────────────
    rows.sort(key=lambda r: (-r['priority_score'], r['keyword']))

    # ── CSV export ─────────────────────────────────────────────────────────
    if get.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="keyword_universe.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Keyword', 'Category', 'Active', 'Priority Score',
            'Search Demand', 'Competitor Pressure', 'LC Presence',
            'Local Intent', 'Commercial Intent',
            'LC Psych Best Rank', 'Competitor Best Rank', 'Suggested Action',
        ])
        for r in rows:
            writer.writerow([
                r['keyword'],
                r['category_display'],
                'Yes' if r['active'] else 'No',
                r['priority_score'],
                r['search_demand'] if r['search_demand'] is not None else '',
                r['competitor_pressure'] if r['competitor_pressure'] is not None else '',
                r['lc_presence'] if r['lc_presence'] is not None else '',
                r['local_intent'] if r['local_intent'] is not None else '',
                r['commercial_intent'] if r['commercial_intent'] is not None else '',
                r['lc_rank'] if r['lc_rank'] is not None else '',
                r['comp_rank'] if r['comp_rank'] is not None else '',
                r['action_label'],
            ])
        return response

    # ── Summary stats ──────────────────────────────────────────────────────
    all_seeds = KeywordSeed.objects.all()
    total_seeds = all_seeds.count()
    active_seeds = all_seeds.filter(active=True).count()
    scored_count = KeywordScore.objects.count()
    suggestions_pending = KeywordSuggestion.objects.filter(used_as_seed=False).count()

    category_counts = {}
    category_choices_with_counts = []
    for v, label in CATEGORY_CHOICES:
        count = all_seeds.filter(category=v).count()
        category_counts[v] = {'label': label, 'count': count}
        category_choices_with_counts.append((v, label, count))

    # Recent unused suggestions (sidebar / secondary panel)
    suggestions = (
        KeywordSuggestion.objects
        .filter(used_as_seed=False)
        .order_by('-timestamp')[:30]
    )

    # Build export URL (preserve all current filters)
    export_params = get.copy()
    export_params['export'] = 'csv'

    context = {
        'seo_title': 'SEO Intelligence — Keyword Universe | L+C Psych',
        'robots': 'noindex, nofollow',
        'active_page': 'keyword_universe',
        'rows': rows,
        'row_count': len(rows),
        'total_seeds': total_seeds,
        'active_seeds': active_seeds,
        'scored_count': scored_count,
        'suggestions_pending': suggestions_pending,
        'suggestions': suggestions,
        'category_choices': CATEGORY_CHOICES,
        'category_choices_with_counts': category_choices_with_counts,
        'category_counts': category_counts,
        # Active filter values (to re-populate form)
        'active_cat': active_cat,
        'min_score_raw': min_score_raw,
        'has_lcpsych': has_lcpsych,
        'has_competitor': has_competitor,
        'only_unscored': only_unscored,
        'export_url': '?' + export_params.urlencode(),
    }
    return render(request, 'seo_intel/keyword_universe.html', context)
