"""
seo_intel/services/competitor_crawler.py
------------------------------------------
Competitor site crawler for the Competitor Analysis Engine.

Crawls up to *max_pages* HTML pages of a competitor domain using
requests + BeautifulSoup, extracting structured signals from each page.
Results are cached for 24 hours (CACHE_TTL seconds).

Public API
----------
    crawl_competitor(domain, max_pages=200, force=False) -> list[dict]
    get_cached_crawl(domain) -> list[dict] | None
    invalidate_crawl(domain) -> None

Each page dict contains:
    url          str       — canonical URL fetched
    title        str       — <title> text
    h1           list[str] — first 3 H1 texts
    h2           list[str] — first 10 H2 texts
    word_count   int       — body word count (nav/footer stripped)
    schema_types list[str] — Schema.org @type values found
    internal_links list[str]
    keyword_hits dict[str, list[str]]  — keys: services/modalities/testing/conditions/locations
"""
from __future__ import annotations

import logging
import re
import time
from collections import deque

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 60 * 24  # 24 hours

_REQUEST_TIMEOUT = 10
_CRAWL_DELAY = 0.5
_USER_AGENT = (
    "Mozilla/5.0 (compatible; LCPsych-SEO-Bot/1.0; +https://lcpsych.com)"
)

# ---------------------------------------------------------------------------
# Keyword taxonomy — broad coverage for mental-health / psychology practices
# ---------------------------------------------------------------------------

SERVICES_KW: frozenset[str] = frozenset({
    "therapy", "therapist", "counseling", "counselor", "psychotherapy",
    "psychiatry", "psychiatrist", "mental health", "behavioral health",
    "psychologist", "assessment", "evaluation", "treatment",
    "telehealth", "teletherapy", "online therapy", "medication management",
    "medication", "prescriber", "clinical social work", "social worker",
    "life coaching", "coaching", "support group",
})

MODALITIES_KW: frozenset[str] = frozenset({
    "cbt", "cognitive behavioral therapy", "cognitive behavioral",
    "dbt", "dialectical behavior therapy", "dialectical behavioral",
    "emdr", "eye movement desensitization",
    "psychodynamic", "psychoanalytic",
    "mindfulness", "mindfulness-based", "mbct",
    "play therapy", "sand tray", "art therapy", "expressive arts",
    "somatic", "somatic experiencing",
    "act", "acceptance and commitment", "acceptance commitment",
    "trauma-focused", "trauma focused", "trauma-informed", "trauma informed",
    "attachment-based", "attachment based", "attachment therapy",
    "solution focused", "solution-focused", "sfbt",
    "motivational interviewing", "motivational enhancement",
    "exposure therapy", "cpt", "cognitive processing therapy",
    "gottman", "family systems", "internal family systems", "ifs",
    "emotionally focused", "eft",
    "narrative therapy", "interpersonal therapy", "ipt",
    "behavioral activation", "prolonged exposure",
    "rational emotive", "rebt",
})

TESTING_KW: frozenset[str] = frozenset({
    "psychological testing", "psychological evaluation",
    "neuropsychological testing", "neuropsychological evaluation", "neuropsychology",
    "psychoeducational evaluation", "psychoeducational testing",
    "adhd testing", "adhd assessment", "adhd evaluation", "adhd diagnosis",
    "autism testing", "autism evaluation", "autism assessment", "autism diagnosis",
    "asd testing", "asd evaluation",
    "iq testing", "iq test", "intelligence testing",
    "learning disability", "learning disabilities", "learning disorder",
    "cognitive assessment", "cognitive testing", "cognitive evaluation",
    "diagnostic evaluation", "diagnostic testing", "diagnostic assessment",
    "gifted testing", "gifted evaluation", "gifted assessment",
    "academic testing", "academic evaluation",
    "behavioral assessment", "personality testing", "personality assessment",
})

