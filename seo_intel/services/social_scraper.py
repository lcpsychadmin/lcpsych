"""
seo_intel/services/social_scraper.py
--------------------------------------
Scrapes competitor (and LC Psych's own) social media presence from:

  Platform   Method
  --------   ------
  facebook   SerpAPI discovery → OpenGraph / HTML scrape of public page
  instagram  SerpAPI discovery → public profile HTML scrape
  tiktok     SerpAPI discovery → public profile HTML scrape
  youtube    SerpAPI discovery → YouTube Data API v3 (if YOUTUBE_API_KEY set)
               fallback: HTML scrape of public channel page

Note on API limitations
-----------------------
  Facebook, Instagram, and TikTok restrict automated access significantly.
  This scraper extracts what is publicly available in static HTML and meta
  tags. Follower counts, posting frequency, and engagement are approximated
  from the data each platform exposes in its initial HTML payload.

  For the most reliable data:
  - YouTube: Set YOUTUBE_API_KEY in the environment.
  - Instagram: Connect via official Instagram Graph API (business account required).
  - Facebook: Connect via official Facebook Marketing API (page admin required).

All results are upserted into SocialProfile and cached for SOCIAL_CACHE_TTL.

Public API
----------
    run_social_scan(domain, force=False) -> dict[str, dict]
    get_cached_social_data(domain) -> dict[str, dict]
    invalidate_social_cache(domain) -> None
    SOCIAL_PLATFORM_LABELS: dict[str, str]
    SOCIAL_PLATFORMS: list[str]
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

SOCIAL_CACHE_TTL = 60 * 60 * 6  # 6 hours

_REQUEST_TIMEOUT = 12
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

SOCIAL_PLATFORM_LABELS: dict[str, str] = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
}

SOCIAL_PLATFORMS = list(SOCIAL_PLATFORM_LABELS.keys())

# SerpAPI search site patterns
_SOCIAL_SEARCH_SITE: dict[str, str] = {
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str, extra_headers: dict | None = None, timeout: int = _REQUEST_TIMEOUT) -> BeautifulSoup | None:
    try:
        headers = {**_HEADERS, **(extra_headers or {})}
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.debug("_fetch_html failed %s: %s", url, exc)
        return None


def _og(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return (tag.get("content") or "").strip() if tag else ""


def _parse_int(text: str) -> int:
    """Parse a compact number like '12.5K', '1.2M', '500', '3,000'."""
    text = str(text).strip().upper().replace(",", "")
    m = re.search(r"([\d.]+)\s*([KMB]?)", text)
    if not m:
        return 0
    value = float(m.group(1))
    suffix = m.group(2)
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(value * multipliers.get(suffix, 1))


def _get_serpapi_key() -> str:
    return os.environ.get("SERPAPI_KEY", "").strip()


def _get_youtube_api_key() -> str:
    return os.environ.get("YOUTUBE_API_KEY", "").strip()


def _serpapi_request(params: dict) -> dict:
    key = _get_serpapi_key()
    if not key:
        raise RuntimeError("SERPAPI_KEY not configured")
    params = {**params, "api_key": key}
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _find_social_url(business_name: str, platform: str) -> str | None:
    """Use SerpAPI organic search to discover the practice's social profile."""
    site = _SOCIAL_SEARCH_SITE.get(platform, "")
    queries = [
        f'site:{site} "{business_name}"',
        f'"{business_name}" {platform}',
    ]
    for query in queries:
        try:
            data = _serpapi_request({
                "engine": "google",
                "q": query,
                "num": 5,
                "gl": "us",
                "hl": "en",
            })
            for result in data.get("organic_results", []):
                url = result.get("link", "")
                if site in url:
                    # Filter out directory pages (search, explore, hashtag pages)
                    if re.search(r"/(search|explore|hashtag|tag|channel_search)/", url):
                        continue
                    return url
        except Exception as exc:
            logger.debug("_find_social_url(%s / %s) failed: %s", platform, query, exc)
            break
    return None


