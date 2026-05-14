"""
core/utils/gsc_utils.py
-----------------------
Helpers for querying the Google Search Console Search Analytics API.

Supports two auth methods (tried in order):
1. OAuth2 refresh token (preferred — works with a real Google account that has
   Search Console access):
     GSC_OAUTH_CLIENT_ID
     GSC_OAUTH_CLIENT_SECRET
     GSC_OAUTH_REFRESH_TOKEN

2. Service account (fallback — requires the SA to be granted GSC property access,
   which the UI currently doesn't support for SA emails):
     GOOGLE_CLIENT_EMAIL
     GOOGLE_PRIVATE_KEY

Both also require:
     GSC_SITE_URL  (e.g. https://www.lcpsych.com)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_SEARCH_ANALYTICS_ENDPOINT = (
    "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)


def _get_access_token() -> str:
    """Return a short-lived access token using whichever credentials are available."""
    # --- Method 1: OAuth2 refresh token (preferred) ---
    client_id = os.environ.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GSC_OAUTH_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GSC_OAUTH_REFRESH_TOKEN", "")
    if client_id and client_secret and refresh_token:
        body = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"OAuth2 token exchange failed: {data}")
        return token

    # --- Method 2: Service account ---
    from google.oauth2 import service_account  # type: ignore
    import google.auth.transport.requests as google_requests  # type: ignore

    private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
    client_email = os.environ.get("GOOGLE_CLIENT_EMAIL", "")
    if not private_key or not client_email:
        raise RuntimeError(
            "No GSC credentials configured. Set GSC_OAUTH_CLIENT_ID / "
            "GSC_OAUTH_CLIENT_SECRET / GSC_OAUTH_REFRESH_TOKEN, or "
            "GOOGLE_CLIENT_EMAIL / GOOGLE_PRIVATE_KEY."
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
    credentials.refresh(google_requests.Request())
    return credentials.token  # type: ignore[return-value]


def fetch_top_queries(
    start_date: date,
    end_date: date,
    row_limit: int = 25,
) -> list[dict]:
    """Return top organic search queries for the given date range.

    Each dict has keys: query, clicks, impressions, ctr, position.
    Returns an empty list if credentials are missing or the API call fails.
    GSC data typically lags ~2–3 days behind the current date.
    """
    site_url = os.environ.get("GSC_SITE_URL", "")
    if not site_url:
        return []

    try:
        access_token = _get_access_token()
    except Exception as exc:
        logger.error("GSC: failed to obtain access token: %s", exc)
        return []

    encoded_site = urllib.parse.quote(site_url, safe="")
    endpoint = _SEARCH_ANALYTICS_ENDPOINT.format(site=encoded_site)

    body = json.dumps(
        {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "rowLimit": row_limit,
            "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("GSC: HTTP %s from Search Analytics API: %s", exc.code, body)
        return []
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.error("GSC: request error: %s", exc)
        return []

    rows = data.get("rows") or []
    results = []
    for row in rows:
        keys = row.get("keys", [])
        results.append(
            {
                "query": keys[0] if keys else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round((row.get("ctr") or 0) * 100, 1),
                "position": round(row.get("position") or 0, 1),
            }
        )
    return results
