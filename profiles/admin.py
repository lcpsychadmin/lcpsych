from django.contrib import admin

from .models import ClientFocus, LicenseType, TherapistProfile


@admin.register(TherapistProfile)
class TherapistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "license_type",
        "accepts_new_clients",
        "is_published",
    )
    list_filter = ("accepts_new_clients", "is_published")
    search_fields = ("first_name", "last_name", "user__email", "user__username")
    readonly_fields = ("slug", "created_at", "updated_at")
    filter_horizontal = ("client_focuses", "services")


@admin.register(LicenseType)
class LicenseTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(ClientFocus)
class ClientFocusAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")
