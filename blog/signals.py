"""
Blog signals.

When a Post transitions to STATUS_PUBLISHED, auto-post it to all configured
social platforms that have auto_post_on_publish=True.

pre_save captures the previous status so post_save can detect the transition.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Post

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Post)
def _capture_prev_status(sender, instance: Post, **kwargs):
    """Store the pre-save status on the instance so post_save can compare."""
    if instance.pk:
        try:
            instance._prev_status = Post.objects.only("status").get(pk=instance.pk).status
        except Post.DoesNotExist:
            instance._prev_status = None
    else:
        instance._prev_status = None


@receiver(post_save, sender=Post)
def auto_post_on_publish(sender, instance: Post, created: bool, **kwargs):
    """Fire social posts when a post first becomes published."""
    if instance.status != Post.STATUS_PUBLISHED:
        return

    prev = getattr(instance, "_prev_status", None)
    # Skip if the post was already published before this save.
    if prev == Post.STATUS_PUBLISHED:
        return

    from core.utils.social_posting import post_to_all_platforms

    try:
        results = post_to_all_platforms(instance)
        for platform_name, ok, msg in results:
            if ok:
                logger.info("Auto-posted '%s' to %s: %s", instance.title, platform_name, msg)
            else:
                logger.warning("Failed to auto-post '%s' to %s: %s", instance.title, platform_name, msg)
    except Exception:
        logger.exception("Unexpected error during auto_post_on_publish for Post pk=%s", instance.pk)
