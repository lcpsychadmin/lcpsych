from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, path, reverse


# ---------------------------------------------------------------------------
# Custom AdminSite — injects SEO Intelligence nav into every page context.
# We monkey-patch admin.site's class so all existing @admin.register()
# calls keep working without any re-registration.
# ---------------------------------------------------------------------------

class LCPsychAdminSite(admin.AdminSite):
    """Default admin site with the SEO Intelligence sidebar group added."""

    def each_context(self, request):
        ctx = super().each_context(request)
        ctx['seo_nav'] = self._build_seo_nav(request)
        return ctx

    def _build_seo_nav(self, request):
        """Return a structured nav list for the SEO Intelligence sidebar group.

        Each entry:
          {'label': str, 'url': str, 'icon': str, 'children': list | None}

        'children' is non-None only for the Analytics submenu.
        Returns an empty list when the user lacks staff access.
        """
        if not (request.user.is_active and request.user.is_staff):
            return []

        is_super = request.user.is_superuser
        has = request.user.has_perm

        def safe_url(name):
            try:
                return reverse(name)
            except NoReverseMatch:
                return '#'

        def nav_item(label, perm, url_name, icon='', children=None):
            """Return a nav item dict if the user has the required permission."""
            if is_super or has(perm):
                return {
                    'label': label,
                    'url': safe_url(url_name) if url_name else None,
                    'icon': icon,
                    'children': children,
                }
            return None

        analytics_children = [x for x in [
            nav_item('Search Console',    'seo_settings.view_searchconsoledashboard',   'admin:seo_settings_searchconsoledashboard_dashboard',   'bar-chart-fill'),
            nav_item('Internal Search',   'seo_settings.view_internalsearchdashboard',  'admin:seo_settings_internalsearchdashboard_dashboard',  'search'),
            nav_item('Dead URLs',         'seo_settings.view_deadurlanalytics',         'admin:seo_settings_deadurlanalytics_dashboard',         'link-45deg'),
            nav_item('Competitor SERPs',  'seo_settings.view_competitorserpanalytics',  'admin:seo_settings_competitorserpanalytics_dashboard',  'trophy-fill'),
            nav_item('Content Gaps',      'seo_settings.view_contentgapanalytics',      'admin:seo_settings_contentgapanalytics_dashboard',      'diagram-3'),
            nav_item('Gap Review',         'seo_settings.view_contentgapanalytics',      'admin:seo_settings_contentgapanalytics_review',          'check2-square'),
        ] if x is not None]

        analytics_item = (
            {'label': 'Analytics', 'url': None, 'icon': 'graph-up-arrow', 'children': analytics_children}
            if analytics_children else None
        )

        nav = [x for x in [
            nav_item('Control Panel',      'seo_settings.view_seocontrolpanel',         'admin:seo_settings_seocontrolpanel_panel',              'speedometer2'),
            nav_item('Settings',           'seo_settings.change_seoglobalsettings',     'admin:seo_settings_seoglobalsettings_dashboard',        'gear-fill'),
            nav_item('Competitor Domains', 'seo_settings.view_competitordomain',        'admin:seo_settings_competitordomain_manager',           'globe'),
            nav_item('Keyword Seeds',      'seo_settings.view_keywordseed',             'admin:seo_settings_keywordseed_manager',                'tags-fill'),
            analytics_item,
        ] if x is not None]

        return nav


# Swap the default site's class so all registered models are preserved.
admin.site.__class__ = LCPsychAdminSite

from .forms import CompetitorDomainForm, KeywordSeedForm, SEOGlobalSettingsForm
from .models import (
    CompetitorDomain,
    CompetitorSERPAnalytics,
    ContentGapAnalytics,
    DeadURLAnalytics,
    InternalSearchDashboard,
    KeywordSeed,
    KEYWORD_CATEGORY_CHOICES,
    SearchConsoleDashboard,
    SEOControlPanel,
    SEOGlobalSettings,
)


