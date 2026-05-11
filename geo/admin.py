from django.contrib import admin

from .models import GeoContentBlock, GeoLocation, GeoRegion, GeoState


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class ContentBlockStateInline(admin.TabularInline):
    model = GeoContentBlock
    fk_name = "state"
    extra = 1
    fields = ["order", "heading", "body"]
    verbose_name = "Content Block"
    verbose_name_plural = "Content Blocks"


class ContentBlockLocationInline(admin.TabularInline):
    model = GeoContentBlock
    fk_name = "location"
    extra = 1
    fields = ["order", "heading", "body"]
    verbose_name = "Content Block"
    verbose_name_plural = "Content Blocks"


class LocationInline(admin.TabularInline):
    model = GeoLocation
    extra = 0
    fields = ["name", "slug", "location_type", "is_active"]
    show_change_link = True
    verbose_name = "Location"
    verbose_name_plural = "Cities & Counties"


# ---------------------------------------------------------------------------
# State admin
# ---------------------------------------------------------------------------


@admin.register(GeoState)
class GeoStateAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation", "slug", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = [
        (
            None,
            {"fields": ["name", "abbreviation", "slug", "is_active"]},
        ),
        (
            "SEO & Page Content",
            {
                "fields": [
                    "seo_title",
                    "seo_description",
                    "hero_heading",
                    "hero_subheading",
                    "og_image_url",
                ],
                "description": (
                    "Leave SEO fields blank to use auto-generated defaults. "
                    "Add content blocks below to populate the page body."
                ),
            },
        ),
    ]
    inlines = [ContentBlockStateInline, LocationInline]


# ---------------------------------------------------------------------------
# Location admin
# ---------------------------------------------------------------------------


@admin.register(GeoLocation)
class GeoLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "location_type", "slug", "is_active"]
    list_filter = ["state", "location_type", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = [
        (
            None,
            {"fields": ["state", "name", "slug", "location_type", "is_active"]},
        ),
        (
            "SEO & Page Content",
            {
                "fields": [
                    "seo_title",
                    "seo_description",
                    "hero_heading",
                    "hero_subheading",
                    "og_image_url",
                ],
                "description": (
                    "Leave SEO fields blank to use auto-generated defaults. "
                    "Add content blocks below to populate the page body."
                ),
            },
        ),
    ]
    inlines = [ContentBlockLocationInline]


# ---------------------------------------------------------------------------
# Region admin
# ---------------------------------------------------------------------------


@admin.register(GeoRegion)
class GeoRegionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["states", "locations", "offices"]
    fieldsets = [
        (
            None,
            {"fields": ["name", "slug", "is_active"]},
        ),
        (
            "Members",
            {
                "fields": ["states", "locations"],
                "description": (
                    "Add states and/or individual cities/counties to this region. "
                    "Therapists and services are derived from the union of all members."
                ),
            },
        ),
        (
            "SEO & Page Content",
            {
                "fields": [
                    "seo_title",
                    "seo_description",
                    "og_image_url",
                    "hero_image",
                ],
                "description": "Leave SEO fields blank to use auto-generated defaults.",
            },
        ),
    ]
