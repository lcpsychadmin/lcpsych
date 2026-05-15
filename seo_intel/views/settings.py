"""
seo_intel/views/settings.py
-----------------------------
Comprehensive SERP Intelligence settings page.

Consolidates: API key status, competitor domains, keyword seeds, and an
automation schedule overview into a single staff-only page.
"""
from __future__ import annotations

import os
from functools import wraps

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse


# ---------------------------------------------------------------------------
# Auth decorator (mirrors seo_settings/views/portal.py)
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
# Helpers
# ---------------------------------------------------------------------------

_KEYWORD_CATEGORY_CHOICES = [
    ('service', 'Service'),
    ('testing', 'Testing'),
    ('modality', 'Modality'),
    ('location', 'Location'),
]

_VALID_CATEGORIES = {v for v, _ in _KEYWORD_CATEGORY_CHOICES}


def _mask_key(value: str) -> str:
    """Return a partially-masked API key showing only the last 4 chars."""
    if not value:
        return ''
    if len(value) <= 4:
        return '****'
    return '*' * min(len(value) - 4, 24) + value[-4:]


def _normalise_domain(raw: str) -> str:
    """Strip scheme / path from a pasted domain string."""
    domain = raw.strip().lower()
    for prefix in ('https://', 'http://', 'www.'):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.split('/')[0].strip()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@_staff_required
def serp_settings(request):
    from seo_settings.models import CompetitorDomain, KeywordSeed

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_competitor':
            domain = _normalise_domain(request.POST.get('domain', ''))
            label = request.POST.get('label', '').strip()[:200]
            if domain:
                _, created = CompetitorDomain.objects.get_or_create(
                    domain=domain,
                    defaults={'label': label},
                )
                if created:
                    msg = f'Competitor domain \u201c{domain}\u201d added.'
                    messages.success(request, msg)
                else:
                    msg = f'\u201c{domain}\u201d already exists.'
                    messages.info(request, msg)
            else:
                msg = 'Please enter a valid domain.'
            if request.headers.get('HX-Request'):
                return render(request, 'seo_intel/partials/_settings_saved.html',
                              {'message': msg, 'is_error': not domain})
            return redirect(reverse('seo_intel:serp_settings'))

        elif action == 'add_keyword':
            keyword = request.POST.get('keyword', '').strip()[:500]
            category = request.POST.get('category', 'service')
            if keyword and category in _VALID_CATEGORIES:
                _, created = KeywordSeed.objects.get_or_create(
                    keyword=keyword,
                    defaults={'category': category},
                )
                if created:
                    msg = f'Keyword \u201c{keyword}\u201d added.'
                    messages.success(request, msg)
                else:
                    msg = f'\u201c{keyword}\u201d already exists.'
                    messages.info(request, msg)
            else:
                msg = 'Please enter a valid keyword.'
            if request.headers.get('HX-Request'):
                return render(request, 'seo_intel/partials/_settings_saved.html',
                              {'message': msg, 'is_error': not (keyword and category in _VALID_CATEGORIES)})
            return redirect(reverse('seo_intel:serp_settings'))

    # --- Build context ---

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

    # Build base URLs for toggle / delete (reuse existing JSON endpoints)
    def _base_url(name, kwarg='pk', sentinel=0):
        full = reverse(f'seo_intel:{name}', kwargs={kwarg: sentinel})
        return full.rsplit(f'/{sentinel}/', 1)[0] + '/'

    context = {
        'seo_title': 'SEO Intelligence \u2014 SERP Settings | L+C Psych',
        'robots': 'noindex, nofollow',
        'active_page': 'serp_settings',
        'api_keys': api_keys,
        'competitors': CompetitorDomain.objects.order_by('domain'),
        'keywords': KeywordSeed.objects.order_by('category', 'keyword'),
        'category_choices': _KEYWORD_CATEGORY_CHOICES,
        'automation_commands': automation_commands,
        'toggle_competitor_base': _base_url('competitor_toggle'),
        'delete_competitor_base': _base_url('competitor_delete'),
        'toggle_keyword_base': _base_url('keyword_toggle'),
        'delete_keyword_base': _base_url('keyword_delete'),
    }
    return render(request, 'seo_intel/settings.html', context)
