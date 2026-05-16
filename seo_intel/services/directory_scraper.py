"""
seo_intel/services/directory_scraper.py
-----------------------------------------
Scrapes competitor (and LC Psych's own) directory profiles from five platforms:

  Platform    Engine
  --------    ------
  gbp         SerpAPI google_maps — rich structured JSON
  psychology_today  requests + BeautifulSoup — public HTML profile
  therapyden        requests + BeautifulSoup — public HTML profile
  zocdoc            requests + schema.org/og meta — JS-heavy, uses meta fallback
  alma              requests + schema.org/og meta

Strategy
--------
  1. Scrape the competitor's homepage to extract a business name
  2. Use SerpAPI organic search to discover the practice's profile URL on each
     directory (e.g. site:psychologytoday.com "Practice Name")
  3. Fetch & parse the profile page with requests + BeautifulSoup

All results are upserted into DirectoryProfile and cached for DIRECTORY_CACHE_TTL.

Public API
----------
    run_directory_scan(domain, force=False) -> dict[str, dict]
    get_cached_directory_data(domain) -> dict[str, dict]
    invalidate_directory_cache(domain) -> None
    PLATFORM_LABELS: dict[str, str]
    DIRECTORY_PLATFORMS: list[str]
"""
from __future__ import annotations

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

DIRECTORY_CACHE_TTL = 60 * 60 * 24  # 24 hours

_REQUEST_TIMEOUT = 12
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PLATFORM_LABELS: dict[str, str] = {
    "gbp": "Google Business Profile",
    "psychology_today": "Psychology Today",
    "therapyden": "TherapyDen",
    "zocdoc": "ZocDoc",
    "alma": "Alma",
}

DIRECTORY_PLATFORMS = list(PLATFORM_LABELS.keys())

