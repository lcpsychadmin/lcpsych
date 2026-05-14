import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone

from .models import (
    CompetitorSERPResult,
    ContentGapRecord,
    DeadURLHit,
    InternalSearchQuery,
    SearchConsoleQuery,
)


# ---------------------------------------------------------------------------
# Shared CSV export helper
# ---------------------------------------------------------------------------

def _export_csv(modeladmin, request, queryset):
    """Generic CSV export action — works on any queryset."""
    meta = modeladmin.model._meta
    field_names = [f.name for f in meta.fields]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{meta.verbose_name_plural}_{timezone.now():%Y%m%d}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, f) for f in field_names])
    return response


_export_csv.short_description = "Export selected rows to CSV"


# ---------------------------------------------------------------------------
# SearchConsoleQuery
# ---------------------------------------------------------------------------

@admin.register(SearchConsoleQuery)
class SearchConsoleQueryAdmin(admin.ModelAdmin):
    list_display = ("query", "page", "date", "clicks", "impressions", "ctr_pct", "position")
    list_filter = ("date",)
    search_fields = ("query", "page")
    date_hierarchy = "date"
    ordering = ("-date", "-clicks")
    list_per_page = 50
    actions = [_export_csv]

    @admin.display(description="CTR %", ordering="ctr")
    def ctr_pct(self, obj):
        return f"{obj.ctr * 100:.1f}%"


# ---------------------------------------------------------------------------
# InternalSearchQuery
# ---------------------------------------------------------------------------

@admin.register(InternalSearchQuery)
class InternalSearchQueryAdmin(admin.ModelAdmin):
    list_display = ("term", "timestamp", "session_key", "user_agent_short")
    search_fields = ("term", "session_key")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 50
    actions = [_export_csv]

    @admin.display(description="User agent")
    def user_agent_short(self, obj):
        return (obj.user_agent or "")[:80]


# ---------------------------------------------------------------------------
# DeadURLHit
# ---------------------------------------------------------------------------

@admin.register(DeadURLHit)
class DeadURLHitAdmin(admin.ModelAdmin):
    list_display = ("url", "referrer_short", "timestamp", "user_agent_short")
    search_fields = ("url", "referrer", "user_agent")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 50
    actions = [_export_csv]

    @admin.display(description="Referrer")
    def referrer_short(self, obj):
        return (obj.referrer or "—")[:80]

    @admin.display(description="User agent")
    def user_agent_short(self, obj):
        return (obj.user_agent or "")[:60]


# ---------------------------------------------------------------------------
# CompetitorSERPResult
# ---------------------------------------------------------------------------

@admin.register(CompetitorSERPResult)
class CompetitorSERPResultAdmin(admin.ModelAdmin):
    list_display = ("rank", "keyword", "competitor_url", "title_short", "timestamp")
    list_filter = ("keyword", "rank")
    search_fields = ("keyword", "competitor_url", "title", "description")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp", "rank")
    list_per_page = 50
    actions = [_export_csv]

    @admin.display(description="Title")
    def title_short(self, obj):
        return (obj.title or "")[:80]


# ---------------------------------------------------------------------------
# ContentGapRecord
# ---------------------------------------------------------------------------

def _mark_resolved(modeladmin, request, queryset):
    updated = queryset.update(resolved=True)
    modeladmin.message_user(request, f"{updated} record(s) marked as resolved.")


_mark_resolved.short_description = "Mark selected gaps as resolved"


def _mark_unresolved(modeladmin, request, queryset):
    updated = queryset.update(resolved=False)
    modeladmin.message_user(request, f"{updated} record(s) marked as unresolved.")


_mark_unresolved.short_description = "Mark selected gaps as unresolved"


@admin.register(ContentGapRecord)
class ContentGapRecordAdmin(admin.ModelAdmin):
    list_display = (
        "keyword",
        "search_volume",
        "competitor_presence",
        "lcpsych_presence",
        "recommended_action",
        "resolved",
        "timestamp",
    )
    list_filter = (
        "resolved",
        "competitor_presence",
        "lcpsych_presence",
        "recommended_action",
    )
    search_fields = ("keyword", "recommended_action")
    date_hierarchy = "timestamp"
    ordering = ("resolved", "-search_volume")
    list_per_page = 50
    list_editable = ("resolved",)
    actions = [_mark_resolved, _mark_unresolved, _export_csv]
