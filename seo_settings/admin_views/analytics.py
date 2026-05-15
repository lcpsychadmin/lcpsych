from __future__ import annotations

import csv
import json

from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse
from django.utils import timezone


def _url(name: str) -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return '#'


def _cp_action_urls() -> dict:
    """Return the control-panel action URL dict for use in dashboard contexts."""
    return {
        'run_sc_pull': _url('admin:seo_settings_seocontrolpanel_run_sc_pull'),
        'run_scrape': _url('admin:seo_settings_seocontrolpanel_run_scrape'),
        'run_gap': _url('admin:seo_settings_seocontrolpanel_run_gap'),
        'clear_dead_urls': _url('admin:seo_settings_seocontrolpanel_clear_dead_urls'),
        'clear_internal_search': _url('admin:seo_settings_seocontrolpanel_clear_internal_search'),
        'clear_competitor_results': _url('admin:seo_settings_seocontrolpanel_clear_competitor_results'),
    }


# ---------------------------------------------------------------------------
# 1 · Search Console Dashboard
# ---------------------------------------------------------------------------

def render_search_console(request, admin_site):
    from datetime import timedelta

    from seo_intel.models import SearchConsoleQuery

    cutoff = timezone.now().date() - timedelta(days=90)

    daily = (
        SearchConsoleQuery.objects
        .filter(date__gte=cutoff)
        .values('date')
        .annotate(total_impressions=Sum('impressions'), total_clicks=Sum('clicks'))
        .order_by('date')
    )

    dates = [str(row['date']) for row in daily]
    impressions = [row['total_impressions'] for row in daily]
    clicks = [row['total_clicks'] for row in daily]

    top_queries = list(
        SearchConsoleQuery.objects
        .values('query')
        .annotate(
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions'),
            avg_position=Avg('position'),
        )
        .order_by('-total_clicks')[:25]
    )

    top_pages = list(
        SearchConsoleQuery.objects
        .values('page')
        .annotate(
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions'),
        )
        .order_by('-total_clicks')[:25]
    )

    context = {
        **admin_site.each_context(request),
        'title': 'Search Console Analytics',
        'chart_data_json': json.dumps({
            'dates': dates,
            'impressions': impressions,
            'clicks': clicks,
        }),
        'top_queries': top_queries,
        'top_pages': top_pages,
        'total_records': SearchConsoleQuery.objects.count(),
        'action_urls': _cp_action_urls(),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/analytics_search_console.html', context
    )


# ---------------------------------------------------------------------------
# 2 · Internal Search Dashboard
# ---------------------------------------------------------------------------

