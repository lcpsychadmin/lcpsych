from __future__ import annotations

import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse


def _url(name: str, **kwargs) -> str:
    try:
        return reverse(name, kwargs=kwargs if kwargs else None)
    except NoReverseMatch:
        return '#'


# ---------------------------------------------------------------------------
# Main review table
# ---------------------------------------------------------------------------

def render_gap_review(request, admin_site):
    from seo_intel.models import ContentGapRecord
    from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

    # ── Bulk POST actions ────────────────────────────────────────────────
    if request.method == 'POST':
        bulk_action = request.POST.get('bulk_action', '')
        raw_pks = request.POST.getlist('selected_ids')
        pks = [int(pk) for pk in raw_pks if pk.isdigit()]
        if pks:
            qs_bulk = ContentGapRecord.objects.filter(pk__in=pks)
            if bulk_action == 'approve':
                count = qs_bulk.update(resolved=True, ignored=False)
                messages.success(request, f'Approved {count} gap record(s).')
            elif bulk_action == 'dismiss':
                count = qs_bulk.update(resolved=False, ignored=True)
                messages.success(request, f'Dismissed {count} gap record(s).')
        preserve = {
            k: v for k, v in request.POST.items()
            if k in ('status', 'category', 'competitor_presence', 'recommended_action')
        }
        redirect_url = _url('admin:seo_settings_contentgapanalytics_review')
        if preserve:
            redirect_url += '?' + urlencode(preserve)
        return redirect(redirect_url)

    # ── Filters ──────────────────────────────────────────────────────────
    f_status = request.GET.get('status', 'open')
    f_category = request.GET.get('category', '')
    f_competitor = request.GET.get('competitor_presence', '')
    f_action = request.GET.get('recommended_action', '').strip()

    qs = ContentGapRecord.objects.all()

    if f_status == 'open':
        qs = qs.filter(resolved=False, ignored=False)
    elif f_status == 'resolved':
        qs = qs.filter(resolved=True)
    elif f_status == 'dismissed':
        qs = qs.filter(ignored=True)
    # 'all' → no status filter

    if f_category:
        cat_keywords = KeywordSeed.objects.filter(
            category=f_category, active=True
        ).values_list('keyword', flat=True)
        qs = qs.filter(keyword__in=cat_keywords)

    if f_competitor == '1':
        qs = qs.filter(competitor_presence=True)
    elif f_competitor == '0':
        qs = qs.filter(competitor_presence=False)

    if f_action:
        qs = qs.filter(recommended_action__icontains=f_action)

    qs = qs.order_by('-search_volume', '-timestamp')

    # ── Tab badge counts (unfiltered) ─────────────────────────────────
    open_count = ContentGapRecord.objects.filter(resolved=False, ignored=False).count()
    resolved_count = ContentGapRecord.objects.filter(resolved=True).count()
    dismissed_count = ContentGapRecord.objects.filter(ignored=True).count()

    # ── Pagination ───────────────────────────────────────────────────────
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ── Export URL with current filters ──────────────────────────────────
    export_params = {
        k: v for k, v in request.GET.items()
        if k in ('status', 'category', 'competitor_presence', 'recommended_action')
    }
    export_url = _url('admin:seo_settings_contentgapanalytics_review_export')
    if export_params:
        export_url += '?' + urlencode(export_params)

    context = {
        **admin_site.each_context(request),
        'title': 'Content Gap Review',
        'page_obj': page_obj,
        'paginator': paginator,
        'filtered_count': qs.count(),
        'open_count': open_count,
        'resolved_count': resolved_count,
        'dismissed_count': dismissed_count,
        'tab_items': [
            ('open',      'Open',      open_count),
            ('resolved',  'Approved',  resolved_count),
            ('dismissed', 'Dismissed', dismissed_count),
            ('all',       'All',       open_count + resolved_count + dismissed_count),
        ],
        'f_status': f_status,
        'f_category': f_category,
        'f_competitor': f_competitor,
        'f_action': f_action,
        'category_choices': KEYWORD_CATEGORY_CHOICES,
        'export_url': export_url,
        'review_url': _url('admin:seo_settings_contentgapanalytics_review'),
        'approve_base_url': _url('admin:seo_settings_contentgapanalytics_review_approve', pk=0).rstrip('0'),
        'dismiss_base_url': _url('admin:seo_settings_contentgapanalytics_review_dismiss', pk=0).rstrip('0'),
        'detail_base_url': _url('admin:seo_settings_contentgapanalytics_review_detail', pk=0).rstrip('0'),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/gap_review.html', context
    )


