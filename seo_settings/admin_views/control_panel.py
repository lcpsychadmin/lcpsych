from __future__ import annotations

from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse


def render_control_panel(request, admin_site):
    """Render the SEO Intelligence Control Panel page."""
    from seo_intel.models import (
        CompetitorSERPResult,
        ContentGapRecord,
        DeadURLHit,
        InternalSearchQuery,
        SearchConsoleQuery,
    )
    from seo_settings.models import CompetitorDomain, KeywordSeed, SEOGlobalSettings

    gs = SEOGlobalSettings.get()

    def _count(manager_or_qs):
        try:
            return manager_or_qs.count()
        except Exception:
            return 0

    def _url(name, *args, **kwargs):
        try:
            return reverse(name, args=args, kwargs=kwargs)
        except NoReverseMatch:
            return '#'

    stats = {
        'sc_queries': _count(SearchConsoleQuery.objects),
        'internal_searches': _count(InternalSearchQuery.objects),
        'dead_urls': _count(DeadURLHit.objects),
        'competitor_results': _count(CompetitorSERPResult.objects),
        'content_gaps_open': _count(ContentGapRecord.objects.filter(resolved=False)),
        'competitor_domains': _count(CompetitorDomain.objects.filter(active=True)),
        'keyword_seeds': _count(KeywordSeed.objects.filter(active=True)),
    }

    modules = [
        {
            'name': 'Search Console',
            'enabled': gs.enable_search_console,
            'icon': 'bi-graph-up',
            'stat': stats['sc_queries'],
            'stat_label': 'Queries on record',
            'admin_url': _url('admin:seo_intel_searchconsolequery_changelist'),
        },
        {
            'name': 'Internal Search',
            'enabled': gs.enable_internal_search_tracking,
            'icon': 'bi-search',
            'stat': stats['internal_searches'],
            'stat_label': 'Searches logged',
            'admin_url': _url('admin:seo_intel_internalsearchquery_changelist'),
        },
        {
            'name': 'Dead URL Logging',
            'enabled': gs.enable_dead_url_logging,
            'icon': 'bi-x-circle',
            'stat': stats['dead_urls'],
            'stat_label': '404 hits logged',
            'admin_url': _url('admin:seo_intel_deadurlhit_changelist'),
        },
        {
            'name': 'Competitor Scraping',
            'enabled': gs.enable_competitor_scraping,
            'icon': 'bi-people',
            'stat': stats['competitor_results'],
            'stat_label': 'SERP results',
            'admin_url': _url('admin:seo_intel_competitorserpresult_changelist'),
        },
        {
            'name': 'Gap Analysis',
            'enabled': gs.enable_gap_analysis,
            'icon': 'bi-bar-chart-line',
            'stat': stats['content_gaps_open'],
            'stat_label': 'Open gaps',
            'admin_url': _url('admin:seo_intel_contentgaprecord_changelist'),
        },
    ]

    action_groups = [
        {
            'title': 'Configuration',
            'icon': 'bi-gear',
            'icon_color': 'primary',
            'actions': [
                {
                    'label': 'SEO Settings',
                    'url': _url('admin:seo_settings_seoglobalsettings_dashboard'),
                    'icon': 'bi-gear-fill',
                    'variant': 'primary',
                },
                {
                    'label': 'Competitor Domains',
                    'url': _url('admin:seo_settings_competitordomain_changelist'),
                    'icon': 'bi-globe',
                    'variant': 'outline-secondary',
                },
                {
                    'label': 'Keyword Seeds',
                    'url': _url('admin:seo_settings_keywordseed_changelist'),
                    'icon': 'bi-tags',
                    'variant': 'outline-secondary',
                },
            ],
        },
        {
            'title': 'Analytics Dashboards',
            'icon': 'bi-graph-up',
            'icon_color': 'info',
            'actions': [
                {
                    'label': 'Search Console Data',
                    'url': _url('admin:seo_intel_searchconsolequery_changelist'),
                    'icon': 'bi-graph-up',
                    'variant': 'outline-primary',
                },
                {
                    'label': 'Internal Searches',
                    'url': _url('admin:seo_intel_internalsearchquery_changelist'),
                    'icon': 'bi-search',
                    'variant': 'outline-info',
                },
                {
                    'label': 'Dead URLs / 404s',
                    'url': _url('admin:seo_intel_deadurlhit_changelist'),
                    'icon': 'bi-slash-circle',
                    'variant': 'outline-warning',
                },
            ],
        },
        {
            'title': 'Intelligence',
            'icon': 'bi-lightbulb',
            'icon_color': 'warning',
            'actions': [
                {
                    'label': 'Competitor Results',
                    'url': _url('admin:seo_intel_competitorserpresult_changelist'),
                    'icon': 'bi-trophy',
                    'variant': 'outline-danger',
                },
                {
                    'label': 'Gap Analysis Results',
                    'url': _url('admin:seo_intel_contentgaprecord_changelist'),
                    'icon': 'bi-bar-chart-line',
                    'variant': 'outline-success',
                },
            ],
        },
    ]

    context = {
        **admin_site.each_context(request),
        'title': 'SEO Intelligence Control Panel',
        'global_settings': gs,
        'stats': stats,
        'modules': modules,
        'action_groups': action_groups,
        # Credential config status (field-presence only — no live API call)
        'creds_configured': bool(
            gs.google_client_email.strip() and gs.google_private_key.strip()
        ),
        'property_configured': bool(gs.search_console_property_url.strip()),
        # Quick links to the two test endpoints for JS buttons
        'test_creds_url': _url('admin:seo_settings_seoglobalsettings_test_google_api'),
        'test_gsc_url': _url('admin:seo_settings_seoglobalsettings_test_search_console'),
        'settings_url': _url('admin:seo_settings_seoglobalsettings_dashboard'),
        'action_urls': {
            'run_sc_pull': _url('admin:seo_settings_seocontrolpanel_run_sc_pull'),
            'run_scrape': _url('admin:seo_settings_seocontrolpanel_run_scrape'),
            'run_gap': _url('admin:seo_settings_seocontrolpanel_run_gap'),
            'clear_dead_urls': _url('admin:seo_settings_seocontrolpanel_clear_dead_urls'),
            'clear_internal_search': _url('admin:seo_settings_seocontrolpanel_clear_internal_search'),
            'clear_competitor_results': _url('admin:seo_settings_seocontrolpanel_clear_competitor_results'),
        },
    }
    return TemplateResponse(request, 'admin/seo_settings/control_panel.html', context)
