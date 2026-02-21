from urllib.parse import urlparse
from django.conf import settings
from django.http import HttpResponsePermanentRedirect


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
