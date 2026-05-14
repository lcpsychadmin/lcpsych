from django.utils import timezone


class DeadURLLoggingMiddleware:
    """Log 404 and 410 responses to DeadURLHit for dead-link analysis."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in (404, 410):
            try:
                from .models import DeadURLHit
                DeadURLHit.objects.create(
                    url=request.path,
                    referrer=request.META.get("HTTP_REFERER") or None,
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    timestamp=timezone.now(),
                )
            except Exception:
                pass  # Never let logging break a real response
        return response