def render_internal_search(request, admin_site):
    from seo_intel.models import InternalSearchQuery

    top_terms = list(
        InternalSearchQuery.objects
        .values('term')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    recent = list(InternalSearchQuery.objects.order_by('-timestamp')[:50])

    # Terms seen only once — proxy for searches that may have found nothing
    rare_terms = list(
        InternalSearchQuery.objects
        .values('term')
        .annotate(count=Count('id'))
        .filter(count=1)
        .order_by('term')[:50]
    )

    context = {
        **admin_site.each_context(request),
        'title': 'Internal Search Analytics',
        'chart_data_json': json.dumps({
            'labels': [row['term'] for row in top_terms],
            'values': [row['count'] for row in top_terms],
        }),
        'top_terms': top_terms,
        'recent_searches': recent,
        'rare_terms': rare_terms,
        'total_searches': InternalSearchQuery.objects.count(),
        'action_urls': _cp_action_urls(),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/analytics_internal_search.html', context
    )


# ---------------------------------------------------------------------------
# 3 · Dead URL Dashboard
# ---------------------------------------------------------------------------

def render_dead_urls(request, admin_site):
    from django.db.models import Q

    from seo_intel.models import DeadURLHit
    from seo_settings.models import CompetitorDomain

    top_urls = list(
        DeadURLHit.objects
        .values('url')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    chart_labels = [
        (row['url'][:55] + '…') if len(row['url']) > 55 else row['url']
        for row in top_urls
    ]

    # Hits whose referrer contains an active competitor domain
    competitor_domains = list(
        CompetitorDomain.objects.filter(active=True).values_list('domain', flat=True)
    )
    competitor_hits = []
    if competitor_domains:
        q = Q()
        for domain in competitor_domains:
            q |= Q(referrer__icontains=domain)
        competitor_hits = list(DeadURLHit.objects.filter(q).order_by('-timestamp')[:50])

    top_referrers = list(
        DeadURLHit.objects
        .exclude(referrer__isnull=True)
        .exclude(referrer='')
        .values('referrer')
        .annotate(count=Count('id'))
        .order_by('-count')[:25]
    )

    context = {
        **admin_site.each_context(request),
        'title': 'Dead URL Analytics',
        'chart_data_json': json.dumps({
            'labels': chart_labels,
            'values': [row['count'] for row in top_urls],
        }),
        'top_urls': top_urls,
        'competitor_hits': competitor_hits,
        'top_referrers': top_referrers,
        'total_hits': DeadURLHit.objects.count(),
        'action_urls': _cp_action_urls(),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/analytics_dead_urls.html', context
    )


# ---------------------------------------------------------------------------
# 4 · Competitor SERP Dashboard
# ---------------------------------------------------------------------------

def render_competitor_serp(request, admin_site):
    from seo_intel.models import CompetitorSERPResult

    results = list(CompetitorSERPResult.objects.order_by('keyword', 'rank')[:100])

    # Ranking distribution buckets
    buckets = {'1–3': 0, '4–10': 0, '11–20': 0, '21+': 0}
    for rank in CompetitorSERPResult.objects.values_list('rank', flat=True):
        if rank <= 3:
            buckets['1–3'] += 1
        elif rank <= 10:
            buckets['4–10'] += 1
        elif rank <= 20:
            buckets['11–20'] += 1
        else:
            buckets['21+'] += 1

    top_keywords = list(
        CompetitorSERPResult.objects
        .values('keyword')
        .annotate(result_count=Count('id'), avg_rank=Avg('rank'))
        .order_by('avg_rank')[:30]
    )

    context = {
        **admin_site.each_context(request),
        'title': 'Competitor SERP Analytics',
        'chart_data_json': json.dumps({
            'labels': list(buckets.keys()),
            'values': list(buckets.values()),
        }),
        'results': results,
        'top_keywords': top_keywords,
        'total_results': CompetitorSERPResult.objects.count(),
        'action_urls': _cp_action_urls(),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/analytics_competitor_serp.html', context
    )


# ---------------------------------------------------------------------------
# 5 · Content Gap Dashboard
# ---------------------------------------------------------------------------

def _build_content_gap_qs(request):
    from seo_intel.models import ContentGapRecord

    qs = ContentGapRecord.objects.all()

    resolved = request.GET.get('resolved', '0')
    if resolved == '1':
        qs = qs.filter(resolved=True)
    elif resolved == '0':
        qs = qs.filter(resolved=False)

    cp = request.GET.get('competitor_presence', '')
    if cp == '1':
        qs = qs.filter(competitor_presence=True)
    elif cp == '0':
        qs = qs.filter(competitor_presence=False)

    lp = request.GET.get('lcpsych_presence', '')
    if lp == '1':
        qs = qs.filter(lcpsych_presence=True)
    elif lp == '0':
        qs = qs.filter(lcpsych_presence=False)

    return qs


def render_content_gaps(request, admin_site):
    from django.urls import reverse

    qs = _build_content_gap_qs(request)

    # Build export URL preserving current filters
    from urllib.parse import urlencode
    export_params = {
        k: v for k, v in request.GET.items()
        if k in ('resolved', 'competitor_presence', 'lcpsych_presence')
    }
    export_url = reverse('admin:seo_settings_contentgapanalytics_export_csv')
    if export_params:
        export_url += '?' + urlencode(export_params)

    context = {
        **admin_site.each_context(request),
        'title': 'Content Gap Analytics',
        'records': qs.order_by('-search_volume')[:200],
        'total': qs.count(),
        'export_url': export_url,
        'filter_resolved': request.GET.get('resolved', '0'),
        'filter_competitor_presence': request.GET.get('competitor_presence', ''),
        'filter_lcpsych_presence': request.GET.get('lcpsych_presence', ''),
        'action_urls': _cp_action_urls(),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/analytics_content_gaps.html', context
    )


def export_content_gaps_csv(request, admin_site):
    qs = _build_content_gap_qs(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="content_gaps.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Keyword', 'Search Volume', 'Competitor Presence',
        'LC Psych Presence', 'Recommended Action', 'Resolved', 'Date',
    ])
    for record in qs.order_by('-search_volume'):
        writer.writerow([
            record.keyword,
            record.search_volume,
            'Yes' if record.competitor_presence else 'No',
            'Yes' if record.lcpsych_presence else 'No',
            record.recommended_action,
            'Yes' if record.resolved else 'No',
            record.timestamp.date() if record.timestamp else '',
        ])

    return response
