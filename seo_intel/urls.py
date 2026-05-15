from django.urls import path
from .views.log_search import log_search
from . import api

urlpatterns = [
    path("api/log-search/", log_search, name="seo_intel_log_search"),

    # ── JSON data API ────────────────────────────────────────────────────
    # Powers Analytics Hub, SERP Explorer, and Keyword Universe.
    # All endpoints require authenticated staff; GET only.
    path("api/seo/keyword-scores/", api.keyword_scores, name="api_keyword_scores"),
    path("api/seo/competitor-hits/", api.competitor_hits, name="api_competitor_hits"),
    path("api/seo/lc-hits/", api.lc_hits, name="api_lc_hits"),
    path("api/seo/content-gaps/", api.content_gaps, name="api_content_gaps"),
    path("api/seo/search-console/", api.search_console, name="api_search_console"),
    path("api/seo/internal-search/", api.internal_search, name="api_internal_search"),
    path("api/seo/dead-urls/", api.dead_urls, name="api_dead_urls"),
]
