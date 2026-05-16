"""
seo_settings/portal_urls.py
-----------------------------
URL configuration for the SEO Intelligence custom portal.
Include via: path('seo/', include('seo_settings.portal_urls', namespace='seo_intel'))
"""
from django.urls import path

from seo_intel.views.actions import (
    run_serpapi,
    run_serpapi_for_discovered,
    run_serpapi_for_keyword,
    run_serpapi_selected,
    run_competitor_crawl,
    poll_job_status,
    score_keywords as score_keywords_action,
)
from seo_intel.views.add_seed import add_seed
from seo_intel.views.analytics_hub import analytics_hub
from seo_intel.views.content_gaps import content_gaps
from seo_intel.views.keyword_discovery import keyword_discovery
from seo_intel.views.keyword_seeds_intel import keyword_seeds_intel
from seo_intel.views.competitor_analysis import competitor_analysis
from seo_intel.views.keyword_universe import keyword_universe
from seo_intel.views.serp_explorer import serp_explorer
from seo_settings.views import actions, portal

app_name = 'seo_intel'

urlpatterns = [
    # Control panel & settings
    path('', portal.control_panel, name='control_panel'),
    path('settings/', portal.global_settings, name='settings'),

    # Competitor domains
    path('competitors/', portal.competitors, name='competitors'),
    path('competitors/<int:pk>/toggle/', portal.toggle_competitor, name='competitor_toggle'),
    path('competitors/<int:pk>/delete/', portal.delete_competitor, name='competitor_delete'),
    path('competitors/export.csv', portal.export_competitors_csv, name='competitors_export'),

    # Keyword seeds
    path('keywords/', portal.keywords, name='keywords'),
    path('keywords/ai-suggest/', portal.ai_suggest_keywords, name='keywords_ai_suggest'),
    path('keywords/bulk-add/', portal.bulk_add_keywords, name='keywords_bulk_add'),
    path('keywords/<int:pk>/toggle/', portal.toggle_keyword, name='keyword_toggle'),
    path('keywords/<int:pk>/delete/', portal.delete_keyword, name='keyword_delete'),
    path('keywords/export.csv', portal.export_keywords_csv, name='keywords_export'),

    # Keyword Seeds Intelligence
    path('keyword-seeds-intel/', keyword_seeds_intel, name='keyword_seeds_intel'),

    # Keyword Discovery Engine
    path('keyword-discovery/', keyword_discovery, name='keyword_discovery'),

    # Add Seed (POST — promotes a discovered keyword to KeywordSeed)
    path('add-seed/', add_seed, name='add_seed'),

    # Keyword Universe
    path('keyword-universe/', keyword_universe, name='keyword_universe'),

    # SERP Explorer
    path('serp-explorer/', serp_explorer, name='serp_explorer'),

    # Content Gaps (enhanced view)
    path('content-gaps/', content_gaps, name='content_gaps'),

    # Competitor Analysis Engine
    path('competitor-analysis/', competitor_analysis, name='competitor_analysis'),

    # Analytics Hub
    path('analytics-hub/', analytics_hub, name='analytics_hub'),

    # Analytics
    path('analytics/sc/', portal.analytics_sc, name='analytics_sc'),
    path('analytics/internal/', portal.analytics_internal, name='analytics_internal'),
    path('analytics/dead-urls/', portal.analytics_dead_urls, name='analytics_dead_urls'),
    path('analytics/gaps/', portal.analytics_gaps, name='analytics_gaps'),
    path('analytics/gaps/export.csv', portal.export_gaps_csv, name='gaps_export'),

    # Action endpoints (POST → JSON)
    path('actions/run-sc/', actions.run_search_console_pull, name='action_run_sc'),
    path('actions/run-scrape/', actions.run_competitor_scrape, name='action_run_scrape'),
    path('actions/run-gap/', actions.run_gap_analysis, name='action_run_gap'),
    path('actions/run-serpapi/', run_serpapi, name='action_run_serpapi'),
    path('actions/run-serpapi-keyword/', run_serpapi_for_keyword, name='action_run_serpapi_keyword'),
    path('actions/run-serpapi-discovered/', run_serpapi_for_discovered, name='action_run_serpapi_discovered'),
    path('actions/run-serpapi-selected/', run_serpapi_selected, name='action_run_serpapi_selected'),
    path('actions/score-keywords/', score_keywords_action, name='action_score_keywords'),
    path('actions/clear-dead/', actions.clear_dead_urls, name='action_clear_dead'),
    path('actions/clear-internal/', actions.clear_internal_search, name='action_clear_internal'),
    path('actions/clear-serps/', actions.clear_competitor_results, name='action_clear_serps'),
    path('actions/run-competitor-crawl/', run_competitor_crawl, name='action_run_competitor_crawl'),
    path('actions/job-status/<str:job_id>/', poll_job_status, name='action_poll_job'),
]