CONDITIONS_KW: frozenset[str] = frozenset({
    "anxiety", "generalized anxiety", "social anxiety", "panic disorder", "panic attacks",
    "phobia", "phobias", "ocd", "obsessive compulsive", "obsessive-compulsive",
    "depression", "major depression", "major depressive", "postpartum depression",
    "ptsd", "post-traumatic stress", "post traumatic stress", "trauma",
    "adhd", "attention deficit", "attention-deficit",
    "autism", "autism spectrum", "asd",
    "bipolar", "bipolar disorder",
    "schizophrenia", "psychosis",
    "eating disorder", "anorexia", "bulimia", "binge eating", "arfid",
    "grief", "bereavement", "loss",
    "stress", "chronic stress",
    "anger management", "anger",
    "relationship issues", "relationship problems", "couples",
    "marriage", "divorce", "co-parenting", "parenting",
    "self-esteem", "self-harm", "self injury", "suicidal",
    "addiction", "substance use", "substance abuse",
    "sleep disorder", "insomnia",
    "chronic illness", "chronic pain", "health anxiety",
    "identity", "lgbtq", "gender identity",
    "racial trauma", "cultural", "multicultural",
    "workplace stress", "burnout", "career",
})

LOCATION_KW: frozenset[str] = frozenset({
    # States
    "kentucky", "ohio", "indiana", "west virginia", "tennessee",
    "virginia", "georgia", "michigan", "illinois",
    # NKY / Cincinnati metro
    "cincinnati", "lexington", "louisville", "northern kentucky",
    "florence", "covington", "newport", "erlanger", "independence",
    "highland heights", "fort mitchell", "edgewood", "elsmere",
    "bellevue", "dayton kentucky", "cold spring", "alexandria",
    # Ohio cities
    "dayton", "columbus", "cleveland", "toledo", "akron",
    # Indiana cities
    "indianapolis", "fort wayne",
    # Qualifiers
    "near me", "nearby", "local", "in-person", "in person",
    "online", "virtual",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_key(domain: str) -> str:
    clean = re.sub(r"^www\.", "", domain.lower()).strip("/")
    return f"comp_crawl_v1_{clean}"


def get_cached_crawl(domain: str) -> list[dict] | None:
    """Return crawl results for *domain* — cache first, then DB."""
    cached = cache.get(_cache_key(domain))
    if cached is not None:
        return cached
    # Fall back to the database snapshot
    try:
        from seo_intel.models import CompetitorCrawl
        snap = CompetitorCrawl.objects.filter(domain=_normalise_domain(domain)).first()
        if snap is not None:
            logger.info(
                "competitor_crawler: DB hit for %s (%d pages, crawled %s)",
                domain, snap.page_count, snap.crawled_at,
            )
            # Warm the cache so subsequent reads are fast
            cache.set(_cache_key(domain), snap.pages, CACHE_TTL)
            return snap.pages
    except Exception as exc:
        logger.warning("competitor_crawler: DB fallback failed for %s: %s", domain, exc)
    return None


def invalidate_crawl(domain: str) -> None:
    """Delete cached crawl results for *domain*."""
    cache.delete(_cache_key(domain))


def _normalise_domain(domain: str) -> str:
    d = domain.lower()
    d = re.sub(r"^https?://", "", d)
    return d.strip("/").split("/")[0]


def _base_url(domain: str) -> str:
    return f"https://{domain}/"


def _same_domain(url: str, domain: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc:
        return True
    return parsed.netloc.lower().replace("www.", "") == domain.lower().replace("www.", "")


_SKIP_EXTENSIONS = frozenset((
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".zip", ".css", ".js", ".ico", ".xml",
    ".woff", ".woff2", ".ttf", ".eot", ".map",
))
_SKIP_SEGMENTS = ("/wp-json/", "/wp-admin/", "/feed/", "?replytocom")


def _skip_url(url: str) -> bool:
    lowered = url.lower().split("?")[0]
    if any(lowered.endswith(ext) for ext in _SKIP_EXTENSIONS):
        return True
    if any(seg in url for seg in _SKIP_SEGMENTS):
        return True
    return False


def _extract_schema_types(soup: BeautifulSoup) -> list[str]:
    types: list[str] = []
    for el in soup.find_all(attrs={"itemtype": True}):
        val = el.get("itemtype", "")
        if val:
            types.append(val.rsplit("/", 1)[-1])
    for script in soup.find_all("script", type="application/ld+json"):
        found = re.findall(r'"@type"\s*:\s*"([^"]+)"', script.get_text())
        types.extend(found)
    return list(set(types))


def _extract_keyword_hits(text_lower: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {
        "services": [],
        "modalities": [],
        "testing": [],
        "conditions": [],
        "locations": [],
    }
    for kw in SERVICES_KW:
        if kw in text_lower:
            hits["services"].append(kw)
    for kw in MODALITIES_KW:
        if kw in text_lower:
            hits["modalities"].append(kw)
    for kw in TESTING_KW:
        if kw in text_lower:
            hits["testing"].append(kw)
    for kw in CONDITIONS_KW:
        if kw in text_lower:
            hits["conditions"].append(kw)
    for kw in LOCATION_KW:
        if kw in text_lower:
            hits["locations"].append(kw)
    return hits


def _extract_internal_links(soup: BeautifulSoup, base: str, domain: str) -> list[str]:
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base, href).split("#")[0].rstrip("/")
        if absolute and _same_domain(absolute, domain) and not _skip_url(absolute):
            links.append(absolute)
    return list(set(links))


def _parse_page(url: str, html: str, domain: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    h1s = [el.get_text(strip=True) for el in soup.find_all("h1")]
    h2s = [el.get_text(strip=True) for el in soup.find_all("h2")]

    schema_types = _extract_schema_types(soup)
    internal_links = _extract_internal_links(soup, url, domain)

    # Strip nav/chrome before word count
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    body_text = soup.get_text(" ", strip=True)
    word_count = len(body_text.split())
    text_lower = body_text.lower()

    keyword_hits = _extract_keyword_hits(text_lower)

    return {
        "url": url,
        "title": title,
        "h1": h1s[:3],
        "h2": h2s[:10],
        "word_count": word_count,
        "schema_types": schema_types,
        "internal_links": internal_links,
        "keyword_hits": keyword_hits,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def crawl_competitor(domain: str, max_pages: int = 200, force: bool = False) -> list[dict]:
    """Crawl a competitor domain and return a list of page dicts.

    Results are stored in the Django cache for CACHE_TTL seconds.
    Pass ``force=True`` to bypass the cache and re-crawl.
    """
    domain = _normalise_domain(domain)
    cache_key = _cache_key(domain)

    if not force:
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(
                "competitor_crawler: cache hit for %s (%d pages)", domain, len(cached)
            )
            return cached

    logger.info(
        "competitor_crawler: starting crawl of %s (max_pages=%d)", domain, max_pages
    )

    base = _base_url(domain)
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    visited: set[str] = set()
    queue: deque[str] = deque([base])
    pages: list[dict] = []
    errors = 0

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        canonical = url.rstrip("/")
        if canonical in visited:
            continue
        visited.add(canonical)

        try:
            resp = session.get(url, timeout=_REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                continue
            if "text/html" not in resp.headers.get("Content-Type", ""):
                continue

            page = _parse_page(url, resp.text, domain)
            pages.append(page)

            for link in page["internal_links"]:
                if link.rstrip("/") not in visited:
                    queue.append(link)

            if len(pages) % 10 == 0:
                logger.info(
                    "competitor_crawler: %s — %d pages crawled so far", domain, len(pages)
                )

        except requests.RequestException as exc:
            errors += 1
            logger.warning("competitor_crawler: error fetching %s: %s", url, exc)
            if errors > 20:
                logger.error(
                    "competitor_crawler: too many consecutive errors, stopping crawl of %s",
                    domain,
                )
                break

        time.sleep(_CRAWL_DELAY)

    logger.info(
        "competitor_crawler: finished %s — %d pages, %d errors", domain, len(pages), errors
    )
    cache.set(cache_key, pages, CACHE_TTL)

    # Persist to database so data survives dyno restarts / cache expiry
    try:
        from django.utils import timezone as _tz
        from seo_intel.models import CompetitorCrawl
        CompetitorCrawl.objects.update_or_create(
            domain=domain,
            defaults={
                "crawled_at": _tz.now(),
                "page_count": len(pages),
                "pages":      pages,
            },
        )
    except Exception as exc:
        logger.warning("competitor_crawler: failed to persist crawl for %s: %s", domain, exc)

    return pages