def _extract_json_blob(html_text: str, patterns: list[str]) -> dict:
    """Try to extract a JSON blob from inline script tags matching *patterns*."""
    for pattern in patterns:
        m = re.search(pattern, html_text)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, IndexError):
                continue
    return {}


# ---------------------------------------------------------------------------
# Facebook scraper
# ---------------------------------------------------------------------------

def _scrape_facebook(profile_url: str) -> dict:
    """Scrape a Facebook Page — extracts what's available without authentication."""
    soup = _fetch_html(profile_url, extra_headers={"Accept": "text/html"})
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["page_name"] = _og(soup, "og:title") or _og(soup, "og:site_name")
    result["description"] = _og(soup, "og:description")

    # Try to get follower count from meta description or page text
    page_text = soup.get_text(" ", strip=True)
    follower_m = re.search(r"([\d,\.]+[KMB]?)\s+(?:followers|people follow this)", page_text, re.I)
    result["followers"] = _parse_int(follower_m.group(1)) if follower_m else None
    result["followers_display"] = follower_m.group(1) if follower_m else "N/A"

    like_m = re.search(r"([\d,\.]+[KMB]?)\s+(?:likes|people like this)", page_text, re.I)
    result["likes"] = _parse_int(like_m.group(1)) if like_m else None

    # Rating
    rating_m = re.search(r"(\d(?:\.\d)?)\s*(?:out of 5|/5|star)", page_text, re.I)
    result["rating"] = float(rating_m.group(1)) if rating_m else None

    # Category
    og_type = _og(soup, "og:type")
    result["page_type"] = og_type or "page"

    # Estimate posting frequency from visible post count (limited without login)
    result["posting_note"] = "Full engagement data requires Facebook API access"
    result["data_quality"] = "limited"  # flags that this is best-effort

    return result


# ---------------------------------------------------------------------------
# Instagram scraper
# ---------------------------------------------------------------------------

def _scrape_instagram(profile_url: str) -> dict:
    """Scrape an Instagram public profile page."""
    # Instagram's public profile exposes some data in meta tags
    soup = _fetch_html(profile_url, extra_headers={"Accept": "text/html"})
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["username"] = profile_url.rstrip("/").split("/")[-1].lstrip("@")
    result["display_name"] = _og(soup, "og:title")

    desc = _og(soup, "og:description")
    result["bio"] = desc

    # IG description format: "X Followers, Y Following, Z Posts — ..."
    parts = re.findall(r"([\d,\.]+[KMB]?)\s+(\w+)", desc)
    metrics: dict[str, int] = {}
    for val, label in parts:
        label_lower = label.lower()
        parsed = _parse_int(val)
        if "follower" in label_lower:
            metrics["followers"] = parsed
        elif "following" in label_lower:
            metrics["following"] = parsed
        elif "post" in label_lower:
            metrics["post_count"] = parsed

    result.update(metrics)
    result["followers_display"] = next((p[0] for p in parts if "follow" in p[1].lower()), "N/A")
    result["data_quality"] = "limited"
    result["posting_note"] = "Full engagement data requires Instagram Graph API access"

    return result


# ---------------------------------------------------------------------------
# TikTok scraper
# ---------------------------------------------------------------------------