# SerpAPI domain search strings — used to discover profile URLs
_PLATFORM_SEARCH_SITE: dict[str, str] = {
    "psychology_today": "psychologytoday.com/us",
    "therapyden": "therapyden.com",
    "zocdoc": "zocdoc.com",
    "alma": "helloalma.com",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_serpapi_key() -> str:
    key = os.environ.get("SERPAPI_KEY", "").strip()
    return key


def _serpapi_request(params: dict) -> dict:
    """Make a SerpAPI request. Returns parsed JSON or raises RuntimeError."""
    key = _get_serpapi_key()
    if not key:
        raise RuntimeError("SERPAPI_KEY not configured")
    params = {**params, "api_key": key, "no_cache": "false"}
    resp = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_html(url: str, timeout: int = _REQUEST_TIMEOUT) -> BeautifulSoup | None:
    """Fetch a page and return a BeautifulSoup tree, or None on error."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.debug("_fetch_html failed for %s: %s", url, exc)
        return None


def _og(soup: BeautifulSoup, prop: str) -> str:
    """Extract an Open Graph meta tag value."""
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return (tag.get("content") or "").strip() if tag else ""


def _schema_prop(soup: BeautifulSoup, prop: str) -> str:
    """Extract a schema.org itemprop value (first match)."""
    tag = soup.find(attrs={"itemprop": prop})
    if not tag:
        return ""
    return (tag.get("content") or tag.get_text(" ", strip=True))[:500].strip()


def _text(soup: BeautifulSoup, selector: str) -> str:
    """Return stripped text of the first CSS-matching element, or empty string."""
    el = soup.select_one(selector)
    return el.get_text(" ", strip=True)[:500] if el else ""


def _texts(soup: BeautifulSoup, selector: str, limit: int = 30) -> list[str]:
    """Return a list of stripped texts for all CSS-matching elements."""
    return [el.get_text(" ", strip=True) for el in soup.select(selector)][:limit]


# ---------------------------------------------------------------------------
# Business name extraction
# ---------------------------------------------------------------------------

def _get_business_name(domain: str) -> str:
    """Try to extract the practice's marketing name from their homepage.

    Falls back progressively through: og:site_name → <title> → domain stem.
    """
    try:
        soup = _fetch_html(f"https://{domain}", timeout=10)
        if soup is None:
            soup = _fetch_html(f"https://www.{domain}", timeout=10)
        if soup:
            # 1. og:site_name
            name = _og(soup, "og:site_name")
            if name and len(name) < 80:
                return name
            # 2. Schema.org name
            name = _schema_prop(soup, "name")
            if name and len(name) < 80:
                return name
            # 3. <title> — strip boilerplate
            title = soup.find("title")
            if title:
                raw = title.get_text(" ", strip=True)
                # Keep only the part before | or - or —
                parts = re.split(r"\s*[\|\-\u2014]\s*", raw)
                candidate = parts[0].strip()
                if candidate and len(candidate) < 80:
                    return candidate
    except Exception as exc:
        logger.debug("_get_business_name(%s) failed: %s", domain, exc)

    # 4. Fallback: capitalise the domain stem
    stem = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
    return stem


# ---------------------------------------------------------------------------
# SerpAPI helpers
# ---------------------------------------------------------------------------

def _find_profile_url(business_name: str, platform: str) -> str | None:
    """Use SerpAPI organic search to find the practice's listing on a directory."""
    site = _PLATFORM_SEARCH_SITE.get(platform)
    if not site:
        return None

    # Try two queries: domain-specific first, then name-based
    queries = [
        f'site:{site} "{business_name}"',
        f'"{business_name}" site:{site}',
    ]
    for query in queries:
        try:
            data = _serpapi_request({
                "engine": "google",
                "q": query,
                "num": 3,
                "gl": "us",
                "hl": "en",
            })
            results = data.get("organic_results", [])
            if results:
                url = results[0].get("link", "")
                if site.split("/")[0] in url:
                    return url
        except Exception as exc:
            logger.debug("_find_profile_url SerpAPI search failed (%s / %s): %s", platform, query, exc)
            break  # If SerpAPI is down / unconfigured, stop trying

    return None


# ---------------------------------------------------------------------------
# GBP scraper (via SerpAPI google_maps engine)
# ---------------------------------------------------------------------------

def _scrape_gbp(domain: str, business_name: str) -> dict:
    """Fetch Google Business Profile data via SerpAPI's google_maps engine."""
    try:
        data = _serpapi_request({
            "engine": "google_maps",
            "q": business_name,
            "type": "search",
            "gl": "us",
            "hl": "en",
        })
    except Exception as exc:
        return {"error": str(exc), "found": False}

    # SerpAPI google_maps returns `local_results` list
    local_results = data.get("local_results", [])
    if not local_results:
        # Try place_results (single place) fallback
        place = data.get("place_results", {})
        if place:
            local_results = [place]

    # Find the best match — prefer results that mention the domain or name
    best = None
    for result in local_results[:5]:
        title = (result.get("title") or "").lower()
        if any(w in title for w in business_name.lower().split()[:3]):
            best = result
            break
    if best is None and local_results:
        best = local_results[0]

    if not best:
        return {"found": False, "error": "No GBP listing found"}

    extensions = best.get("extensions", {})

    return {
        "found": True,
        "profile_url": best.get("website") or best.get("link") or "",
        "maps_url": best.get("place_id")
            and f"https://www.google.com/maps/place/?q=place_id:{best['place_id']}" or "",
        "business_name": best.get("title", ""),
        "categories": best.get("type", ""),
        "rating": best.get("rating"),
        "reviews_count": best.get("reviews") or best.get("reviews_original") or 0,
        "photos_count": extensions.get("total_photos") or best.get("thumbnail") and 1 or 0,
        "service_areas": best.get("service_area_name", ""),
        "address": best.get("address", ""),
        "phone": best.get("phone", ""),
        "hours": best.get("hours", ""),
        "posts_available": bool(extensions.get("posts")),
        "booking_available": bool(extensions.get("online_appointments")),
        "q_and_a_count": extensions.get("questions_and_answers") or 0,
        "attributes": best.get("attributes", {}),
        "completeness_notes": _gbp_completeness(best),
    }


def _gbp_completeness(result: dict) -> list[str]:
    """Return list of missing GBP completeness items."""
    missing = []
    if not result.get("description"):
        missing.append("No business description")
    if not result.get("hours"):
        missing.append("Business hours not set")
    if not (result.get("extensions", {}).get("total_photos") or 0) > 5:
        missing.append("Fewer than 5 photos")
    if not result.get("website"):
        missing.append("Website not linked")
    return missing


# ---------------------------------------------------------------------------
# Psychology Today scraper
# ---------------------------------------------------------------------------

def _scrape_psychology_today(profile_url: str) -> dict:
    """Scrape a Psychology Today therapist profile page."""
    soup = _fetch_html(profile_url)
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    # Business / practice name
    result["name"] = (
        _text(soup, "h1.profile-title")
        or _text(soup, "h1.profile-header-name")
        or _og(soup, "og:title")
    )

    # Bio / description
    bio_el = soup.select_one(".profile-description-text, #summary, .provider-summary")
    result["bio_text"] = bio_el.get_text(" ", strip=True) if bio_el else ""
    result["bio_length"] = len(result["bio_text"].split())

    # Specialties
    result["specialties"] = _texts(
        soup,
        ".profile-tags .profile-tag, .tags-area .tag-item, .issues li",
    )

    # Modalities / approaches
    result["modalities"] = _texts(
        soup,
        ".modalities li, .approaches li, "
        "[data-section='modalities'] li, "
        "[data-section='Therapeutic Approach'] li",
    )

    # Insurance
    result["insurance"] = _texts(
        soup,
        ".insurance-list li, .insurance li, "
        "[data-section='insurance'] li",
    )

    # Photo count — count actual image elements in profile photos section
    photo_section = soup.select_one(".profile-photos, .photo-gallery, .photos-section")
    if photo_section:
        result["photos_count"] = len(photo_section.find_all("img"))
    else:
        result["photos_count"] = 1 if soup.find("img", class_=re.compile(r"profile.*photo|avatar")) else 0

    # Rating / reviews
    rating_el = soup.select_one(".rating-value, .average-rating, [itemprop='ratingValue']")
    result["rating"] = float(rating_el.get_text(strip=True)) if rating_el else None

    review_count_el = soup.select_one(".review-count, [itemprop='reviewCount']")
    result["reviews_count"] = _parse_int(review_count_el.get_text(strip=True)) if review_count_el else 0

    # Profile completeness estimate
    filled = sum([
        bool(result["bio_length"] > 50),
        bool(result["specialties"]),
        bool(result["modalities"]),
        bool(result["insurance"]),
        bool(result["photos_count"]),
    ])
    result["completeness_pct"] = round(filled / 5 * 100)

    return result


# ---------------------------------------------------------------------------
# TherapyDen scraper
# ---------------------------------------------------------------------------

def _scrape_therapyden(profile_url: str) -> dict:
    """Scrape a TherapyDen therapist profile page."""
    soup = _fetch_html(profile_url)
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["name"] = (
        _text(soup, "h1.therapist-name, h1.provider-name, h1")
        or _og(soup, "og:title")
    )
    bio_el = soup.select_one(".bio, .therapist-bio, .about-section, .description")
    result["bio_text"] = bio_el.get_text(" ", strip=True) if bio_el else _og(soup, "og:description")
    result["bio_length"] = len(result["bio_text"].split())

    result["specialties"] = _texts(soup, ".specialties li, .issues li, .tags li")
    result["modalities"] = _texts(soup, ".approaches li, .modalities li, .treatment-approaches li")
    result["insurance"] = _texts(soup, ".insurance li, .insurance-accepted li")
    result["photos_count"] = len(soup.select(".profile-photo, .gallery img")) or (
        1 if soup.select_one("img.avatar, img.profile-img") else 0
    )

    rating_el = soup.select_one("[itemprop='ratingValue'], .rating")
    result["rating"] = float(rating_el.get_text(strip=True)) if rating_el else None

    filled = sum([
        bool(result["bio_length"] > 50),
        bool(result["specialties"]),
        bool(result["modalities"]),
        bool(result["insurance"]),
    ])
    result["completeness_pct"] = round(filled / 4 * 100)

    return result


# ---------------------------------------------------------------------------
# ZocDoc scraper (meta-tag fallback — page is JS-rendered)
# ---------------------------------------------------------------------------

def _scrape_zocdoc(profile_url: str) -> dict:
    """Scrape a ZocDoc provider profile — extracts what's available in static HTML."""
    soup = _fetch_html(profile_url)
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["name"] = _og(soup, "og:title") or _schema_prop(soup, "name")
    result["bio_text"] = _og(soup, "og:description") or _schema_prop(soup, "description")
    result["bio_length"] = len(result["bio_text"].split())

    # Schema.org AggregateRating
    rating_el = soup.find(attrs={"itemprop": "ratingValue"})
    result["rating"] = float(rating_el.get("content") or rating_el.get_text(strip=True) or 0) if rating_el else None

    review_el = soup.find(attrs={"itemprop": "reviewCount"})
    result["reviews_count"] = _parse_int(review_el.get("content") or review_el.get_text(strip=True)) if review_el else 0

    result["specialties"] = _texts(soup, "[itemprop='medicalSpecialty'], .specialty-tag")
    result["insurance"] = _texts(soup, "[data-test='insurance-name'], .insurance-item")
    result["photos_count"] = 1 if soup.find("img", attrs={"itemprop": "image"}) else 0

    filled = sum([
        bool(result["name"]),
        bool(result["bio_length"] > 20),
        bool(result["specialties"]),
        bool(result["insurance"]),
    ])
    result["completeness_pct"] = round(filled / 4 * 100)

    return result


# ---------------------------------------------------------------------------
# Alma scraper (meta-tag fallback — page is JS-rendered)
# ---------------------------------------------------------------------------

def _scrape_alma(profile_url: str) -> dict:
    """Scrape an Alma provider profile — extracts what's in static HTML/meta."""
    soup = _fetch_html(profile_url)
    if soup is None:
        return {"found": False, "profile_url": profile_url, "error": "Could not fetch page"}

    result: dict[str, Any] = {"found": True, "profile_url": profile_url}

    result["name"] = _og(soup, "og:title") or _schema_prop(soup, "name")
    result["bio_text"] = _og(soup, "og:description") or _schema_prop(soup, "description")
    result["bio_length"] = len(result["bio_text"].split())
    result["specialties"] = _texts(soup, ".specialties li, .issues li, [data-testid='specialty']")
    result["insurance"] = _texts(soup, ".insurance li, [data-testid='insurance']")
    result["photos_count"] = 1 if soup.find("img", attrs={"itemprop": "image"}) else 0

    filled = sum([
        bool(result["name"]),
        bool(result["bio_length"] > 20),
        bool(result["specialties"]),
    ])
    result["completeness_pct"] = round(filled / 3 * 100)

    return result


# ---------------------------------------------------------------------------
# Orchestration helpers
# ---------------------------------------------------------------------------

def _parse_int(text: str) -> int:
    """Parse a numeric string that may contain commas or parentheses."""
    m = re.search(r"\d[\d,]*", str(text).replace(",", ""))
    return int(m.group().replace(",", "")) if m else 0


def _scrape_platform(domain: str, platform: str, business_name: str) -> dict:
    """Discover + scrape a single platform. Returns structured result dict."""
    if platform == "gbp":
        return _scrape_gbp(domain, business_name)

    # Discover profile URL via SerpAPI
    profile_url: str | None = None
    try:
        profile_url = _find_profile_url(business_name, platform)
    except Exception as exc:
        logger.debug("_find_profile_url(%s, %s) error: %s", domain, platform, exc)

    if not profile_url:
        return {"found": False, "error": "Profile URL not found via SerpAPI"}

    time.sleep(0.5)  # polite delay between pages

    scrapers = {
        "psychology_today": _scrape_psychology_today,
        "therapyden": _scrape_therapyden,
        "zocdoc": _scrape_zocdoc,
        "alma": _scrape_alma,
    }
    scraper = scrapers.get(platform)
    if scraper is None:
        return {"found": False, "error": f"Unknown platform: {platform}"}

    try:
        return scraper(profile_url)
    except Exception as exc:
        logger.warning("_scrape_platform(%s, %s) failed: %s", domain, platform, exc)
        return {"found": False, "profile_url": profile_url, "error": str(exc)}


def _cache_key(domain: str) -> str:
    safe = re.sub(r"[^a-z0-9]", "_", domain.lower())
    return f"dir_profiles:{safe}"


def _upsert_db(domain: str, platform: str, data: dict) -> None:
    """Upsert a DirectoryProfile row."""
    from seo_intel.models import DirectoryProfile
    DirectoryProfile.objects.update_or_create(
        competitor_domain=domain,
        platform=platform,
        defaults={"data": data},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_directory_scan(domain: str, force: bool = False) -> dict[str, dict]:
    """Scan all directory platforms for *domain* and return results.

    Results are upserted into DirectoryProfile and cached for 24 hours.
    Pass ``force=True`` to bypass the cache and re-fetch.
    """
    ck = _cache_key(domain)
    if not force:
        cached = cache.get(ck)
        if cached is not None:
            return cached

    business_name = _get_business_name(domain)
    logger.info("run_directory_scan(%s) — business_name=%r", domain, business_name)

    results: dict[str, dict] = {}
    for platform in DIRECTORY_PLATFORMS:
        logger.info("  scanning %s / %s …", domain, platform)
        try:
            data = _scrape_platform(domain, platform, business_name)
        except Exception as exc:
            logger.exception("  platform %s crashed: %s", platform, exc)
            data = {"found": False, "error": str(exc)}

        data["_business_name"] = business_name
        results[platform] = data
        _upsert_db(domain, platform, data)

    cache.set(ck, results, DIRECTORY_CACHE_TTL)
    return results


def get_cached_directory_data(domain: str) -> dict[str, dict]:
    """Load directory profiles from cache, falling back to DB rows.

    Returns a dict keyed by platform name. Platforms with no data have
    an empty dict as value.
    """
    ck = _cache_key(domain)
    cached = cache.get(ck)
    if cached is not None:
        return cached

    # DB fallback
    from seo_intel.models import DirectoryProfile
    rows = DirectoryProfile.objects.filter(competitor_domain=domain)
    if not rows.exists():
        return {p: {} for p in DIRECTORY_PLATFORMS}

    result = {p: {} for p in DIRECTORY_PLATFORMS}
    for row in rows:
        result[row.platform] = row.data or {}

    cache.set(ck, result, DIRECTORY_CACHE_TTL)
    return result


def invalidate_directory_cache(domain: str) -> None:
    """Remove the directory cache for *domain*."""
    cache.delete(_cache_key(domain))
