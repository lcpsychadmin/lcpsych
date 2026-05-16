"""
seo_intel/services/keyword_discovery.py
-----------------------------------------
Keyword Discovery Engine.

Identifies keyword opportunities *beyond* the existing KeywordSeed list by
aggregating signals from five local data sources — no live SerpAPI calls.

Sources
-------
A. SearchConsoleQuery  — rising queries, high-impression non-seeds, zero-click
B. KeywordSuggestion   — PAA and related-search expansions from past SERP runs
C. CompetitorHit       — keywords competitors rank for that LC Psych doesn't
D. InternalSearchQuery — site search terms not in the seed list
E. DeadURLHit          — 404 URL paths that imply missing service/location pages

Results are cached for 15 minutes (configurable via _CACHE_TTL).

Public API
----------
    run_discovery() -> list[dict]
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, timedelta
from urllib.parse import urlparse

from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

_CACHE_KEY = "kw_discovery_v1"
_CACHE_TTL  = 60 * 15   # 15 minutes

# ── Source identifiers ────────────────────────────────────────────────────
SRC_SC         = "search_console"
SRC_PAA        = "paa"
SRC_RELATED    = "related"
SRC_COMPETITOR = "competitor"
SRC_INTERNAL   = "internal"
SRC_DEAD_URL   = "dead_url"

SOURCE_LABELS: dict[str, str] = {
    SRC_SC:         "Search Console",
    SRC_PAA:        "People Also Ask",
    SRC_RELATED:    "Related Search",
    SRC_COMPETITOR: "Competitor Gap",
    SRC_INTERNAL:   "Internal Search",
    SRC_DEAD_URL:   "Dead URL",
}

SOURCE_CSS: dict[str, str] = {
    SRC_SC:         "src-sc",
    SRC_PAA:        "src-paa",
    SRC_RELATED:    "src-related",
    SRC_COMPETITOR: "src-competitor",
    SRC_INTERNAL:   "src-internal",
    SRC_DEAD_URL:   "src-deadurl",
}

# ── Vocabulary (mirrors keyword_scoring / keyword_trends_analyzer) ─────────

_LOCAL_TERMS: frozenset[str] = frozenset(
    {
        "florence", "covington", "newport", "erlanger", "lexington",
        "cincinnati", "northern kentucky", "nky", "kentucky", "ohio",
        "bellevue", "dayton", "fort mitchell", "fort thomas",
        "highland heights", "independence", "union", "burlington",
        "boone county", "campbell county", "kenton county", "ky", "oh",
        "near me",
    }
)

_COMMERCIAL_TERMS: frozenset[str] = frozenset(
    {
        "therapy", "therapist", "counseling", "counselor",
        "psychologist", "psychiatrist", "psychiatric",
        "testing", "evaluation", "assessment", "diagnosis",
        "treatment", "adhd", "autism", "anxiety", "depression",
        "trauma", "ocd", "ptsd", "telehealth", "neurodivergent",
        "executive functioning", "somatic", "perinatal", "postpartum",
        "burnout", "ketamine", "appointment", "session",
    }
)

# URL path segments to skip for dead-URL extraction
_SKIP_URL_SEGMENTS: frozenset[str] = frozenset(
    {
        "services", "therapists", "team", "about", "blog", "posts",
        "page", "wp-content", "wp-admin", "admin", "static", "media",
        "contact", "locations", "geo", "category", "tag", "feed",
        "sitemap", "robots", "favicon", "apple-touch-icon",
    }
)

# Min / max keyword phrase length to accept
_KW_MIN_WORDS = 2
_KW_MAX_WORDS = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_local(kw: str) -> bool:
    kw_l = kw.lower()
    return any(t in kw_l for t in _LOCAL_TERMS)


def _has_commercial(kw: str) -> bool:
    kw_l = kw.lower()
    return any(t in kw_l for t in _COMMERCIAL_TERMS)


def _word_count(kw: str) -> int:
    return len(kw.split())


def _is_plausible_keyword(kw: str) -> bool:
    """Return True if the phrase looks like a real search query."""
    wc = _word_count(kw)
    if wc < _KW_MIN_WORDS or wc > _KW_MAX_WORDS:
        return False
    if len(kw) < 6:
        return False
    # Skip if it's mostly numbers
    if sum(c.isdigit() for c in kw) > len(kw) // 2:
        return False
    return True


def _recommended_action(
    lc_rank: int | None,
    competitor_rank: int | None,
    has_local: bool,
    category: str = "",
) -> tuple[str, str]:
    """Return (action_label, css_key)."""
    if lc_rank is None:
        if competitor_rank is not None and competitor_rank <= 3:
            return "Create page — urgent", "red"
        if not has_local:
            return "Add local landing page", "blue"
        if category == "testing":
            return "Add testing page", "purple"
        if category == "modality":
            return "Add modality page", "purple"
        return "Create new page", "orange"
    if lc_rank <= 3:
        return "Strengthen content", "green"
    if lc_rank <= 10:
        return "Optimize existing page", "yellow"
    return "Optimize existing page — low ranking", "amber"


def _priority_score(
    impressions_7d: int,
    competitor_count: int,
    lc_rank: int | None,
    has_local: bool,
    has_commercial: bool,
) -> int:
    # Search demand (0-25): log-scaled impressions
    import math
    if impressions_7d > 0:
        sd = min(25, int(math.log10(impressions_7d + 1) * 8))
    else:
        sd = 0

    # Competitor pressure (0-25)
    cp = min(25, competitor_count * 5)

    # LC Psych presence (0-25)
    if lc_rank is None:
        lp = 20  # opportunity: not ranking at all
    elif lc_rank <= 3:
        lp = 5   # already winning, less opportunity
    elif lc_rank <= 10:
        lp = 15
    else:
        lp = 20

    # Local intent (0-15)
    li = 15 if has_local else 0

    # Commercial intent (0-10)
    ci = 10 if has_commercial else 0

    return min(100, sd + cp + lp + li + ci)


def _score_css(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "mid"
    if score > 0:
        return "low"
    return "none"


def _build_entry(
    keyword: str,
    source: str,
    *,
    source_detail: str = "",
    impressions_7d: int = 0,
    impressions_prev_7d: int = 0,
    competitor_domains: list[str] | None = None,
    top_competitor_rank: int | None = None,
    lc_rank: int | None = None,
    category: str = "",
) -> dict:
    competitor_domains = competitor_domains or []
    has_local      = _has_local(keyword)
    has_commercial = _has_commercial(keyword)
    score          = _priority_score(
        impressions_7d, len(competitor_domains), lc_rank, has_local, has_commercial
    )
    action, action_css = _recommended_action(
        lc_rank, top_competitor_rank, has_local, category
    )

    # Trend
    if impressions_prev_7d == 0 and impressions_7d == 0:
        trend_direction = "neutral"
        trend_pct       = 0.0
        trend_label     = "no data"
    elif impressions_prev_7d == 0:
        trend_direction = "up"
        trend_pct       = 100.0
        trend_label     = "↑ new signal"
    else:
        pct = (impressions_7d - impressions_prev_7d) / impressions_prev_7d * 100
        trend_pct = round(pct, 1)
        if pct > 5:
            trend_direction, trend_label = "up",      f"↑ +{pct:.0f}%"
        elif pct < -5:
            trend_direction, trend_label = "down",    f"↓ {pct:.0f}%"
        else:
            trend_direction, trend_label = "neutral", f"→ {pct:+.0f}%"

    return {
        "keyword":              keyword,
        "keyword_lower":        keyword.lower(),
        "source":               source,
        "sources":              [source],          # may grow via _merge
        "source_label":         SOURCE_LABELS[source],
        "source_css":           SOURCE_CSS[source],
        "source_detail":        source_detail,
        # GSC
        "impressions_7d":       impressions_7d,
        "impressions_prev_7d":  impressions_prev_7d,
        "trend_direction":      trend_direction,
        "trend_pct":            trend_pct,
        "trend_label":          trend_label,
        # SERP
        "competitor_domains":   competitor_domains,
        "competitor_count":     len(competitor_domains),
        "top_competitor_rank":  top_competitor_rank,
        "lc_rank":              lc_rank,
        # Scores
        "priority_score":       score,
        "score_css":            _score_css(score),
        # Intent
        "has_local":            has_local,
        "has_commercial":       has_commercial,
        # Action
        "recommended_action":   action,
        "action_css":           action_css,
        # Category (may be inferred)
        "category":             category or ("location" if has_local else
                                              "testing"  if "testing" in keyword.lower() or "evaluation" in keyword.lower() else
                                              "service"),
    }


def _merge(pool: dict[str, dict], entry: dict) -> None:
    """Upsert an entry into the dedup pool; keep highest score, union sources."""
    key = entry["keyword_lower"]
    if key not in pool:
        pool[key] = entry
        return
    existing = pool[key]
    # Union sources
    merged_sources = list({*existing["sources"], *entry["sources"]})
    existing["sources"] = merged_sources
    existing["source_label"] = " + ".join(SOURCE_LABELS[s] for s in merged_sources)
    # Keep the higher priority score
    if entry["priority_score"] > existing["priority_score"]:
        existing["priority_score"] = entry["priority_score"]
        existing["score_css"]       = entry["score_css"]
    # Prefer richer SERP data
    if entry["impressions_7d"] > existing["impressions_7d"]:
        existing["impressions_7d"]      = entry["impressions_7d"]
        existing["impressions_prev_7d"] = entry["impressions_prev_7d"]
        existing["trend_direction"]     = entry["trend_direction"]
        existing["trend_pct"]           = entry["trend_pct"]
        existing["trend_label"]         = entry["trend_label"]
    if entry["competitor_domains"]:
        combined = list({*existing["competitor_domains"], *entry["competitor_domains"]})
        existing["competitor_domains"] = combined
        existing["competitor_count"]   = len(combined)
    if entry["lc_rank"] is not None and (
        existing["lc_rank"] is None or entry["lc_rank"] < existing["lc_rank"]
    ):
        existing["lc_rank"] = entry["lc_rank"]


# ---------------------------------------------------------------------------
# Source A: Search Console
# ---------------------------------------------------------------------------

def _from_search_console(existing_seeds: set[str]) -> list[dict]:
    """
    Yield keyword opportunities from SearchConsoleQuery:
      1. Rising queries (last 7d vs prior 7d, delta > 10%)
      2. High-impression queries not in seeds
      3. Zero-click queries (impressions > 5, clicks == 0)
    """
    from seo_intel.models import SearchConsoleQuery

    today    = date.today()
    wk_end   = today - timedelta(days=1)
    wk_start = today - timedelta(days=7)
    prev_end = today - timedelta(days=8)
    prev_start = today - timedelta(days=14)

    # Aggregate last-7d
    recent = (
        SearchConsoleQuery.objects
        .filter(date__gte=wk_start, date__lte=wk_end)
        .values("query")
        .annotate(
            impressions=Sum("impressions"),
            clicks=Sum("clicks"),
        )
    )
    recent_map: dict[str, dict] = {
        r["query"].lower(): r for r in recent
    }

    # Aggregate prior-7d
    prior = (
        SearchConsoleQuery.objects
        .filter(date__gte=prev_start, date__lte=prev_end)
        .values("query")
        .annotate(impressions=Sum("impressions"))
    )
    prior_map: dict[str, int] = {
        p["query"].lower(): p["impressions"] for p in prior
    }

    results: list[dict] = []
    seen: set[str] = set()

    for kw_lower, r in recent_map.items():
        kw       = r["query"]
        impr     = r["impressions"] or 0
        clicks   = r["clicks"] or 0
        prev_i   = prior_map.get(kw_lower, 0)

        # Skip if already a seed
        if kw_lower in existing_seeds:
            continue
        # Skip very short / single-word queries
        if not _is_plausible_keyword(kw):
            continue
        if kw_lower in seen:
            continue
        seen.add(kw_lower)

        # Classify signal
        if prev_i == 0 and impr > 0:
            detail = "breakout — new impressions"
        elif prev_i > 0:
            delta = (impr - prev_i) / prev_i * 100
            if delta < 10:
                # Only include if high-impression or zero-click opportunity
                if impr < 20 and clicks > 0:
                    continue
                if impr >= 20:
                    detail = f"high impression ({impr} impr)"
                elif clicks == 0 and impr >= 5:
                    detail = f"zero-click ({impr} impr, 0 clicks)"
                else:
                    continue
            else:
                detail = f"rising +{delta:.0f}%"
        else:
            continue

        entry = _build_entry(
            kw,
            SRC_SC,
            source_detail=detail,
            impressions_7d=impr,
            impressions_prev_7d=prev_i,
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Source B: SerpAPI Expansions (PAA + Related + Organic title phrases)
# ---------------------------------------------------------------------------

def _from_serpapi_expansions(existing_seeds: set[str]) -> list[dict]:
    """
    Yield keyword opportunities from stored KeywordSuggestion records
    (PAA and related searches captured during previous SERP runs).
    Also extracts phrase candidates from SerpRawResult organic titles.
    """
    from seo_intel.models import KeywordSuggestion, SerpRawResult

    results: list[dict] = []
    seen: set[str] = set()

    # ── PAA and Related ──────────────────────────────────────────────────
    for s in KeywordSuggestion.objects.filter(used_as_seed=False):
        kw      = s.suggestion.strip()
        kw_lower = kw.lower()
        if kw_lower in existing_seeds or kw_lower in seen:
            continue
        if not _is_plausible_keyword(kw):
            continue
        seen.add(kw_lower)
        source = SRC_PAA if s.source_type == KeywordSuggestion.PAA else SRC_RELATED
        entry  = _build_entry(
            kw,
            source,
            source_detail=f"from seed: {s.source_keyword}",
        )
        results.append(entry)

    # ── Organic title phrase extraction ─────────────────────────────────
    _STOPWORDS = frozenset(
        "a an the and or but in on at to for of with is are was were be been being "
        "have has had do does did will would could should may might shall can "
        "our we you your it its this that these those i me my".split()
    )

    def _phrases_from_title(title: str) -> list[str]:
        """Extract 2-4 word meaningful sub-phrases from an organic title."""
        # Clean separators
        clean = re.sub(r"[|•–—/]", " ", title)
        clean = re.sub(r"\s+", " ", clean).strip()
        words = [w.strip(",:;.\"'()[]") for w in clean.split()]
        phrases = []
        for size in (4, 3, 2):
            for i in range(len(words) - size + 1):
                chunk = words[i : i + size]
                # Skip if starts or ends with stopword
                if chunk[0].lower() in _STOPWORDS or chunk[-1].lower() in _STOPWORDS:
                    continue
                phrase = " ".join(chunk)
                if _is_plausible_keyword(phrase):
                    phrases.append(phrase)
        return phrases

    recent_serps = SerpRawResult.objects.order_by("-timestamp")[:100]
    for serp_rec in recent_serps:
        parsed = serp_rec.payload.get("parsed", {}) if isinstance(serp_rec.payload, dict) else {}
        organic = parsed.get("organic", [])
        for result in organic[:5]:  # top 5 results only
            title = result.get("title", "")
            if not title:
                continue
            for phrase in _phrases_from_title(title):
                kw_lower = phrase.lower()
                if kw_lower in existing_seeds or kw_lower in seen:
                    continue
                if not (_has_local(phrase) or _has_commercial(phrase)):
                    continue
                seen.add(kw_lower)
                entry = _build_entry(
                    phrase,
                    SRC_RELATED,
                    source_detail=f"organic title: {title[:50]}",
                )
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Source C: Competitor gaps
# ---------------------------------------------------------------------------

def _from_competitors(existing_seeds: set[str]) -> list[dict]:
    """
    Keywords where competitors appear in SERP but LC Psych does not.
    Also flags keywords where competitors dominate the top 3.
    """
    from seo_intel.models import CompetitorHit, LCPsychHit

    cutoff = timezone.now() - timedelta(days=90)

    # All keywords with competitor hits (recent)
    competitor_keywords = set(
        CompetitorHit.objects
        .filter(timestamp__gte=cutoff)
        .values_list("keyword", flat=True)
        .distinct()
    )

    # LC Psych ranks by keyword
    lc_ranks: dict[str, int] = {}
    for hit in LCPsychHit.objects.filter(timestamp__gte=cutoff).order_by("rank"):
        kl = hit.keyword.lower()
        if kl not in lc_ranks:
            lc_ranks[kl] = hit.rank

    results: list[dict] = []
    seen: set[str] = set()

    for kw in competitor_keywords:
        kw_lower = kw.lower()
        if kw_lower in existing_seeds or kw_lower in seen:
            continue
        if not _is_plausible_keyword(kw):
            continue
        seen.add(kw_lower)

        # Gather competitor domains + best rank
        comp_hits = (
            CompetitorHit.objects
            .filter(keyword__iexact=kw, timestamp__gte=cutoff)
            .order_by("rank")
            .values("competitor_domain", "rank")
        )
        domains_seen: set[str] = set()
        domains: list[str] = []
        top_rank: int | None = None
        top3_count = 0
        for h in comp_hits:
            d, r = h["competitor_domain"], h["rank"]
            if d not in domains_seen:
                domains_seen.add(d)
                domains.append(d)
                if top_rank is None:
                    top_rank = r
                if r <= 3:
                    top3_count += 1

        lc_rank = lc_ranks.get(kw_lower)

        detail = []
        if lc_rank is None:
            detail.append("LC Psych not ranking")
        if top3_count >= 2:
            detail.append(f"{top3_count} competitors in top 3")

        entry = _build_entry(
            kw,
            SRC_COMPETITOR,
            source_detail=", ".join(detail) if detail else f"{len(domains)} competitors",
            competitor_domains=domains,
            top_competitor_rank=top_rank,
            lc_rank=lc_rank,
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Source D: Internal search
# ---------------------------------------------------------------------------

def _from_internal_search(existing_seeds: set[str]) -> list[dict]:
    """Terms typed into the site's own search that are not in the seed list."""
    from seo_intel.models import InternalSearchQuery

    cutoff = timezone.now() - timedelta(days=90)
    terms  = (
        InternalSearchQuery.objects
        .filter(timestamp__gte=cutoff)
        .values("term")
        .annotate(count=Count("id"))
        .filter(count__gte=2)   # at least 2 users searched for it
        .order_by("-count")
    )

    results: list[dict] = []
    seen: set[str] = set()
    for row in terms:
        kw      = row["term"].strip()
        kw_lower = kw.lower()
        if kw_lower in existing_seeds or kw_lower in seen:
            continue
        if not _is_plausible_keyword(kw):
            continue
        seen.add(kw_lower)
        entry = _build_entry(
            kw,
            SRC_INTERNAL,
            source_detail=f"searched {row['count']}× on site",
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Source E: Dead URL patterns
# ---------------------------------------------------------------------------

def _extract_keyword_from_path(path: str) -> str | None:
    """
    Convert a URL path segment to a keyword candidate.
    e.g. '/services/adhd-testing-covington-ky/' → 'adhd testing covington ky'
    """
    segments = [s for s in path.strip("/").split("/") if s]
    if not segments:
        return None
    # Take the last substantive segment (skip known prefixes)
    for seg in reversed(segments):
        if seg.lower() in _SKIP_URL_SEGMENTS:
            continue
        # Remove file extensions
        seg = re.sub(r"\.\w{2,5}$", "", seg)
        # Convert separators to spaces
        kw = re.sub(r"[-_]+", " ", seg).strip().lower()
        if _is_plausible_keyword(kw):
            return kw
    return None


def _from_dead_urls(existing_seeds: set[str]) -> list[dict]:
    """Extract keyword candidates from 404 URL paths."""
    from seo_intel.models import DeadURLHit

    cutoff = timezone.now() - timedelta(days=90)
    hits   = (
        DeadURLHit.objects
        .filter(timestamp__gte=cutoff)
        .values("url")
        .annotate(count=Count("id"))
        .filter(count__gte=2)
        .order_by("-count")
    )

    results: list[dict] = []
    seen: set[str] = set()
    for row in hits:
        url  = row["url"]
        path = urlparse(url).path
        kw   = _extract_keyword_from_path(path)
        if not kw:
            continue
        kw_lower = kw.lower()
        if kw_lower in existing_seeds or kw_lower in seen:
            continue
        seen.add(kw_lower)
        entry = _build_entry(
            kw,
            SRC_DEAD_URL,
            source_detail=f"404 hit {row['count']}× — {url[:60]}",
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_discovery(*, force: bool = False) -> list[dict]:
    """
    Run the full discovery pipeline and return a scored, deduplicated list
    of keyword opportunities not already in the KeywordSeed list.

    Results are cached for 15 minutes.  Pass ``force=True`` to bypass cache.
    """
    if not force:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            logger.debug("keyword_discovery: cache hit (%d items)", len(cached))
            return cached

    from seo_settings.models import KeywordSeed

    existing_seeds: set[str] = {
        kw.lower()
        for kw in KeywordSeed.objects.values_list("keyword", flat=True)
    }

    pool: dict[str, dict] = {}

    for entry in _from_search_console(existing_seeds):
        _merge(pool, entry)
    for entry in _from_serpapi_expansions(existing_seeds):
        _merge(pool, entry)
    for entry in _from_competitors(existing_seeds):
        _merge(pool, entry)
    for entry in _from_internal_search(existing_seeds):
        _merge(pool, entry)
    for entry in _from_dead_urls(existing_seeds):
        _merge(pool, entry)

    results = list(pool.values())

    # Final sort: priority_score desc, then keyword alpha
    results.sort(key=lambda r: (-r["priority_score"], r["keyword"].lower()))

    cache.set(_CACHE_KEY, results, _CACHE_TTL)
    logger.info("keyword_discovery: found %d opportunities", len(results))
    return results


def invalidate_cache() -> None:
    """Delete the discovery cache (call after adding/removing seeds)."""
    cache.delete(_CACHE_KEY)