# ---------------------------------------------------------------------------
# SEOGlobalSettings — singleton with custom dashboard
# ---------------------------------------------------------------------------

@admin.register(SEOGlobalSettings)
class SEOGlobalSettingsAdmin(admin.ModelAdmin):

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.dashboard_view),
                name='seo_settings_seoglobalsettings_dashboard',
            ),
            path(
                'test-google-api/',
                self.admin_site.admin_view(self.test_google_api_view),
                name='seo_settings_seoglobalsettings_test_google_api',
            ),
            path(
                'test-search-console/',
                self.admin_site.admin_view(self.test_search_console_view),
                name='seo_settings_seoglobalsettings_test_search_console',
            ),
            path(
                'run-competitor-scrape/',
                self.admin_site.admin_view(self.run_competitor_scrape_view),
                name='seo_settings_seoglobalsettings_run_competitor_scrape',
            ),
            path(
                'run-gap-analysis/',
                self.admin_site.admin_view(self.run_gap_analysis_view),
                name='seo_settings_seoglobalsettings_run_gap_analysis',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """Redirect the list view straight to the dashboard."""
        return redirect(reverse('admin:seo_settings_seoglobalsettings_dashboard'))

    def has_add_permission(self, request):
        return not SEOGlobalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    # -----------------------------------------------------------------------
    # Dashboard view (GET: show form, POST: save form)
    # -----------------------------------------------------------------------

    def dashboard_view(self, request):
        global_settings = SEOGlobalSettings.get()

        if request.method == 'POST':
            form = SEOGlobalSettingsForm(request.POST, instance=global_settings)
            if form.is_valid():
                form.save()
                messages.success(request, 'SEO settings saved successfully.')
                return redirect(reverse('admin:seo_settings_seoglobalsettings_dashboard'))
        else:
            form = SEOGlobalSettingsForm(instance=global_settings)

        toggle_fields = [form[f] for f in [
            'enable_search_console',
            'enable_internal_search_tracking',
            'enable_dead_url_logging',
            'enable_competitor_scraping',
            'enable_gap_analysis',
        ]]
        gsc_fields = [form[f] for f in [
            'search_console_property_url',
            'google_client_email',
            'google_private_key',
        ]]
        status_modules = [
            ('Search Console', global_settings.enable_search_console),
            ('Internal Search Tracking', global_settings.enable_internal_search_tracking),
            ('Dead URL Logging', global_settings.enable_dead_url_logging),
            ('Competitor Scraping', global_settings.enable_competitor_scraping),
            ('Gap Analysis', global_settings.enable_gap_analysis),
        ]

        competitor_count = CompetitorDomain.objects.count()
        active_competitor_count = CompetitorDomain.objects.filter(active=True).count()
        keyword_count = KeywordSeed.objects.count()
        keyword_stats = [
            {
                'code': code,
                'label': label,
                'active': KeywordSeed.objects.filter(category=code, active=True).count(),
                'total': KeywordSeed.objects.filter(category=code).count(),
            }
            for code, label in KEYWORD_CATEGORY_CHOICES
        ]

        context = {
            **self.admin_site.each_context(request),
            'title': 'SEO Settings Dashboard',
            'form': form,
            'global_settings': global_settings,
            'toggle_fields': toggle_fields,
            'gsc_fields': gsc_fields,
            'status_modules': status_modules,
            'competitor_count': competitor_count,
            'active_competitor_count': active_competitor_count,
            'keyword_count': keyword_count,
            'keyword_stats': keyword_stats,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        return TemplateResponse(
            request,
            'seo_settings/settings_dashboard.html',
            context,
        )

    # -----------------------------------------------------------------------
    # Google API credential test (POST → JSON)
    # -----------------------------------------------------------------------

    def test_google_api_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        result = SEOGlobalSettingsForm.test_google_credentials(SEOGlobalSettings.get())
        return JsonResponse(result)

    def test_search_console_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        result = SEOGlobalSettingsForm.test_search_console_connection(SEOGlobalSettings.get())
        return JsonResponse(result)

    # -----------------------------------------------------------------------
    # Manual task triggers (POST → JSON)
    # -----------------------------------------------------------------------

    def run_competitor_scrape_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        settings_obj = SEOGlobalSettings.get()
        if not settings_obj.enable_competitor_scraping:
            return JsonResponse(
                {'success': False, 'error': 'Competitor scraping is disabled. Enable it in Feature Toggles first.'},
                status=400,
            )
        try:
            from seo_intel.tasks import scrape_competitor_serp
            result = scrape_competitor_serp.delay()
            return JsonResponse({'success': True, 'message': f'Competitor scrape queued (task ID: {result.id})'})
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    def run_gap_analysis_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        settings_obj = SEOGlobalSettings.get()
        if not settings_obj.enable_gap_analysis:
            return JsonResponse(
                {'success': False, 'error': 'Gap analysis is disabled. Enable it in Feature Toggles first.'},
                status=400,
            )
        try:
            from seo_intel.tasks import analyse_content_gaps
            result = analyse_content_gaps.delay()
            return JsonResponse({'success': True, 'message': f'Gap analysis queued (task ID: {result.id})'})
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)


# ---------------------------------------------------------------------------
# SEOControlPanel — proxy model that creates the "Control Panel" menu entry
# ---------------------------------------------------------------------------

@admin.register(SEOControlPanel)
class SEOControlPanelAdmin(admin.ModelAdmin):

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'panel/',
                self.admin_site.admin_view(self._control_panel_view),
                name='seo_settings_seocontrolpanel_panel',
            ),
            # ── Run actions ───────────────────────────────────────────
            path(
                'actions/run-sc-pull/',
                self.admin_site.admin_view(self._run_sc_pull_view),
                name='seo_settings_seocontrolpanel_run_sc_pull',
            ),
            path(
                'actions/run-scrape/',
                self.admin_site.admin_view(self._run_scrape_view),
                name='seo_settings_seocontrolpanel_run_scrape',
            ),
            path(
                'actions/run-gap/',
                self.admin_site.admin_view(self._run_gap_view),
                name='seo_settings_seocontrolpanel_run_gap',
            ),
            # ── Clear actions ─────────────────────────────────────────
            path(
                'actions/clear-dead-urls/',
                self.admin_site.admin_view(self._clear_dead_urls_view),
                name='seo_settings_seocontrolpanel_clear_dead_urls',
            ),
            path(
                'actions/clear-internal-search/',
                self.admin_site.admin_view(self._clear_internal_search_view),
                name='seo_settings_seocontrolpanel_clear_internal_search',
            ),
            path(
                'actions/clear-competitor-results/',
                self.admin_site.admin_view(self._clear_competitor_results_view),
                name='seo_settings_seocontrolpanel_clear_competitor_results',
            ),
        ]
        return custom_urls + urls

    def _control_panel_view(self, request):
        from seo_settings.admin_views.control_panel import render_control_panel
        return render_control_panel(request, self.admin_site)

    def _run_sc_pull_view(self, request):
        from seo_settings.views.actions import run_search_console_pull
        return run_search_console_pull(request)

    def _run_scrape_view(self, request):
        from seo_settings.views.actions import run_competitor_scrape
        return run_competitor_scrape(request)

    def _run_gap_view(self, request):
        from seo_settings.views.actions import run_gap_analysis
        return run_gap_analysis(request)

    def _clear_dead_urls_view(self, request):
        from seo_settings.views.actions import clear_dead_urls
        return clear_dead_urls(request)

    def _clear_internal_search_view(self, request):
        from seo_settings.views.actions import clear_internal_search
        return clear_internal_search(request)

    def _clear_competitor_results_view(self, request):
        from seo_settings.views.actions import clear_competitor_results
        return clear_competitor_results(request)

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin:seo_settings_seocontrolpanel_panel'))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True


