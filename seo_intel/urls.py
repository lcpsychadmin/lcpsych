from django.urls import path
from .views.log_search import log_search

urlpatterns = [
    path("api/log-search/", log_search, name="seo_intel_log_search"),
]
