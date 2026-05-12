"""
core/views_url_removal.py
--------------------------
POST /api/url-removal/

Accepts a JSON body with a list of URLs and submits each one to the
Google Search Console URL Removals API as a TEMPORARY_HIDE request.

Required environment variables
--------------------------------
URL_REMOVAL_TOKEN   – Secret token that must be sent in the X-Removal-Token header.
GOOGLE_CLIENT_EMAIL – Service-account email with Search Console access.
GOOGLE_PRIVATE_KEY  – RSA private key for the service account (newlines as \\n).
GSC_SITE_URL        – The site URL registered in Search Console, e.g. https://www.lcpsych.com

Optional
--------
GOOGLE_PROJECT_ID   – Not used at runtime but good to document alongside the other vars.

Security notes
--------------
- Only staff-level secret token auth is applied here (X-Removal-Token header).
- This endpoint should NOT be exposed without authentication.
- CSRF is exempt because it is an API endpoint called by scripts, not browsers.
"""

from __future__ import annotations

import json
import os
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


# ---------------------------------------------------------------------------
# Helper: Google Search Console URL Removals API
# ---------------------------------------------------------------------------

_GSC_REMOVALS_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlRemovals"
_SCOPE = "https://www.googleapis.com/auth/webmasters"


def _get_access_token() -> str:
    """
    Obtain a short-lived OAuth2 access token for the Search Console API
    using service-account credentials from environment variables.

    Requires: google-auth (pip install google-auth)
    """
    try:
        from google.oauth2 import service_account  # type: ignore
        import google.auth.transport.requests as google_requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-auth is not installed.  Add 'google-auth' to requirements.txt."
        ) from exc

    private_key: str = os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
    client_email: str = os.environ.get("GOOGLE_CLIENT_EMAIL", "")
    if not private_key or not client_email:
        raise RuntimeError(
            "GOOGLE_CLIENT_EMAIL and GOOGLE_PRIVATE_KEY environment variables must be set."
        )

    credentials = service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=[_SCOPE],
    )
    # Refresh to get an access token
    credentials.refresh(google_requests.Request())
    return credentials.token  # type: ignore[return-value]


def _submit_url_removal(access_token: str, site_url: str, url: str) -> dict[str, Any]:
    """
    Call the GSC URL Removals API for a single URL.
    Returns a dict with 'url', 'success', and optionally 'error'.
    """
    import urllib.request
    import urllib.error

    payload = json.dumps(
        {
            "siteUrl": site_url,
            "url": url,
            "removalType": "TEMPORARY_HIDE",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        _GSC_REMOVALS_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            return {"url": url, "success": True, "response": body}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else str(exc)
        return {"url": url, "success": False, "error": f"HTTP {exc.code}: {error_body}"}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def url_removal(request: HttpRequest) -> JsonResponse:
    """
    POST /api/url-removal/

    Request headers:
        X-Removal-Token: <URL_REMOVAL_TOKEN env var>
        Content-Type: application/json

    Request body:
        { "urls": ["https://www.lcpsych.com/old-url-1", ...] }

    Response (200):
        {
            "submitted": 2,
            "results": [
                {"url": "...", "success": true, "response": {...}},
                {"url": "...", "success": false, "error": "..."}
            ]
        }
    """
    # ── 1. Token authentication ──────────────────────────────────────────────
    expected_token: str = os.environ.get("URL_REMOVAL_TOKEN", "")
    if not expected_token:
        return JsonResponse(
            {"error": "URL_REMOVAL_TOKEN is not configured on this server."},
            status=500,
        )
    provided_token = request.headers.get("X-Removal-Token", "")
    if not provided_token or provided_token != expected_token:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # ── 2. Parse and validate body ───────────────────────────────────────────
    try:
        body: dict[str, Any] = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    urls = body.get("urls")
    if not isinstance(urls, list) or not urls:
        return JsonResponse({"error": "'urls' must be a non-empty list of strings."}, status=400)
    if not all(isinstance(u, str) for u in urls):
        return JsonResponse({"error": "All items in 'urls' must be strings."}, status=400)

    # ── 3. Validate GSC site URL ─────────────────────────────────────────────
    site_url: str = os.environ.get("GSC_SITE_URL", "").rstrip("/")
    if not site_url:
        return JsonResponse({"error": "GSC_SITE_URL is not configured on this server."}, status=500)

    # ── 4. Obtain access token ───────────────────────────────────────────────
    try:
        access_token = _get_access_token()
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    # ── 5. Submit each URL ───────────────────────────────────────────────────
    results: list[dict[str, Any]] = []
    for url in urls:
        results.append(_submit_url_removal(access_token, site_url, url))

    successes = sum(1 for r in results if r["success"])
    failures = len(results) - successes

    return JsonResponse(
        {
            "submitted": len(urls),
            "successes": successes,
            "failures": failures,
            "results": results,
        }
    )