# ---------------------------------------------------------------------------
# CompetitorDomain
# ---------------------------------------------------------------------------

@admin.register(CompetitorDomain)
class CompetitorDomainAdmin(admin.ModelAdmin):
    form = CompetitorDomainForm
    # Standard add/change views are still used for single-record editing;
    # the custom manager page replaces the changelist.

    def get_urls(self):
        custom_urls = [
            path(
                'manager/',
                self.admin_site.admin_view(self._manager_view),
                name='seo_settings_competitordomain_manager',
            ),
            path(
                'toggle/<int:pk>/',
                self.admin_site.admin_view(self._toggle_view),
                name='seo_settings_competitordomain_toggle',
            ),
            path(
                'delete-ajax/<int:pk>/',
                self.admin_site.admin_view(self._delete_ajax_view),
                name='seo_settings_competitordomain_delete_ajax',
            ),
            path(
                'export-csv/',
                self.admin_site.admin_view(self._export_csv_view),
                name='seo_settings_competitordomain_export_csv',
            ),
        ]
        return custom_urls + super().get_urls()

    def _manager_view(self, request):
        from seo_settings.admin_views.managers import render_competitor_manager
        return render_competitor_manager(request, self.admin_site)

    def _toggle_view(self, request, pk):
        from seo_settings.admin_views.managers import toggle_competitor_active
        return toggle_competitor_active(request, self.admin_site, pk)

    def _delete_ajax_view(self, request, pk):
        from seo_settings.admin_views.managers import delete_competitor
        return delete_competitor(request, self.admin_site, pk)

    def _export_csv_view(self, request):
        from seo_settings.admin_views.managers import export_competitors_csv
        return export_competitors_csv(request, self.admin_site)

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin:seo_settings_competitordomain_manager'))