# ---------------------------------------------------------------------------
# Per-record AJAX actions
# ---------------------------------------------------------------------------

def gap_approve_view(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    from seo_intel.models import ContentGapRecord
    record = get_object_or_404(ContentGapRecord, pk=pk)
    record.resolved = True
    record.ignored = False
    record.save(update_fields=['resolved', 'ignored'])
    return JsonResponse({'status': 'ok'})


def gap_dismiss_view(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    from seo_intel.models import ContentGapRecord
    record = get_object_or_404(ContentGapRecord, pk=pk)
    record.resolved = False
    record.ignored = True
    record.save(update_fields=['resolved', 'ignored'])
    return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def render_gap_detail(request, pk, admin_site):
    from django.db.models import Avg, Sum

    from seo_intel.models import (
        CompetitorSERPResult,
        ContentGapRecord,
        SearchConsoleQuery,
    )

    record = get_object_or_404(ContentGapRecord, pk=pk)

    competitor_results = list(
        CompetitorSERPResult.objects
        .filter(keyword__iexact=record.keyword)
        .order_by('rank')[:20]
    )

    lcpsych_pages = list(
        SearchConsoleQuery.objects
        .filter(query__iexact=record.keyword)
        .values('page')
        .annotate(
            total_clicks=Sum('clicks'),
            avg_position=Avg('position'),
        )
        .order_by('-total_clicks')[:20]
    )

    context = {
        **admin_site.each_context(request),
        'title': f'Gap Detail: {record.keyword}',
        'record': record,
        'competitor_results': competitor_results,
        'lcpsych_pages': lcpsych_pages,
        'back_url': _url('admin:seo_settings_contentgapanalytics_review'),
        'approve_url': _url('admin:seo_settings_contentgapanalytics_review_approve', pk=pk),
        'dismiss_url': _url('admin:seo_settings_contentgapanalytics_review_dismiss', pk=pk),
    }
    return TemplateResponse(
        request, 'admin/seo_settings/gap_review_detail.html', context
    )


# ---------------------------------------------------------------------------
# Export filtered results to CSV
# ---------------------------------------------------------------------------

def export_gap_review_csv(request, admin_site):  # noqa: ARG001 (admin_site unused but kept for consistency)
    from seo_intel.models import ContentGapRecord
    from seo_settings.models import KeywordSeed

    f_status = request.GET.get('status', 'open')
    f_category = request.GET.get('category', '')
    f_competitor = request.GET.get('competitor_presence', '')
    f_action = request.GET.get('recommended_action', '').strip()

    qs = ContentGapRecord.objects.all()

    if f_status == 'open':
        qs = qs.filter(resolved=False, ignored=False)
    elif f_status == 'resolved':
        qs = qs.filter(resolved=True)
    elif f_status == 'dismissed':
        qs = qs.filter(ignored=True)

    if f_category:
        cat_keywords = KeywordSeed.objects.filter(
            category=f_category, active=True
        ).values_list('keyword', flat=True)
        qs = qs.filter(keyword__in=cat_keywords)

    if f_competitor == '1':
        qs = qs.filter(competitor_presence=True)
    elif f_competitor == '0':
        qs = qs.filter(competitor_presence=False)

    if f_action:
        qs = qs.filter(recommended_action__icontains=f_action)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="content_gap_review.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Keyword', 'Search Volume', 'Competitor Presence', 'LC Psych Presence',
        'Recommended Action', 'Status', 'Date',
    ])
    for rec in qs.order_by('-search_volume'):
        if rec.resolved:
            status = 'Approved'
        elif rec.ignored:
            status = 'Dismissed'
        else:
            status = 'Open'
        writer.writerow([
            rec.keyword,
            rec.search_volume,
            'Yes' if rec.competitor_presence else 'No',
            'Yes' if rec.lcpsych_presence else 'No',
            rec.recommended_action,
            status,
            rec.timestamp.date() if rec.timestamp else '',
        ])

    return response
