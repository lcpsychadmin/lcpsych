from urllib.parse import urlparse
from django.conf import settings
from django.http import HttpResponse, HttpResponsePermanentRedirect


class CanonicalDomainMiddleware:
    """
    Enforces a single canonical host based on settings.BASE_URL by issuing 301 redirects
    when the request host differs. Protocol redirection is handled by SECURE_SSL_REDIRECT.
    Skips in DEBUG or when BASE_URL is not configured.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        base = (getattr(settings, 'BASE_URL', '') or '').strip()
        self._parsed = urlparse(base) if base else None
        self._canonical_host = self._parsed.netloc if self._parsed else None

    def __call__(self, request):
        # Only enforce in non-debug and when BASE_URL is configured
        if not settings.DEBUG and self._canonical_host:
            # Avoid host redirects on Azure SSO endpoints to prevent auth loops
            if request.path.startswith('/accounts/azure/'):
                return self.get_response(request)
            req_host = request.get_host()
            # Allow Heroku preview/app host access without redirect for testing
            if req_host.endswith('.herokuapp.com'):
                return self.get_response(request)
            if req_host and req_host != self._canonical_host:
                # Build absolute URL to canonical host, preserving path and query
                scheme = 'https' if (self._parsed and self._parsed.scheme == 'https') else 'http'
                redirect_to = f"{scheme}://{self._canonical_host}{request.get_full_path()}"
                return HttpResponsePermanentRedirect(redirect_to)

        return self.get_response(request)


class GeoSlug410Middleware:
    """
    Converts Http404 exceptions raised by geo and therapist profile views into
    HTTP 410 Gone responses.

    URL prefixes that trigger 410 conversion:
      - /regions/     – region hub and intersectional pages
      - /therapists/  – therapist profile & area pages

    For state-rooted pages (/<state>/...) the StateSlugConverter guarantees the
    first segment is a valid state, so any Http404 raised inside those views is
    always a subsequent invalid slug — we convert those by checking the resolved
    URL app_name.

    Installation — add AFTER CanonicalDomainMiddleware in settings.MIDDLEWARE::

        'core.middleware.GeoSlug410Middleware',
    """

    _GEO_PREFIXES = ("/regions/", "/therapists/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.http import Http404
        if not isinstance(exception, Http404):
            return None

        path = request.path_info

        # Explicit geo-prefixed namespaces
        if path.startswith(self._GEO_PREFIXES):
            return HttpResponse("Gone", status=410)

        # State-rooted paths: resolve to check the URL namespace
        from django.urls import resolve, Resolver404
        try:
            match = resolve(path)
        except Resolver404:
            return None  # Pattern didn't match at all — true 404

        if getattr(match, 'app_name', None) == 'geo':
            return HttpResponse("Gone", status=410)

        return None  # All other Http404s remain standard 404s
