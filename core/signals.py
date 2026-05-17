"""
Post-save signals that ping Google whenever sitemap-relevant content changes.
Fires for: Service, GeoLocation, GeoState, GeoRegion, and TherapistProfile.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.lcpsych.com/sitemap.xml"


def _ping():
    try:
        from django.contrib.sitemaps import ping_google
        ping_google(SITEMAP_URL)
    except Exception as exc:
        # Never let a ping failure break a save
        logger.warning("ping_google failed: %s", exc)


@receiver(post_save, sender="core.Service")
def ping_on_service_save(sender, instance, created, **kwargs):
    if created:
        _ping()


@receiver(post_save, sender="geo.GeoLocation")
def ping_on_location_save(sender, instance, created, **kwargs):
    if created:
        _ping()


@receiver(post_save, sender="geo.GeoState")
def ping_on_state_save(sender, instance, created, **kwargs):
    if created:
        _ping()


@receiver(post_save, sender="geo.GeoRegion")
def ping_on_region_save(sender, instance, created, **kwargs):
    if created:
        _ping()


@receiver(post_save, sender="profiles.TherapistProfile")
def ping_on_therapist_save(sender, instance, created, **kwargs):
    if created:
        _ping()
