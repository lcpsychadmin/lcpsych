"""
lcpsych/celery.py
-----------------
Celery application instance for the LCPsych project.

This module is imported by lcpsych/__init__.py so Django's app registry
is ready before any tasks are discovered.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lcpsych.settings")

app = Celery("lcpsych")

# Pull all CELERY_* settings from Django settings (namespace="CELERY").
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in any installed app's tasks.py.
app.autodiscover_tasks()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register the beat schedule after all apps are loaded."""
    from seo_intel.tasks import BEAT_SCHEDULE  # noqa: PLC0415

    sender.conf.beat_schedule.update(BEAT_SCHEDULE)
