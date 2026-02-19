from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "profiles"
    verbose_name = "Therapist Profiles"

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401