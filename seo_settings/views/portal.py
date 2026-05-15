"""
seo_settings/views/portal.py
-----------------------------
Custom front-end portal views for SEO Intelligence.
All views require authenticated staff or superuser access.
"""
from __future__ import annotations

import csv
import json
import os
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def _staff_required(view_func):
    """Decorator: requires authenticated staff or superuser. Redirects to login or raises 403."""
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
# Control Panel
# ---------------------------------------------------------------------------

@_staff_required
@ensure_csrf_cookie
def control_panel(request):
    from seo_intel.models import (
        CompetitorSERPResult,
        ContentGapRecord,
        DeadURLHit,
        InternalSearchQuery,
        SearchConsoleQuery,
    )
    from seo_settings.models import CompetitorDomain, KeywordSeed, SEOGlobalSettings

    gs = SEOGlobalSettings.get()

    stats = {
        'sc_queries': SearchConsoleQuery.objects.count(),
        'internal_searches': InternalSearchQuery.objects.count(),
        'dead_urls': DeadURLHit.objects.count(),
        'competitor_results': CompetitorSERPResult.objects.count(),
        'content_gaps_open': ContentGapRecord.objects.filter(resolved=False, ignored=False).count(),
        'competitor_domains': CompetitorDomain.objects.filter(active=True).count(),
        'keyword_seeds': KeywordSeed.objects.filter(active=True).count(),
    }

    modules = [
        {
            'name': 'Search Console',
            'enabled': gs.enable_search_console,
            'stat': stats['sc_queries'],
            'stat_label': 'queries on record',
        },
        {
            'name': 'Internal Search Tracking',
            'enabled': gs.enable_internal_search_tracking,
            'stat': stats['internal_searches'],
            'stat_label': 'searches logged',
        },
        {
            'name': 'Dead URL Logging',
            'enabled': gs.enable_dead_url_logging,
            'stat': stats['dead_urls'],
            'stat_label': '404 hits logged',
        },
        {
            'name': 'Competitor Scraping',
            'enabled': gs.enable_competitor_scraping,
            'stat': stats['competitor_results'],
            'stat_label': 'SERP results',
        },
        {
            'name': 'Gap Analysis',
            'enabled': gs.enable_gap_analysis,
            'stat': stats['content_gaps_open'],
            'stat_label': 'open gaps',
        },
    ]

    context = {
        'seo_title': 'SEO Intelligence — Control Panel | L+C Psych',
        'robots': 'noindex, nofollow',
        'global_settings': gs,
        'stats': stats,
        'modules': modules,
        'creds_configured': bool(
            os.environ.get('GSC_OAUTH_CLIENT_ID') and os.environ.get('GSC_OAUTH_REFRESH_TOKEN')
        ),
        'property_configured': bool(gs.search_console_property_url.strip()),
        'action_urls': {
            'run_sc': reverse('seo_intel:action_run_sc'),
            'run_scrape': reverse('seo_intel:action_run_scrape'),
            'run_gap': reverse('seo_intel:action_run_gap'),
            'clear_dead': reverse('seo_intel:action_clear_dead'),
            'clear_internal': reverse('seo_intel:action_clear_internal'),
            'clear_serps': reverse('seo_intel:action_clear_serps'),
        },
        'active_page': 'control_panel',
    }
    return render(request, 'seo_settings/portal/control_panel.html', context)


# ---------------------------------------------------------------------------
# Global Settings
# ---------------------------------------------------------------------------

def _mask_key(value: str) -> str:
    """Return a partially-masked API key showing only the last 4 chars."""
    if not value:
        return ''
    if len(value) <= 4:
        return '****'
    return '*' * min(len(value) - 4, 24) + value[-4:]


