"""
seo_intel/services/serpapi_client.py
--------------------------------------
SerpApi-based Google SERP fetcher for LC Psych.

Targeted at the Northern Kentucky / Greater Cincinnati region so that organic
results reflect what a local prospective client would see, not a generic
nationwide SERP.

Setup
-----
Set the SERPAPI_KEY environment variable (same key used by serp_scraper.py).
Sign up / manage your account at https://serpapi.com/.

Free tier: 100 searches / month.  Each call to fetch_serp() = 1 search credit.

Public API
----------
    fetch_serp(keyword)         -> dict          raw SerpApi JSON response
    parse_serp(keyword, serp)   -> dict          normalised result dict
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LOCATION = "Northern Kentucky, United States"
_GOOGLE_DOMAIN = "google.com"
_GL = "us"
_HL = "en"


def _get_api_key() -> str:
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "SERPAPI_KEY is not configured. "
            "Set it in your .env file (locally) or as a Heroku config var."
        )
    return key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_serp(keyword: str, *, timeout: int = 20) -> dict:
    """
    Query SerpApi for *keyword* and return the raw parsed JSON dict.

    Parameters
    ----------
    keyword:
        The search query to run.
    timeout:
        HTTP timeout in seconds (passed through to the underlying request).

    Returns
    -------
    Raw SerpApi response as a Python dict.

    Raises
    ------
    RuntimeError   — SERPAPI_KEY not set
    Exception      — any network / API error (logged before re-raising)
    """
    from serpapi import GoogleSearch  # google-search-results package

    api_key = _get_api_key()

    params = {
        "engine": "google",
        "q": keyword,
        "location": _LOCATION,
        "google_domain": _GOOGLE_DOMAIN,
        "gl": _GL,
        "hl": _HL,
        "api_key": api_key,
    }

    logger.debug("SerpApi fetch: %r (location=%s)", keyword, _LOCATION)
    try:
        search = GoogleSearch(params)
        result = search.get_dict()
    except Exception as exc:
        logger.error("SerpApi error for %r: %s", keyword, exc)
        raise

    if "error" in result:
        msg = result["error"]
        logger.error("SerpApi returned error for %r: %s", keyword, msg)
        raise RuntimeError(f"SerpApi error: {msg}")

    logger.debug(
        "SerpApi ok for %r: %d organic results",
        keyword,
        len(result.get("organic_results", [])),
    )
    return result


def parse_serp(keyword: str, serp: dict) -> dict:
    """
    Normalise a raw SerpApi response into a structured dict.

    Parameters
    ----------
    keyword:
        The original search query (echoed in the output for convenience).
    serp:
        The dict returned by :func:`fetch_serp`.

    Returns
    -------
    ::

        {
            "keyword": str,
            "organic": [
                {"position": int, "title": str, "link": str, "snippet": str},
                ...
            ],
            "people_also_ask": ["question text", ...],
            "related_searches": ["query text", ...],
        }
    """
    organic = []
    for item in serp.get("organic_results") or []:
        organic.append(
            {
                "position": item.get("position", 0),
                "title": (item.get("title") or "").strip(),
                "link": (item.get("link") or "").strip(),
                "snippet": (item.get("snippet") or "").strip(),
            }
        )

    people_also_ask = [
        (item.get("question") or "").strip()
        for item in (serp.get("related_questions") or [])
        if item.get("question")
    ]

    related_searches = [
        (item.get("query") or "").strip()
        for item in (serp.get("related_searches") or [])
        if item.get("query")
    ]

    return {
        "keyword": keyword,
        "organic": organic,
        "people_also_ask": people_also_ask,
        "related_searches": related_searches,
    }


def detect_competitor_hits(keyword: str, organic_results: list) -> list:
    """
    Cross-reference organic SERP results against active CompetitorDomain records.

    Parameters
    ----------
    keyword:
        The search query that produced these results.
    organic_results:
        The ``organic`` list from :func:`parse_serp` — each item must have
        ``link``, ``title``, and ``position`` keys.

    Returns
    -------
    List of hit dicts, one per (result, matched domain):

        [
            {
                "keyword": str,
                "competitor_domain": str,
                "url": str,
                "title": str,
                "rank": int,
            },
            ...
        ]
    """
    from seo_settings.models import CompetitorDomain

    active_domains = list(
        CompetitorDomain.objects.filter(active=True).values_list("domain", flat=True)
    )

    if not active_domains:
        logger.debug("detect_competitor_hits: no active competitor domains configured.")
        return []

    hits: list[dict] = []
    for result in organic_results:
        url = result.get("link", "")
        for domain in active_domains:
            if domain and domain in url:
                hits.append(
                    {
                        "keyword": keyword,
                        "competitor_domain": domain,
                        "url": url,
                        "title": result.get("title", ""),
                        "rank": result.get("position", 0),
                    }
                )
                break  # one match per result is enough

    logger.debug(
        "detect_competitor_hits: %d hit(s) for %r", len(hits), keyword
    )
    return hits


def detect_lcpsych_hits(
    keyword: str,
    organic_results: list,
    domain: str = "lcpsych.com",
) -> list:
    """
    Find positions where LC Psych appears in organic SERP results.

    Parameters
    ----------
    keyword:
        The search query that produced these results.
    organic_results:
        The ``organic`` list from :func:`parse_serp`.
    domain:
        Domain substring to match against result URLs (default: ``"lcpsych.com"``).

    Returns
    -------
    List of hit dicts::

        [
            {
                "keyword": str,
                "url": str,
                "title": str,
                "rank": int,
            },
            ...
        ]
    """
    hits: list[dict] = []
    for result in organic_results:
        url = result.get("link", "")
        if domain and domain in url:
            hits.append(
                {
                    "keyword": keyword,
                    "url": url,
                    "title": result.get("title", ""),
                    "rank": result.get("position", 0),
                }
            )
    logger.debug(
        "detect_lcpsych_hits: %d hit(s) for %r", len(hits), keyword
    )
    return hits
