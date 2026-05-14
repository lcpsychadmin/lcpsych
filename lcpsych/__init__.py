# Make the Celery app available as soon as Django is initialised so that
# @shared_task and periodic tasks work correctly.
from .celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)