@_staff_required
def global_settings(request):
    from seo_settings.forms import SEOGlobalSettingsForm
    from seo_settings.models import SEOGlobalSettings

    gs = SEOGlobalSettings.get()

    if request.method == 'POST':
        form = SEOGlobalSettingsForm(request.POST, instance=gs)
        if form.is_valid():
            form.save()
            messages.success(request, 'SEO settings saved.')
            return redirect(reverse('seo_intel:settings'))
    else:
        form = SEOGlobalSettingsForm(instance=gs)

    serpapi_raw = os.environ.get('SERPAPI_KEY', '')
    openai_raw = os.environ.get('OPENAI_API_KEY', '')

    api_keys = [
        {
            'name': 'SerpAPI Key',
            'env_var': 'SERPAPI_KEY',
            'configured': bool(serpapi_raw),
            'masked': _mask_key(serpapi_raw),
            'docs_url': 'https://serpapi.com/dashboard',
        },
        {
            'name': 'OpenAI API Key',
            'env_var': 'OPENAI_API_KEY',
            'configured': bool(openai_raw),
            'masked': _mask_key(openai_raw),
            'docs_url': 'https://platform.openai.com/api-keys',
        },
    ]

    automation_commands = [
        {
            'command': 'run_serpapi_for_seeds',
            'description': 'Fetch SERPs for all active keyword seeds; records competitor hits, LC Psych hits, and new keyword suggestions.',
            'flags': '--limit N  --category CAT  --delay SECS  --dry-run',
        },
        {
            'command': 'promote_suggestions_to_seeds',
            'description': 'Promote PAA / related-search suggestions into KeywordSeed records.',
            'flags': '--category CAT  --source-type paa|related  --limit N  --dry-run',
        },
        {
            'command': 'score_keywords',
            'description': 'Score all keyword seeds by demand, competitor pressure, LC Psych presence, local intent, and commercial intent.',
            'flags': '--top N  --dry-run',
        },
    ]

    context = {
        'seo_title': 'SEO Intelligence — Settings | L+C Psych',
        'robots': 'noindex, nofollow',
        'form': form,
        'gs': gs,
        'api_keys': api_keys,
        'automation_commands': automation_commands,
        'active_page': 'settings',
    }
    return render(request, 'seo_settings/portal/global_settings.html', context)


# ---------------------------------------------------------------------------
# Competitor Domains
# ---------------------------------------------------------------------------

@_staff_required
def competitors(request):
    from seo_settings.forms import CompetitorDomainForm
    from seo_settings.models import CompetitorDomain

    add_form = CompetitorDomainForm()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add':
            add_form = CompetitorDomainForm(request.POST)
            if add_form.is_valid():
                obj = add_form.save()
                messages.success(request, f'Domain "{obj.domain}" added.')
                return redirect(reverse('seo_intel:competitors'))

        elif action == 'bulk_import':
            raw = request.POST.get('domains_text', '')
            created = skipped = 0
            for line in raw.splitlines():
                domain = line.strip().lower()
                for prefix in ('https://', 'http://', 'www.'):
                    if domain.startswith(prefix):
                        domain = domain[len(prefix):]
                domain = domain.split('/')[0].strip()
                if not domain:
                    continue
                try:
                    _, was_created = CompetitorDomain.objects.get_or_create(domain=domain)
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    messages.error(request, str(exc))
            if created:
                messages.success(request, f'Imported {created} domain(s).')
            if skipped:
                messages.info(request, f'{skipped} domain(s) already existed.')
            return redirect(reverse('seo_intel:competitors'))

    qs = CompetitorDomain.objects.order_by('domain')
    context = {
        'seo_title': 'SEO Intelligence — Competitors | L+C Psych',
        'robots': 'noindex, nofollow',
        'domains': qs,
        'active_count': qs.filter(active=True).count(),
        'add_form': add_form,
        'toggle_base': reverse('seo_intel:competitor_toggle', kwargs={'pk': 0}).rsplit('/0/', 1)[0] + '/',
        'delete_base': reverse('seo_intel:competitor_delete', kwargs={'pk': 0}).rsplit('/0/', 1)[0] + '/',
        'export_url': reverse('seo_intel:competitors_export'),
        'active_page': 'competitors',
    }
    return render(request, 'seo_settings/portal/competitors.html', context)