def _scrape_tiktok(profile_url: str) -> dict:
    """Scrape a TikTok public profile page."""
    # TikTok exposes basic data in meta tags / initial data JSON
    headers = {
        **_HEADERS,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        # TikTok requires specific accept headers to serve HTML
        "Referer": "https://www.tiktok.com/",
    }
    soup = _fetch_html(profile_url, extra_headers=headers)
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["username"] = profile_url.rstrip("/").split("/@")[-1] if "/@" in profile_url else ""
    result["display_name"] = _og(soup, "og:title")
    desc = _og(soup, "og:description")
    result["bio"] = desc

    # Try to extract from __NEXT_DATA__ or window.__INIT_PROPS__
    page_source = soup.get_text(" ", strip=True)
    follower_m = re.search(r'"followerCount"\s*:\s*(\d+)', str(soup))
    following_m = re.search(r'"followingCount"\s*:\s*(\d+)', str(soup))
    video_m = re.search(r'"videoCount"\s*:\s*(\d+)', str(soup))
    like_m = re.search(r'"heartCount"\s*:\s*(\d+)', str(soup))

    result["followers"] = int(follower_m.group(1)) if follower_m else None
    result["following"] = int(following_m.group(1)) if following_m else None
    result["video_count"] = int(video_m.group(1)) if video_m else None
    result["total_likes"] = int(like_m.group(1)) if like_m else None

    # Followers from description fallback
    if result["followers"] is None:
        f_m = re.search(r"([\d\.]+[KMB]?)\s+Followers", desc, re.I)
        result["followers"] = _parse_int(f_m.group(1)) if f_m else None
        result["followers_display"] = f_m.group(1) if f_m else "N/A"
    else:
        result["followers_display"] = str(result["followers"])

    result["data_quality"] = "limited"
    result["posting_note"] = "Full engagement data requires TikTok Research API access"

    return result


# ---------------------------------------------------------------------------
# YouTube scraper (API v3 or HTML fallback)
# ---------------------------------------------------------------------------

def _scrape_youtube_api(channel_url: str, business_name: str, api_key: str) -> dict | None:
    """Fetch YouTube channel data via YouTube Data API v3. Returns None on failure."""
    # First, determine the channel ID from the URL or via search
    channel_id = None

    # Try to extract channel ID or handle from URL
    # Formats: /channel/{id}, /@{handle}, /c/{name}, /user/{name}
    m = re.search(r"/channel/([a-zA-Z0-9_-]+)", channel_url)
    if m:
        channel_id = m.group(1)

    if not channel_id:
        # Use YouTube search API to find by business name
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": business_name,
                    "type": "channel",
                    "maxResults": 3,
                    "key": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if items:
                channel_id = items[0]["snippet"]["channelId"]
        except Exception as exc:
            logger.debug("YouTube search API failed: %s", exc)
            return None

    if not channel_id:
        return None

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": channel_id,
                "key": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        ch = items[0]
        stats = ch.get("statistics", {})
        snippet = ch.get("snippet", {})
        return {
            "found": True,
            "channel_id": channel_id,
            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            "channel_name": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "subscribers": _parse_int(str(stats.get("subscriberCount", 0))),
            "subscribers_display": stats.get("subscriberCount", "N/A"),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "country": snippet.get("country", ""),
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "data_quality": "api",
        }
    except Exception as exc:
        logger.debug("YouTube channels API failed: %s", exc)
        return None


