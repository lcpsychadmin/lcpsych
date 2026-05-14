import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def log_search(request):
    """Record an internal site search term to InternalSearchQuery."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "error", "detail": "invalid json"}, status=400)

    term = (data.get("term") or "").strip()[:500]
    if not term:
        return JsonResponse({"status": "error", "detail": "term required"}, status=400)

    try:
        from seo_intel.models import InternalSearchQuery
        InternalSearchQuery.objects.create(
            term=term,
            timestamp=timezone.now(),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            session_key=request.session.session_key or None,
        )
    except Exception:
        pass  # Never let logging break the page

    return JsonResponse({"status": "ok"})