# ---------------------------------------------------------------------------
# KeywordSeed
# ---------------------------------------------------------------------------

@admin.register(KeywordSeed)
class KeywordSeedAdmin(admin.ModelAdmin):
    form = KeywordSeedForm
    # Standard add/change views are still used for single-record editing;
    # the custom manager page replaces the changelist.

    def get_urls(self):
        custom_urls = [
            path(
                'manager/',
                self.admin_site.admin_view(self._manager_view),
                name='seo_settings_keywordseed_manager',
            ),
            path(
                'toggle/<int:pk>/',
                self.admin_site.admin_view(self._toggle_view),
                name='seo_settings_keywordseed_toggle',
            ),
            path(
                'delete-ajax/<int:pk>/',
                self.admin_site.admin_view(self._delete_ajax_view),
                name='seo_settings_keywordseed_delete_ajax',
            ),
            path(
                'export-csv/',
                self.admin_site.admin_view(self._export_csv_view),
                name='seo_settings_keywordseed_export_csv',
            ),
        ]
        return custom_urls + super().get_urls()

    def _manager_view(self, request):
        from seo_settings.admin_views.managers import render_keyword_manager
        return render_keyword_manager(request, self.admin_site)

    def _toggle_view(self, request, pk):
        from seo_settings.admin_views.managers import toggle_keyword_active
        return toggle_keyword_active(request, self.admin_site, pk)

    def _delete_ajax_view(self, request, pk):
        from seo_settings.admin_views.managers import delete_keyword
        return delete_keyword(request, self.admin_site, pk)

    def _export_csv_view(self, request):
        from seo_settings.admin_views.managers import export_keywords_csv
        return export_keywords_csv(request, self.admin_site)

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin:seo_settings_keywordseed_manager'))


# ---------------------------------------------------------------------------
# Analytics dashboards — one ModelAdmin per proxy model
# ---------------------------------------------------------------------------

def _make_analytics_admin(view_fn_name, url_suffix, url_name_suffix):
    """Return a ModelAdmin class wired to the named analytics view function."""

    class _AnalyticsAdmin(admin.ModelAdmin):

        def get_urls(self):
            return [
                path(
                    f'{url_suffix}/',
                    self.admin_site.admin_view(self._dashboard_view),
                    name=url_name_suffix,
                ),
            ] + super().get_urls()

        def _dashboard_view(self, request):
            import importlib
            mod = importlib.import_module('seo_settings.admin_views.analytics')
            return getattr(mod, view_fn_name)(request, self.admin_site)

        def changelist_view(self, request, extra_context=None):
            return redirect(reverse(f'admin:{url_name_suffix}'))

        def has_add_permission(self, request):
            return False

        def has_delete_permission(self, request, obj=None):
            return False

        def has_change_permission(self, request, obj=None):
            return True

    return _AnalyticsAdmin


