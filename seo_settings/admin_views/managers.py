from __future__ import annotations

import csv

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from urllib.parse import urlencode


# ---------------------------------------------------------------------------
# Competitor Domain Manager
# ---------------------------------------------------------------------------

def render_competitor_manager(request, admin_site):
    from seo_settings.forms import CompetitorDomainForm
    from seo_settings.models import CompetitorDomain

    add_form = CompetitorDomainForm()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add':
            add_form = CompetitorDomainForm(request.POST)
            if add_form.is_valid():
                obj = add_form.save()
                messages.success(request, f'Domain "{obj.domain}" added successfully.')
                return redirect(reverse('admin:seo_settings_competitordomain_manager'))
            # Fall through — re-render with form errors

        elif action == 'bulk_import':
            raw = request.POST.get('domains_text', '')
            created = skipped = 0
            errors = []

            for line in raw.splitlines():
                raw_val = line.strip().lower()
                if not raw_val:
                    continue
                # Strip URL prefixes so users can paste full URLs
                domain = raw_val
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
                    errors.append(f'{domain}: {exc}')

            if created:
                messages.success(request, f'Imported {created} new domain(s).')
            if skipped:
                messages.info(request, f'{skipped} domain(s) already existed and were skipped.')
            for err in errors:
                messages.error(request, err)
            return redirect(reverse('admin:seo_settings_competitordomain_manager'))

    domains = CompetitorDomain.objects.order_by('domain')
    active_count = domains.filter(active=True).count()

    context = {
        **admin_site.each_context(request),
        'title': 'Competitor Domain Manager',
        'domains': domains,
        'domain_count': domains.count(),
        'active_count': active_count,
        'add_form': add_form,
        'export_url': reverse('admin:seo_settings_competitordomain_export_csv'),
        'opts': CompetitorDomain._meta,
        'app_label': 'seo_settings',
    }
    return TemplateResponse(request, 'seo_settings/competitors.html', context)


def toggle_competitor_active(request, admin_site, pk):
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


def delete_competitor(request, admin_site, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import CompetitorDomain
    try:
        CompetitorDomain.objects.filter(pk=pk).delete()
        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


def export_competitors_csv(request, admin_site):
    from seo_settings.models import CompetitorDomain
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="competitor_domains.csv"'
    writer = csv.writer(response)
    writer.writerow(['Domain', 'Label', 'Active'])
    for obj in CompetitorDomain.objects.order_by('domain'):
        writer.writerow([obj.domain, obj.label, 'Yes' if obj.active else 'No'])
    return response


# ---------------------------------------------------------------------------
# Keyword Seed Manager
# ---------------------------------------------------------------------------

def render_keyword_manager(request, admin_site):
    from seo_settings.forms import KeywordSeedForm
    from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

    category_filter = request.GET.get('category', '')
    add_form = KeywordSeedForm()

    if request.method == 'POST':
        action = request.POST.get('action', '')
        # Preserve category filter across redirects
        next_url = reverse('admin:seo_settings_keywordseed_manager')
        if category_filter:
            next_url += '?' + urlencode({'category': category_filter})

        if action == 'add':
            add_form = KeywordSeedForm(request.POST)
            if add_form.is_valid():
                obj = add_form.save()
                messages.success(request, f'Keyword "{obj.keyword}" added successfully.')
                return redirect(next_url)
            # Fall through — re-render with form errors

        elif action == 'bulk_import':
            raw = request.POST.get('keywords_text', '')
            default_category = request.POST.get('bulk_category', 'service')
            created = skipped = 0

            for line in raw.splitlines():
                keyword = line.strip()
                if not keyword or len(keyword) > 500:
                    continue
                _, was_created = KeywordSeed.objects.get_or_create(
                    keyword=keyword,
                    category=default_category,
                    defaults={'active': True},
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

            if created:
                messages.success(request, f'Imported {created} new keyword(s).')
            if skipped:
                messages.info(request, f'{skipped} keyword(s) already existed and were skipped.')
            return redirect(next_url)

    qs = KeywordSeed.objects.all()
    if category_filter:
        qs = qs.filter(category=category_filter)
    keywords = qs.order_by('category', 'keyword')

    # Per-category counts for filter tabs — precomputed as list of dicts so
    # Django templates can iterate without needing a custom dict-key filter.
    total_count = KeywordSeed.objects.count()
    category_tabs = [
        {
            'code': code,
            'label': label,
            'count': KeywordSeed.objects.filter(category=code).count(),
            'active': category_filter == code,
        }
        for code, label in KEYWORD_CATEGORY_CHOICES
    ]

    # Build export URL (preserve category filter)
    export_url = reverse('admin:seo_settings_keywordseed_export_csv')
    if category_filter:
        export_url += '?' + urlencode({'category': category_filter})

    context = {
        **admin_site.each_context(request),
        'title': 'Keyword Seed Manager',
        'keywords': keywords,
        'total_count': total_count,
        'filtered_count': keywords.count(),
        'add_form': add_form,
        'category_choices': KEYWORD_CATEGORY_CHOICES,
        'category_filter': category_filter,
        'category_tabs': category_tabs,
        'export_url': export_url,
        'opts': KeywordSeed._meta,
        'app_label': 'seo_settings',
    }
    return TemplateResponse(request, 'seo_settings/keywords.html', context)


def toggle_keyword_active(request, admin_site, pk):
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


def delete_keyword(request, admin_site, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    from seo_settings.models import KeywordSeed
    try:
        KeywordSeed.objects.filter(pk=pk).delete()
        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


def export_keywords_csv(request, admin_site):
    from seo_settings.models import KeywordSeed
    category_filter = request.GET.get('category', '')
    qs = KeywordSeed.objects.all()
    if category_filter:
        qs = qs.filter(category=category_filter)

    fname = f'keyword_seeds_{category_filter}.csv' if category_filter else 'keyword_seeds.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    writer = csv.writer(response)
    writer.writerow(['Keyword', 'Category', 'Active'])
    for obj in qs.order_by('category', 'keyword'):
        writer.writerow([obj.keyword, obj.get_category_display(), 'Yes' if obj.active else 'No'])
    return response
