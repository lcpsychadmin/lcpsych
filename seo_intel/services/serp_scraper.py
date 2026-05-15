"""
seo_intel/services/serp_scraper.py
------------------------------------
Query the **SerpApi** to capture top-10 organic Google results for a keyword
and store them in CompetitorSERPResult.

Why SerpApi instead of scraping google.com directly?
  - Direct HTML scraping of google.com violates Google's ToS and is
    immediately blocked by CAPTCHAs in automated contexts.
  - SerpApi is a paid proxy service that returns structured JSON results
    from a real Google SERP — no HTML parsing required.

Setup (one-time)
----------------
1. Sign up at https://serpapi.com/ (100 free searches/month on the free plan).

2. Copy your API key from the dashboard.

3. Set env var (Heroku):
     heroku config:set SERPAPI_KEY=<your-api-key> --app lcpsych-prod

Free tier: 100 searches/month. Paid plans start at ~$50/month for 5,000.

Public API:
-----------
    scrape_keyword(keyword)          -> list[SerpRow]
    save_serp_results(keyword, rows) -> tuple[int, int]  # (created, updated)
"""

from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------

class SerpRow:
    """A single SERP result row."""

    __slots__ = ("url", "title", "description", "rank")

    def __init__(self, url: str, title: str, description: str, rank: int) -> None:
        self.url = url
        self.title = title[:500]
        self.description = description
        self.rank = rank

    def __repr__(self) -> str:
        return f"SerpRow(rank={self.rank}, url={self.url!r})"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_SERPAPI_ENDPOINT = "https://serpapi.com/search"


def _get_api_key() -> str:
    """Return the SerpApi key or raise RuntimeError if not configured."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SerpApi key not configured.\n"
            "Set SERPAPI_KEY environment variable.\n"
            "Sign up at https://serpapi.com/ (100 free searches/month)."
        )
    return api_key


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def scrape_keyword(
    keyword: str,
    num_results: int = 10,
    *,
    request_timeout: int = 15,
) -> list[SerpRow]:
    """
    Fetch up to `num_results` organic results for `keyword` via SerpApi.

    Parameters
    ----------
    keyword:
        The search query string.
    num_results:
        How many results to return (default 10, max capped at 10).
    request_timeout:
        HTTP timeout in seconds.

    Returns
    -------
    List of SerpRow objects ordered by rank (1-based).

    Raises
    ------
    RuntimeError  — SERPAPI_KEY not configured
    requests.HTTPError — API returned a non-2xx status
    """
    api_key = _get_api_key()
    num_results = min(num_results, 10)

    params = {
        "api_key": api_key,
        "engine": "google",
        "q": keyword,
        "num": num_results,
        "safe": "active",
        "output": "json",
    }
    resp = requests.get(_SERPAPI_ENDPOINT, params=params, timeout=request_timeout)
    resp.raise_for_status()
    data = resp.json()

    rows: list[SerpRow] = []
    for item in data.get("organic_results", []):
        rows.append(
            SerpRow(
                url=item.get("link", ""),
                title=item.get("title", ""),
                description=item.get("snippet", ""),
                rank=item.get("position", len(rows) + 1),
            )
        )

    return rows


def save_serp_results(
    keyword: str,
    rows: list[SerpRow],
) -> tuple[int, int]:
    """
    Persist SERP rows to the database.

    Deduplication strategy: one record per (keyword, competitor_url) per
    calendar day — if a record already exists for today it is updated in
    place; otherwise a new record is created.  This preserves history
    across days while preventing duplicate rows from repeated same-day runs.

    Returns
    -------
    (created, updated) counts.
    """
    from django.utils import timezone
    from seo_intel.models import CompetitorSERPResult

    now = timezone.now()
    today = now.date()
    created_count = 0
    updated_count = 0

    for row in rows:
        if not row.url:
            continue

        existing = (
            CompetitorSERPResult.objects
            .filter(keyword=keyword, competitor_url=row.url)
            .filter(timestamp__date=today)
            .first()
        )
        if existing:
            existing.title = row.title
            existing.description = row.description
            existing.rank = row.rank
            existing.timestamp = now
            existing.save(update_fields=["title", "description", "rank", "timestamp"])
            updated_count += 1
        else:
            CompetitorSERPResult.objects.create(
                keyword=keyword,
                competitor_url=row.url,
                title=row.title,
                description=row.description,
                rank=row.rank,
                timestamp=now,
            )
            created_count += 1

    return created_count, updated_count


def scrape_and_save(
    keyword: str,
    num_results: int = 10,
) -> tuple[int, int]:
    """Convenience wrapper: scrape a keyword then save results. Returns (created, updated)."""
    rows = scrape_keyword(keyword, num_results=num_results)
    return save_serp_results(keyword, rows)