@admin.register(SearchConsoleDashboard)
class SearchConsoleDashboardAdmin(
    _make_analytics_admin(
        'render_search_console',
        'dashboard',
        'seo_settings_searchconsoledashboard_dashboard',
    )
):
    pass


@admin.register(InternalSearchDashboard)
class InternalSearchDashboardAdmin(
    _make_analytics_admin(
        'render_internal_search',
        'dashboard',
        'seo_settings_internalsearchdashboard_dashboard',
    )
):
    pass


@admin.register(DeadURLAnalytics)
class DeadURLAnalyticsAdmin(
    _make_analytics_admin(
        'render_dead_urls',
        'dashboard',
        'seo_settings_deadurlanalytics_dashboard',
    )
):
    pass


@admin.register(CompetitorSERPAnalytics)
class CompetitorSERPAnalyticsAdmin(
    _make_analytics_admin(
        'render_competitor_serp',
        'dashboard',
        'seo_settings_competitorserpanalytics_dashboard',
    )
):
    pass


@admin.register(ContentGapAnalytics)
class ContentGapAnalyticsAdmin(admin.ModelAdmin):
    """Content gap dashboard — extra URL for CSV export."""

    def get_urls(self):
        return [
            path(
                'dashboard/',
                self.admin_site.admin_view(self._dashboard_view),
                name='seo_settings_contentgapanalytics_dashboard',
            ),
            path(
                'export-csv/',
                self.admin_site.admin_view(self._export_csv),
                name='seo_settings_contentgapanalytics_export_csv',
            ),
            path(
                'review/',
                self.admin_site.admin_view(self._review_view),
                name='seo_settings_contentgapanalytics_review',
            ),
            path(
                'review/<int:pk>/',
                self.admin_site.admin_view(self._review_detail_view),
                name='seo_settings_contentgapanalytics_review_detail',
            ),
            path(
                'review/<int:pk>/approve/',
                self.admin_site.admin_view(self._review_approve_view),
                name='seo_settings_contentgapanalytics_review_approve',
            ),
            path(
                'review/<int:pk>/dismiss/',
                self.admin_site.admin_view(self._review_dismiss_view),
                name='seo_settings_contentgapanalytics_review_dismiss',
            ),
            path(
                'review/export-csv/',
                self.admin_site.admin_view(self._review_export_view),
                name='seo_settings_contentgapanalytics_review_export',
            ),
        ] + super().get_urls()

    def _dashboard_view(self, request):
        from seo_settings.admin_views.analytics import render_content_gaps
        return render_content_gaps(request, self.admin_site)

    def _export_csv(self, request):
        from seo_settings.admin_views.analytics import export_content_gaps_csv
        return export_content_gaps_csv(request, self.admin_site)

    def _review_view(self, request):
        from seo_settings.admin_views.gap_review import render_gap_review
        return render_gap_review(request, self.admin_site)

    def _review_detail_view(self, request, pk):
        from seo_settings.admin_views.gap_review import render_gap_detail
        return render_gap_detail(request, pk, self.admin_site)

    def _review_approve_view(self, request, pk):
        from seo_settings.admin_views.gap_review import gap_approve_view
        return gap_approve_view(request, pk)

    def _review_dismiss_view(self, request, pk):
        from seo_settings.admin_views.gap_review import gap_dismiss_view
        return gap_dismiss_view(request, pk)

    def _review_export_view(self, request):
        from seo_settings.admin_views.gap_review import export_gap_review_csv
        return export_gap_review_csv(request, self.admin_site)

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin:seo_settings_contentgapanalytics_dashboard'))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True

