"""
Management command: pull_search_console
----------------------------------------
Fetches Search Console Search Analytics data for the last N days (default 7)
and stores the results in SearchConsoleQuery, deduplicating on (query, page, date).

Usage
-----
    python manage.py pull_search_console
    python manage.py pull_search_console --days 28
    python manage.py pull_search_console --days 7 --row-limit 1000

Auth
----
Uses the same credential chain as core.utils.gsc_utils:
  1. OAuth2 refresh token (GSC_OAUTH_CLIENT_ID / GSC_OAUTH_CLIENT_SECRET / GSC_OAUTH_REFRESH_TOKEN)
  2. Service account (GOOGLE_CLIENT_EMAIL / GOOGLE_PRIVATE_KEY)

Both methods also require GSC_SITE_URL (e.g. https://www.lcpsych.com).

Scheduling
----------
Heroku Scheduler (simplest):
    heroku addons:create scheduler:standard --app lcpsych-prod
    # In the Scheduler dashboard add a job:
    python manage.py pull_search_console --days 7
    # Run: Every day at 04:00 UTC (GSC data lags ~2-3 days, so daily is fine)

Heroku + Celery Beat (if Celery is already wired up):
    # In your Celery app config / beat schedule:
    #
    #   CELERY_BEAT_SCHEDULE = {
    #       "pull-search-console-daily": {
    #           "task": "seo_intel.tasks.pull_search_console_task",
    #           "schedule": crontab(hour=4, minute=0),
    #       },
    #   }
    #
    # Then create seo_intel/tasks.py:
    #
    #   from celery import shared_task
    #   from django.core.management import call_command
    #
    #   @shared_task
    #   def pull_search_console_task():
    #       call_command("pull_search_console", days=7)

cron (non-Heroku / local):
    0 4 * * * /path/to/.venv/bin/python /path/to/manage.py pull_search_console --days 7
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_SEARCH_ANALYTICS_URL = (
    "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)


def _get_access_token() -> str:
    """Return a short-lived access token; prefers OAuth2, falls back to service account."""
    client_id = os.environ.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GSC_OAUTH_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GSC_OAUTH_REFRESH_TOKEN", "")

    if client_id and client_secret and refresh_token:
        body = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"OAuth2 token exchange failed: {data}")
        return token

    # Service account fallback
    from google.oauth2 import service_account  # type: ignore
    import google.auth.transport.requests as google_requests  # type: ignore

    private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
    client_email = os.environ.get("GOOGLE_CLIENT_EMAIL", "")
    if not private_key or not client_email:
        raise RuntimeError(
            "No GSC credentials found. Set GSC_OAUTH_CLIENT_ID / "
            "GSC_OAUTH_CLIENT_SECRET / GSC_OAUTH_REFRESH_TOKEN  or  "
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


def _fetch_rows(
    access_token: str,
    site_url: str,
    start: date,
    end: date,
    row_limit: int,
) -> list[dict]:
    """
    Call the Search Analytics API with dimensions=[query, page] and return
    the raw rows list.  Raises on HTTP errors.
    """
    encoded_site = urllib.parse.quote(site_url, safe="")
    endpoint = _SEARCH_ANALYTICS_URL.format(site=encoded_site)

    payload = json.dumps(
        {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["date", "query", "page"],
            "rowLimit": row_limit,
            "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GSC API returned HTTP {exc.code}: {detail}"
        ) from exc

    return data.get("rows") or []


class Command(BaseCommand):
    help = "Pull Search Console search analytics and store in SearchConsoleQuery."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to look back (default: 7). "
                 "GSC data typically lags 2–3 days.",
        )
        parser.add_argument(
            "--row-limit",
            type=int,
            default=1000,
            help="Maximum rows to request from GSC per call (default: 1000, max: 25000).",
        )

    def handle(self, *args, **options):
        from seo_intel.models import SearchConsoleQuery

        site_url = os.environ.get("GSC_SITE_URL", "").rstrip("/")
        if not site_url:
            raise CommandError("GSC_SITE_URL environment variable is not set.")

        days: int = options["days"]
        row_limit: int = min(options["row_limit"], 25000)

        # GSC lags ~2 days; end yesterday to avoid incomplete data.
        end_date = date.today() - timedelta(days=2)
        start_date = end_date - timedelta(days=days - 1)

        self.stdout.write(
            f"Fetching GSC data for {site_url}  "
            f"{start_date} → {end_date}  (row_limit={row_limit}) …"
        )

        try:
            access_token = _get_access_token()
        except Exception as exc:
            raise CommandError(f"Auth failed: {exc}") from exc

        try:
            rows = _fetch_rows(access_token, site_url, start_date, end_date, row_limit)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"  Received {len(rows)} rows from API.")

        created = 0
        updated = 0

        for row in rows:
            keys = row.get("keys", [])
            if len(keys) < 3:
                continue

            # dimensions order: date, query, page
            try:
                row_date = date.fromisoformat(keys[0])
            except ValueError:
                continue
            query_str = keys[1]
            page_url = keys[2]

            _, was_created = SearchConsoleQuery.objects.update_or_create(
                query=query_str,
                page=page_url,
                date=row_date,
                defaults={
                    "clicks": int(row.get("clicks") or 0),
                    "impressions": int(row.get("impressions") or 0),
                    "ctr": float(row.get("ctr") or 0.0),
                    "position": float(row.get("position") or 0.0),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}  Updated: {updated}  "
                f"Total stored: {created + updated}"
            )
        )