@_staff_required
def toggle_competitor(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import CompetitorDomain
    try:
        obj = CompetitorDomain.objects.get(pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=['active'])
        return JsonResponse({'success': True, 'active': obj.active})
    except CompetitorDomain.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@_staff_required
def delete_competitor(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import CompetitorDomain
    CompetitorDomain.objects.filter(pk=pk).delete()
    return JsonResponse({'success': True})


@_staff_required
def export_competitors_csv(request):
    from seo_settings.models import CompetitorDomain
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="competitor_domains.csv"'
    writer = csv.writer(response)
    writer.writerow(['Domain', 'Label', 'Active'])
    for obj in CompetitorDomain.objects.order_by('domain'):
        writer.writerow([obj.domain, obj.label, 'Yes' if obj.active else 'No'])
    return response


# ---------------------------------------------------------------------------
# Keyword Seeds
# ---------------------------------------------------------------------------

@_staff_required
def keywords(request):
    from seo_settings.forms import KeywordSeedForm
    from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

    category_filter = request.GET.get('category', '')
    add_form = KeywordSeedForm()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add':
            add_form = KeywordSeedForm(request.POST)
            if add_form.is_valid():
                obj = add_form.save()
                messages.success(request, f'Keyword "{obj.keyword}" added.')
                return redirect(reverse('seo_intel:keywords'))

        elif action == 'bulk_import':
            raw = request.POST.get('keywords_text', '')
            default_category = request.POST.get('bulk_category', 'service')
            created = skipped = 0
            for line in raw.splitlines():
                keyword = line.strip()
                if not keyword:
                    continue
                try:
                    _, was_created = KeywordSeed.objects.get_or_create(
                        keyword=keyword,
                        defaults={'category': default_category},
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    messages.error(request, str(exc))
            if created:
                messages.success(request, f'Imported {created} keyword(s).')
            if skipped:
                messages.info(request, f'{skipped} keyword(s) already existed.')
            return redirect(reverse('seo_intel:keywords'))

    qs = KeywordSeed.objects.order_by('keyword')
    if category_filter:
        qs = qs.filter(category=category_filter)

    context = {
        'seo_title': 'SEO Intelligence — Keywords | L+C Psych',
        'robots': 'noindex, nofollow',
        'keywords': qs,
        'add_form': add_form,
        'category_choices': KEYWORD_CATEGORY_CHOICES,
        'category_filter': category_filter,
        'toggle_base': reverse('seo_intel:keyword_toggle', kwargs={'pk': 0}).rsplit('/0/', 1)[0] + '/',
        'delete_base': reverse('seo_intel:keyword_delete', kwargs={'pk': 0}).rsplit('/0/', 1)[0] + '/',
        'export_url': reverse('seo_intel:keywords_export'),
        'active_page': 'keywords',
    }
    return render(request, 'seo_settings/portal/keywords.html', context)


@_staff_required
def toggle_keyword(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import KeywordSeed
    try:
        obj = KeywordSeed.objects.get(pk=pk)
        obj.active = not obj.active
        obj.save(update_fields=['active'])
        return JsonResponse({'success': True, 'active': obj.active})
    except KeywordSeed.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@_staff_required
def delete_keyword(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import KeywordSeed
    KeywordSeed.objects.filter(pk=pk).delete()
    return JsonResponse({'success': True})


@_staff_required
def export_keywords_csv(request):
    from seo_settings.models import KeywordSeed
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="keyword_seeds.csv"'
    writer = csv.writer(response)
    writer.writerow(['Keyword', 'Category', 'Active'])
    for obj in KeywordSeed.objects.order_by('keyword'):
        writer.writerow([obj.keyword, obj.get_category_display(), 'Yes' if obj.active else 'No'])
    return response


@_staff_required
def ai_suggest_keywords(request):
    """POST → JSON: return AI-generated keyword suggestions not already in the seed list."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import requests as http_requests
    from geo.models import GeoLocation, GeoState
    from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return JsonResponse({'error': 'OPENAI_API_KEY is not configured.'}, status=400)

    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    focus = (body.get('focus') or '').strip()[:200]

    existing = list(
        KeywordSeed.objects.values_list('keyword', flat=True).order_by('keyword')
    )
    category_labels = ', '.join(f'"{v}" ({label})' for v, label in KEYWORD_CATEGORY_CHOICES)

    # Pull actual service areas from the geo app
    active_states = list(
        GeoState.objects.filter(is_active=True)
        .values_list('name', 'abbreviation')
        .order_by('name')
    )
    active_cities = list(
        GeoLocation.objects
        .filter(is_active=True, location_type=GeoLocation.CITY)
        .select_related('state')
        .values_list('name', 'state__abbreviation')
        .order_by('state__name', 'name')[:60]
    )
    state_list = ', '.join(f"{name} ({abbr})" for name, abbr in active_states) or 'not configured'
    city_list = ', '.join(f"{name} {abbr}" for name, abbr in active_cities) or 'not configured'

    focus_instruction = f' Focus especially on: {focus}.' if focus else ''

    system_prompt = (
        "You are an SEO specialist for a psychology and mental health private practice. "
        "Suggest search keywords that prospective therapy clients or their families might use to find services. "
        "Return ONLY a JSON array — no prose, no code fences — where each element is an object with keys: "
        '"keyword" (string), "category" (one of: service, testing, modality, location), '
        '"reason" (one short sentence explaining relevance). '
        f"Valid categories: {category_labels}. "
        "Aim for 12–16 diverse, high-intent suggestions spanning all four categories. "
        "Incorporate currently trending mental health and psychology search topics such as: "
        "adult ADHD diagnosis, autism spectrum assessments in adults, perinatal and postpartum mood disorders, "
        "burnout and work-related stress, telehealth therapy, OCD treatment, ketamine-assisted therapy, "
        "executive functioning coaching, neurodivergent-affirming therapy, and somatic or trauma-informed care. "
        "For 'location' category keywords, ONLY use the specific cities and states this practice actually serves — "
        "do NOT suggest cities outside this list. Location keywords should be specific and local "
        "(e.g. 'anxiety therapy Florence KY') not generic regional names. "
        f"States served: {state_list}. "
        f"Cities/areas served: {city_list}. "
        "Do NOT include any keyword already in the existing list."
        f"{focus_instruction} "
        f"Existing keywords (do not repeat): {existing[:200]}"
    )
    user_prompt = (
        f"Suggest new keyword seeds for a psychology practice serving {state_list}."
        f"{' Topic focus: ' + focus if focus else ''}"
    )

    try:
        resp = http_requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.7,
                'max_tokens': 900,
            },
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as exc:
        return JsonResponse({'error': f'AI request failed: {exc}'}, status=502)

    try:
        raw = resp.json()['choices'][0]['message']['content']
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            raise ValueError('Expected a JSON array')
    except Exception as exc:
        return JsonResponse({'error': f'Could not parse AI response: {exc}'}, status=502)

    # Filter out anything already in the DB (case-insensitive)
    existing_lower = {k.lower() for k in existing}
    valid_categories = {v for v, _ in KEYWORD_CATEGORY_CHOICES}
    filtered = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        kw = (item.get('keyword') or '').strip()
        cat = (item.get('category') or 'service').strip()
        if not kw or kw.lower() in existing_lower:
            continue
        if cat not in valid_categories:
            cat = 'service'
        filtered.append({
            'keyword': kw,
            'category': cat,
            'reason': (item.get('reason') or '').strip(),
        })

    return JsonResponse({'suggestions': filtered})


@_staff_required
def bulk_add_keywords(request):
    """POST JSON array of {keyword, category} objects → add to KeywordSeed."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

    try:
        items = json.loads(request.body.decode() or '[]')
        if not isinstance(items, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Expected a JSON array.'}, status=400)

    valid_categories = {v for v, _ in KEYWORD_CATEGORY_CHOICES}
    created = skipped = 0
    for item in items:
        kw = (item.get('keyword') or '').strip()
        cat = (item.get('category') or 'service').strip()
        if not kw or cat not in valid_categories:
            continue
        _, was_created = KeywordSeed.objects.get_or_create(
            keyword=kw,
            defaults={'category': cat, 'active': True},
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    return JsonResponse({'created': created, 'skipped': skipped})


# ---------------------------------------------------------------------------
# Analytics: Search Console
# ---------------------------------------------------------------------------

@_staff_required
def analytics_sc(request):
    from datetime import timedelta

    from django.db.models import Avg, Sum

    from seo_intel.models import SearchConsoleQuery

    cutoff = timezone.now().date() - timedelta(days=90)

    daily = (
        SearchConsoleQuery.objects.filter(date__gte=cutoff)
        .values('date')
        .annotate(total_impressions=Sum('impressions'), total_clicks=Sum('clicks'))
        .order_by('date')
    )

    top_queries = list(
        SearchConsoleQuery.objects.values('query')
        .annotate(
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions'),
            avg_position=Avg('position'),
        )
        .order_by('-total_clicks')[:25]
    )

    top_pages = list(
        SearchConsoleQuery.objects.values('page')
        .annotate(total_clicks=Sum('clicks'), total_impressions=Sum('impressions'))
        .order_by('-total_clicks')[:25]
    )

    context = {
        'seo_title': 'SEO Intelligence — Search Console | L+C Psych',
        'robots': 'noindex, nofollow',
        'chart_data_json': json.dumps({
            'dates': [str(row['date']) for row in daily],
            'impressions': [row['total_impressions'] for row in daily],
            'clicks': [row['total_clicks'] for row in daily],
        }),
        'top_queries': top_queries,
        'top_pages': top_pages,
        'total_records': SearchConsoleQuery.objects.count(),
        'action_run_sc': reverse('seo_intel:action_run_sc'),
        'active_page': 'analytics_sc',
    }
    return render(request, 'seo_settings/portal/analytics_sc.html', context)


# ---------------------------------------------------------------------------
# Analytics: Internal Search
# ---------------------------------------------------------------------------

@_staff_required
def analytics_internal(request):
    from django.db.models import Count

    from seo_intel.models import InternalSearchQuery

    top_terms = list(
        InternalSearchQuery.objects.values('term')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    recent = list(InternalSearchQuery.objects.order_by('-timestamp')[:50])

    rare_terms = list(
        InternalSearchQuery.objects.values('term')
        .annotate(count=Count('id'))
        .filter(count=1)
        .order_by('term')[:50]
    )

    context = {
        'seo_title': 'SEO Intelligence — Internal Search | L+C Psych',
        'robots': 'noindex, nofollow',
        'chart_data_json': json.dumps({
            'labels': [row['term'] for row in top_terms],
            'values': [row['count'] for row in top_terms],
        }),
        'top_terms': top_terms,
        'recent_searches': recent,
        'rare_terms': rare_terms,
        'total_searches': InternalSearchQuery.objects.count(),
        'action_clear_internal': reverse('seo_intel:action_clear_internal'),
        'active_page': 'analytics_internal',
    }
    return render(request, 'seo_settings/portal/analytics_internal.html', context)


# ---------------------------------------------------------------------------
# Analytics: Dead URLs
# ---------------------------------------------------------------------------

@_staff_required
def analytics_dead_urls(request):
    from django.db.models import Count, Q

    from seo_intel.models import DeadURLHit
    from seo_settings.models import CompetitorDomain

    top_urls = list(
        DeadURLHit.objects.values('url')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    chart_labels = [
        (row['url'][:55] + '\u2026') if len(row['url']) > 55 else row['url']
        for row in top_urls
    ]

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
        DeadURLHit.objects.exclude(referrer__isnull=True)
        .exclude(referrer='')
        .values('referrer')
        .annotate(count=Count('id'))
        .order_by('-count')[:25]
    )

    context = {
        'seo_title': 'SEO Intelligence — Dead URLs | L+C Psych',
        'robots': 'noindex, nofollow',
        'chart_data_json': json.dumps({
            'labels': chart_labels,
            'values': [row['count'] for row in top_urls],
        }),
        'top_urls': top_urls,
        'competitor_hits': competitor_hits,
        'top_referrers': top_referrers,
        'total_hits': DeadURLHit.objects.count(),
        'action_clear_dead': reverse('seo_intel:action_clear_dead'),
        'active_page': 'analytics_dead_urls',
    }
    return render(request, 'seo_settings/portal/analytics_dead_urls.html', context)


# ---------------------------------------------------------------------------
# Analytics: Content Gaps
# ---------------------------------------------------------------------------

@_staff_required
def analytics_gaps(request):
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

    export_params = {
        k: v
        for k, v in request.GET.items()
        if k in ('resolved', 'competitor_presence', 'lcpsych_presence')
    }
    export_url = reverse('seo_intel:gaps_export')
    if export_params:
        export_url += '?' + urlencode(export_params)

    context = {
        'seo_title': 'SEO Intelligence — Content Gaps | L+C Psych',
        'robots': 'noindex, nofollow',
        'records': qs.order_by('-search_volume')[:200],
        'total': qs.count(),
        'export_url': export_url,
        'filter_resolved': resolved,
        'filter_competitor_presence': cp,
        'filter_lcpsych_presence': lp,
        'action_run_gap': reverse('seo_intel:action_run_gap'),
        'active_page': 'analytics_gaps',
    }
    return render(request, 'seo_settings/portal/analytics_gaps.html', context)


@_staff_required
def export_gaps_csv(request):
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

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="content_gaps.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Keyword', 'Search Volume', 'Competitor Presence', 'LC Psych Presence',
        'Recommended Action', 'Resolved', 'Date',
    ])
    for rec in qs.order_by('-search_volume'):
        writer.writerow([
            rec.keyword, rec.search_volume,
            'Yes' if rec.competitor_presence else 'No',
            'Yes' if rec.lcpsych_presence else 'No',
            rec.recommended_action,
            'Yes' if rec.resolved else 'No',
            rec.timestamp.date() if rec.timestamp else '',
        ])
    return response