def _scrape_youtube_html(channel_url: str) -> dict:
    """Fallback: HTML scrape of a YouTube channel page."""
    soup = _fetch_html(channel_url)
    if soup is None:
        return {"found": False, "profile_url": channel_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": channel_url}
    result["channel_name"] = _og(soup, "og:title")
    result["description"] = _og(soup, "og:description")

    page_text = str(soup)
    sub_m = re.search(r'"subscriberCountText"\s*:\s*\{"simpleText"\s*:\s*"([^"]+)"', page_text)
    result["subscribers_display"] = sub_m.group(1) if sub_m else "N/A"
    result["subscribers"] = _parse_int(result["subscribers_display"])

    vid_m = re.search(r'"videoCountText"\s*.*?"(\d+(?:,\d+)*)\s*videos?"', page_text)
    result["video_count"] = _parse_int(vid_m.group(1)) if vid_m else None

    result["data_quality"] = "html"
    result["posting_note"] = "Set YOUTUBE_API_KEY for richer data"

    return result


def _scrape_youtube(profile_url: str, business_name: str) -> dict:
    """Scrape YouTube channel — prefers API, falls back to HTML scrape."""
    api_key = _get_youtube_api_key()
    if api_key:
        api_result = _scrape_youtube_api(profile_url, business_name, api_key)
        if api_result:
            api_result["profile_url"] = profile_url
            return api_result

    return _scrape_youtube_html(profile_url)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _get_business_name(domain: str) -> str:
    """Reuse the same business name extraction as directory_scraper."""
    from seo_intel.services.directory_scraper import _get_business_name as _dn
    return _dn(domain)


def _scrape_platform(domain: str, platform: str, business_name: str) -> dict:
    """Discover + scrape a single social platform. Returns structured dict."""
    profile_url: str | None = None
    try:
        profile_url = _find_social_url(business_name, platform)
    except Exception as exc:
        logger.debug("_find_social_url(%s, %s) error: %s", domain, platform, exc)

    if not profile_url:
        return {"found": False, "error": "Profile not found via SerpAPI"}

    time.sleep(0.5)

    try:
        if platform == "facebook":
            return _scrape_facebook(profile_url)
        elif platform == "instagram":
            return _scrape_instagram(profile_url)
        elif platform == "tiktok":
            return _scrape_tiktok(profile_url)
        elif platform == "youtube":
            return _scrape_youtube(profile_url, business_name)
        else:
            return {"found": False, "error": f"Unknown platform: {platform}"}
    except Exception as exc:
        logger.warning("_scrape_platform(%s, %s) crashed: %s", domain, platform, exc)
        return {"found": False, "profile_url": profile_url or "", "error": str(exc)}


def _cache_key(domain: str) -> str:
    safe = re.sub(r"[^a-z0-9]", "_", domain.lower())
    return f"social_profiles:{safe}"


def _upsert_db(domain: str, platform: str, data: dict) -> None:
    from seo_intel.models import SocialProfile
    SocialProfile.objects.update_or_create(
        competitor_domain=domain,
        platform=platform,
        defaults={"data": data},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_social_scan(domain: str, force: bool = False) -> dict[str, dict]:
    """Scan all social platforms for *domain* and return results.

    Results are upserted into SocialProfile and cached for 6 hours.
    Pass ``force=True`` to bypass the cache and re-scan.
    """
    ck = _cache_key(domain)
    if not force:
        cached = cache.get(ck)
        if cached is not None:
            return cached

    business_name = _get_business_name(domain)
    logger.info("run_social_scan(%s) — business_name=%r", domain, business_name)

    results: dict[str, dict] = {}
    for platform in SOCIAL_PLATFORMS:
        logger.info("  scanning %s / %s …", domain, platform)
        try:
            data = _scrape_platform(domain, platform, business_name)
        except Exception as exc:
            logger.exception("  platform %s crashed: %s", platform, exc)
            data = {"found": False, "error": str(exc)}

        data["_business_name"] = business_name
        results[platform] = data
        _upsert_db(domain, platform, data)

    cache.set(ck, results, SOCIAL_CACHE_TTL)
    return results


def get_cached_social_data(domain: str) -> dict[str, dict]:
    """Load social profiles from cache, falling back to DB rows."""
    ck = _cache_key(domain)
    cached = cache.get(ck)
    if cached is not None:
        return cached

    from seo_intel.models import SocialProfile
    rows = SocialProfile.objects.filter(competitor_domain=domain)
    if not rows.exists():
        return {p: {} for p in SOCIAL_PLATFORMS}

    result = {p: {} for p in SOCIAL_PLATFORMS}
    for row in rows:
        result[row.platform] = row.data or {}

    cache.set(ck, result, SOCIAL_CACHE_TTL)
    return result


def invalidate_social_cache(domain: str) -> None:
    """Remove the social cache for *domain*."""
    cache.delete(_cache_key(domain))
