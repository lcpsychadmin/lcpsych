"""
seo_intel/views/add_seed.py
-----------------------------
POST-only endpoint: promote a discovered keyword to a KeywordSeed record.

On success returns JSON {status, keyword, created} and invalidates the
discovery cache so the next page load shows fresh results.
"""
from __future__ import annotations

import json
import logging
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"service", "testing", "modality", "location"}


def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Login required"}, status=401)
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@_staff_required
def add_seed(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode() or "{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    keyword  = (body.get("keyword") or "").strip()
    category = (body.get("category") or "service").strip()

    if not keyword:
        return JsonResponse({"status": "error", "message": "keyword is required"}, status=400)
    if category not in VALID_CATEGORIES:
        category = "service"

    from seo_settings.models import KeywordSeed
    _, created = KeywordSeed.objects.get_or_create(
        keyword=keyword,
        defaults={"category": category, "active": True},
    )

    # Invalidate discovery cache so the next load reflects the new seed
    try:
        from seo_intel.services.keyword_discovery import invalidate_cache
        invalidate_cache()
    except Exception:
        logger.warning("add_seed: could not invalidate discovery cache")

    logger.info("add_seed: %r (created=%s)", keyword, created)
    return JsonResponse({
        "status":  "created" if created else "exists",
        "keyword": keyword,
        "created": created,
    })
