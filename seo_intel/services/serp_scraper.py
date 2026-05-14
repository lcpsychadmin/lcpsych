"""
seo_intel/services/serp_scraper.py
------------------------------------
Query the **Google Custom Search JSON API** to capture top-10 organic results
for a keyword and store them in CompetitorSERPResult.

Why the Custom Search API instead of scraping google.com?
  - Direct HTML scraping of google.com violates Google's ToS and is
    immediately blocked by CAPTCHAs in automated contexts.
  - The Custom Search JSON API is the Google-approved programmatic search
    interface. Results are structured JSON — no HTML parsing required for
    the URLs/titles, though BeautifulSoup is still used to strip the <b>
    highlight tags Google includes in snippet text.

Setup (one-time)
----------------
1. In Google Cloud Console (project: lc-psychological-services):
   Enable "Custom Search API":
     APIs & Services → Library → search "Custom Search API" → Enable

2. Create an API key (if you don't already have one):
     APIs & Services → Credentials → Create credentials → API key
   Restrict it to the Custom Search API for safety.

3. Create a Programmable Search Engine configured to search the entire web:
     https://programmablesearchengine.google.com/
   - Click "Add" → give it any name
   - Under "Sites to search" choose "Search the entire web"
   - Copy the Search engine ID (cx value)

4. Set env vars (Heroku):
     heroku config:set GOOGLE_CSE_API_KEY=<your-api-key> --app lcpsych-prod
     heroku config:set GOOGLE_CSE_ID=<your-cx-id>       --app lcpsych-prod

Free tier: 100 queries/day. Paid: $5 per 1,000 additional queries.

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
from bs4 import BeautifulSoup

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

_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def _get_credentials() -> tuple[str, str]:
    """Return (api_key, cx_id) or raise RuntimeError if not configured."""
    api_key = os.environ.get("GOOGLE_CSE_API_KEY", "")
    cx_id = os.environ.get("GOOGLE_CSE_ID", "")
    if not api_key or not cx_id:
        raise RuntimeError(
            "Google Custom Search credentials not configured.\n"
            "Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID environment variables.\n"
            "See module docstring for setup instructions."
        )
    return api_key, cx_id


def _strip_html(text: str) -> str:
    """Remove HTML tags (e.g. <b> highlights) from a snippet string."""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


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
    Fetch up to `num_results` organic results for `keyword` from the
    Google Custom Search JSON API.

    The API returns at most 10 results per request. If num_results > 10
    a second request is made (uses an additional daily quota unit).

    Parameters
    ----------
    keyword:
        The search query string.
    num_results:
        How many results to return (default 10, max capped at 20).
    request_timeout:
        HTTP timeout in seconds.

    Returns
    -------
    List of SerpRow objects ordered by rank (1-based).

    Raises
    ------
    RuntimeError  — credentials not configured
    requests.HTTPError — API returned a non-2xx status
    """
    api_key, cx_id = _get_credentials()
    num_results = min(num_results, 20)  # API supports start=1..91, keep simple

    rows: list[SerpRow] = []
    start_index = 1  # 1-based, max 10 per page

    while len(rows) < num_results:
        batch_size = min(10, num_results - len(rows))
        params = {
            "key": api_key,
            "cx": cx_id,
            "q": keyword,
            "num": batch_size,
            "start": start_index,
            "safe": "active",
        }
        resp = requests.get(_CSE_ENDPOINT, params=params, timeout=request_timeout)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items") or []
        if not items:
            break  # fewer results than requested (e.g. niche keyword)

        for item in items:
            raw_snippet = item.get("snippet", "")
            rows.append(
                SerpRow(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    description=_strip_html(raw_snippet),
                    rank=len(rows) + 1,
                )
            )

        start_index += len(items)
        if len(items) < batch_size:
            break  # API returned fewer than asked; no more pages

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
