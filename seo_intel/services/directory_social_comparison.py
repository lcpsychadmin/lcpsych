"""
seo_intel/services/directory_social_comparison.py
---------------------------------------------------
Comparison engine: pits a competitor's directory & social presence against
LC Psych's own profiles to identify gaps and score visibility.

Scores (all 0–100, higher = competitor is stronger / LC Psych is weaker):
  directory_gap_score   — competitor has better directory presence
  social_gap_score      — competitor has better social presence
  review_gap_score      — competitor has stronger review profile
  overall_visibility_score — weighted blend of the three

Public API
----------
    get_directory_social_comparison(domain) -> dict
    LC_PSYCH_DOMAIN: str   — derived from settings.BASE_URL
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# Derive LC Psych's own domain from BASE_URL setting
_base = getattr(settings, "BASE_URL", "") or ""
_parsed = urlparse(_base)
_hostname = _parsed.hostname or ""
LC_PSYCH_DOMAIN: str = _hostname.lstrip("www.") or "lcpsych.com"

# Weights for overall visibility score
_W_DIRECTORY = 0.40
_W_SOCIAL = 0.30
_W_REVIEW = 0.30


# ---------------------------------------------------------------------------
# Directory comparison helpers
# ---------------------------------------------------------------------------

def _platform_label(platform: str) -> str:
    from seo_intel.services.directory_scraper import PLATFORM_LABELS
    return PLATFORM_LABELS.get(platform, platform.replace("_", " ").title())


def _social_label(platform: str) -> str:
    from seo_intel.services.social_scraper import SOCIAL_PLATFORM_LABELS
    return SOCIAL_PLATFORM_LABELS.get(platform, platform.title())


def _profile_present(data: dict) -> bool:
    """True if the scraped data indicates a profile was found and is not empty."""
    if not data:
        return False
    return bool(data.get("found", False) or data.get("profile_url") or data.get("name") or data.get("channel_name"))


def _profile_completeness(data: dict) -> int:
    """Return a 0–100 completeness estimate from the scraped data dict."""
    if not _profile_present(data):
        return 0
    return int(data.get("completeness_pct") or data.get("completeness") or 50)


def _review_strength(dir_data: dict) -> dict:
    """Extract review signals from directory data (GBP preferred)."""
    gbp = dir_data.get("gbp", {})
    pt = dir_data.get("psychology_today", {})

    rating = gbp.get("rating") or pt.get("rating") or 0
    count = (
        int(gbp.get("reviews_count") or 0)
        + int(pt.get("reviews_count") or 0)
    )
    return {
        "rating": float(rating) if rating else None,
        "reviews_count": count,
        "has_gbp_reviews": bool(gbp.get("reviews_count")),
        "has_pt_reviews": bool(pt.get("reviews_count")),
    }


def _build_directory_comparison_rows(
    comp_dir: dict,
    lc_dir: dict,
) -> list[dict]:
    """Build per-platform comparison rows."""
    from seo_intel.services.directory_scraper import DIRECTORY_PLATFORMS

    rows = []
    for platform in DIRECTORY_PLATFORMS:
        comp_data = comp_dir.get(platform, {})
        lc_data = lc_dir.get(platform, {})

        comp_present = _profile_present(comp_data)
        lc_present = _profile_present(lc_data)
        comp_complete = _profile_completeness(comp_data)
        lc_complete = _profile_completeness(lc_data)

        # Status: gap / shared / lc-only / neither
        if comp_present and lc_present:
            status = "shared"
            status_label = "Both Listed"
            status_css = "dir-shared"
        elif comp_present and not lc_present:
            status = "gap"
            status_label = "Competitor Only"
            status_css = "dir-gap"
        elif not comp_present and lc_present:
            status = "lc-only"
            status_label = "LC Psych Only"
            status_css = "dir-lc"
        else:
            status = "neither"
            status_label = "Neither Listed"
            status_css = "dir-neither"

        # Advantage: who has higher completeness?
        if comp_present and lc_present:
            if comp_complete > lc_complete + 10:
                advantage = "competitor"
                advantage_label = "Competitor more complete"
            elif lc_complete > comp_complete + 10:
                advantage = "lc"
                advantage_label = "LC Psych more complete"
            else:
                advantage = "equal"
                advantage_label = "Similar completeness"
        elif comp_present:
            advantage = "competitor"
            advantage_label = "LC Psych not listed"
        elif lc_present:
            advantage = "lc"
            advantage_label = "Competitor not listed"
        else:
            advantage = "none"
            advantage_label = "No presence"

        # GBP-specific fields
        extra: dict = {}
        if platform == "gbp":
            for key in ("rating", "reviews_count", "photos_count", "address", "categories"):
                if comp_data.get(key):
                    extra[f"comp_{key}"] = comp_data[key]
                if lc_data.get(key):
                    extra[f"lc_{key}"] = lc_data[key]

        # PT-specific fields
        if platform == "psychology_today":
            extra["comp_specialties"] = comp_data.get("specialties", [])[:5]
            extra["lc_specialties"] = lc_data.get("specialties", [])[:5]
            extra["comp_insurance"] = len(comp_data.get("insurance", []))
            extra["lc_insurance"] = len(lc_data.get("insurance", []))

        rows.append({
            "platform": platform,
            "platform_label": _platform_label(platform),
            "comp_present": comp_present,
            "lc_present": lc_present,
            "comp_complete": comp_complete,
            "lc_complete": lc_complete,
            "comp_profile_url": comp_data.get("profile_url") or comp_data.get("maps_url") or "",
            "lc_profile_url": lc_data.get("profile_url") or lc_data.get("maps_url") or "",
            "status": status,
            "status_label": status_label,
            "status_css": status_css,
            "advantage": advantage,
            "advantage_label": advantage_label,
            **extra,
        })

    return rows


def _build_social_comparison_rows(
    comp_soc: dict,
    lc_soc: dict,
) -> list[dict]:
    """Build per-platform social comparison rows."""
    from seo_intel.services.social_scraper import SOCIAL_PLATFORMS

    rows = []
    for platform in SOCIAL_PLATFORMS:
        comp_data = comp_soc.get(platform, {})
        lc_data = lc_soc.get(platform, {})

        comp_present = _profile_present(comp_data)
        lc_present = _profile_present(lc_data)

        comp_followers = int(comp_data.get("followers") or comp_data.get("subscribers") or 0)
        lc_followers = int(lc_data.get("followers") or lc_data.get("subscribers") or 0)

        comp_followers_display = (
            comp_data.get("followers_display")
            or comp_data.get("subscribers_display")
            or ("N/A" if not comp_present else "?")
        )
        lc_followers_display = (
            lc_data.get("followers_display")
            or lc_data.get("subscribers_display")
            or ("N/A" if not lc_present else "?")
        )

        if comp_present and lc_present:
            status = "shared"
            status_css = "soc-shared"
            if comp_followers > lc_followers * 1.5:
                advantage = "competitor"
                advantage_label = f"Competitor: {comp_followers_display} vs {lc_followers_display}"
            elif lc_followers > comp_followers * 1.5:
                advantage = "lc"
                advantage_label = f"LC Psych: {lc_followers_display} vs {comp_followers_display}"
            else:
                advantage = "equal"
                advantage_label = "Similar audience size"
        elif comp_present:
            status = "gap"
            status_css = "soc-gap"
            advantage = "competitor"
            advantage_label = "LC Psych not present"
        elif lc_present:
            status = "lc-only"
            status_css = "soc-lc"
            advantage = "lc"
            advantage_label = "Competitor not present"
        else:
            status = "neither"
            status_css = "soc-neither"
            advantage = "none"
            advantage_label = "No presence"

        # Platform-specific extras
        extra: dict = {}
        if platform == "youtube":
            extra["comp_video_count"] = comp_data.get("video_count")
            extra["lc_video_count"] = lc_data.get("video_count")
        if platform == "instagram":
            extra["comp_post_count"] = comp_data.get("post_count")
            extra["lc_post_count"] = lc_data.get("post_count")
        if platform == "tiktok":
            extra["comp_video_count"] = comp_data.get("video_count")
            extra["lc_video_count"] = lc_data.get("video_count")

        rows.append({
            "platform": platform,
            "platform_label": _social_label(platform),
            "comp_present": comp_present,
            "lc_present": lc_present,
            "comp_followers": comp_followers,
            "lc_followers": lc_followers,
            "comp_followers_display": comp_followers_display,
            "lc_followers_display": lc_followers_display,
            "comp_profile_url": comp_data.get("profile_url") or comp_data.get("channel_url") or "",
            "lc_profile_url": lc_data.get("profile_url") or lc_data.get("channel_url") or "",
            "status": status,
            "status_css": status_css,
            "advantage": advantage,
            "advantage_label": advantage_label,
            "data_quality": comp_data.get("data_quality", "unknown"),
            **extra,
        })

    return rows


# ---------------------------------------------------------------------------
# Gap analysis & scoring
# ---------------------------------------------------------------------------

def _score_directory(comp_dir: dict, lc_dir: dict) -> int:
    """0–100: how much better the competitor's directory presence is vs LC Psych."""
    from seo_intel.services.directory_scraper import DIRECTORY_PLATFORMS

    total_advantage = 0
    max_possible = len(DIRECTORY_PLATFORMS) * 2  # present (1) + completeness delta (1)

    for platform in DIRECTORY_PLATFORMS:
        comp_data = comp_dir.get(platform, {})
        lc_data = lc_dir.get(platform, {})

        # Presence advantage
        if _profile_present(comp_data) and not _profile_present(lc_data):
            total_advantage += 1
        elif not _profile_present(comp_data) and _profile_present(lc_data):
            total_advantage -= 1

        # Completeness advantage (if both present)
        if _profile_present(comp_data) and _profile_present(lc_data):
            delta = _profile_completeness(comp_data) - _profile_completeness(lc_data)
            if delta > 20:
                total_advantage += 1
            elif delta < -20:
                total_advantage -= 1

    # Normalise to 0–100 (clamped, with 50 as neutral)
    normalised = (total_advantage / max_possible) * 50 + 50
    return max(0, min(100, int(normalised)))


def _score_social(comp_soc: dict, lc_soc: dict) -> int:
    """0–100: how much better the competitor's social presence is vs LC Psych."""
    from seo_intel.services.social_scraper import SOCIAL_PLATFORMS

    total_advantage = 0.0
    platform_count = len(SOCIAL_PLATFORMS)

    for platform in SOCIAL_PLATFORMS:
        comp_data = comp_soc.get(platform, {})
        lc_data = lc_soc.get(platform, {})
        comp_pres = _profile_present(comp_data)
        lc_pres = _profile_present(lc_data)

        if comp_pres and not lc_pres:
            total_advantage += 1.0
        elif not comp_pres and lc_pres:
            total_advantage -= 1.0
        elif comp_pres and lc_pres:
            # Compare follower counts
            comp_f = int(comp_data.get("followers") or comp_data.get("subscribers") or 0)
            lc_f = int(lc_data.get("followers") or lc_data.get("subscribers") or 0)
            if comp_f > 0 and lc_f > 0:
                ratio = comp_f / lc_f
                if ratio > 2:
                    total_advantage += 0.75
                elif ratio > 1.25:
                    total_advantage += 0.25
                elif ratio < 0.5:
                    total_advantage -= 0.75
                elif ratio < 0.8:
                    total_advantage -= 0.25

    normalised = (total_advantage / platform_count) * 50 + 50
    return max(0, min(100, int(normalised)))


def _score_reviews(comp_dir: dict, lc_dir: dict) -> int:
    """0–100: how much stronger the competitor's review profile is vs LC Psych."""
    comp_rev = _review_strength(comp_dir)
    lc_rev = _review_strength(lc_dir)

    score = 50  # neutral

    # Review count advantage
    comp_cnt = comp_rev["reviews_count"]
    lc_cnt = lc_rev["reviews_count"]
    if comp_cnt > lc_cnt:
        ratio = comp_cnt / max(lc_cnt, 1)
        score += min(25, int(ratio * 5))
    elif lc_cnt > comp_cnt:
        ratio = lc_cnt / max(comp_cnt, 1)
        score -= min(25, int(ratio * 5))

    # Rating advantage
    comp_rat = float(comp_rev["rating"] or 0)
    lc_rat = float(lc_rev["rating"] or 0)
    if comp_rat and lc_rat:
        delta = comp_rat - lc_rat
        score += int(delta * 10)
    elif comp_rat and not lc_rat:
        score += 10
    elif lc_rat and not comp_rat:
        score -= 10

    return max(0, min(100, score))


def _build_gap_analysis(
    dir_rows: list[dict],
    soc_rows: list[dict],
    scores: dict,
) -> dict:
    """Build the gap analysis and recommendations section."""
    missing_directories = [r for r in dir_rows if r["status"] == "gap"]
    weak_directories = [
        r for r in dir_rows
        if r["status"] == "shared" and r.get("advantage") == "competitor"
    ]
    missing_social = [r for r in soc_rows if r["status"] == "gap"]
    weak_social = [
        r for r in soc_rows
        if r["status"] == "shared" and r.get("advantage") == "competitor"
    ]

    recommendations: list[dict] = []

    for r in missing_directories:
        recommendations.append({
            "priority": "High",
            "priority_css": "action-red",
            "category": "directory",
            "category_label": "Directory",
            "action": f"Create {r['platform_label']} profile",
            "description": (
                f"Competitor is listed on {r['platform_label']} but LC Psych is not. "
                "Creating a profile could improve local visibility and referrals."
            ),
            "effort": "Medium",
        })

    for r in weak_directories:
        recommendations.append({
            "priority": "Medium",
            "priority_css": "action-yellow",
            "category": "directory",
            "category_label": "Directory",
            "action": f"Improve {r['platform_label']} profile completeness",
            "description": (
                f"Competitor's {r['platform_label']} profile ({r.get('comp_complete', '?')}% complete) "
                f"is more complete than LC Psych's ({r.get('lc_complete', '?')}%). "
                "Adding more specialties, modalities, photos, and insurance can close the gap."
            ),
            "effort": "Low",
        })

    for r in missing_social:
        recommendations.append({
            "priority": "Medium",
            "priority_css": "action-yellow",
            "category": "social",
            "category_label": "Social",
            "action": f"Establish {r['platform_label']} presence",
            "description": (
                f"Competitor is active on {r['platform_label']} but LC Psych has no presence. "
                "Consider whether this channel aligns with your audience."
            ),
            "effort": "High",
        })

    for r in weak_social:
        recommendations.append({
            "priority": "Low",
            "priority_css": "action-gray",
            "category": "social",
            "category_label": "Social",
            "action": f"Grow {r['platform_label']} audience",
            "description": (
                f"Competitor has significantly more followers on {r['platform_label']}. "
                "Consistent posting and engagement can help close the audience gap."
            ),
            "effort": "High",
        })

    return {
        "missing_directories": missing_directories,
        "weak_directories": weak_directories,
        "missing_social": missing_social,
        "weak_social": weak_social,
        "recommendations": recommendations,
        "total_gaps": len(missing_directories) + len(missing_social),
        "total_improvements": len(weak_directories) + len(weak_social),
    }


# ---------------------------------------------------------------------------
# Score label helpers
# ---------------------------------------------------------------------------

def _score_css(score: int) -> str:
    if score >= 65:
        return "score-low"   # competitor stronger — bad for LC Psych
    if score >= 40:
        return "score-mid"
    return "score-high"      # LC Psych stronger


def _score_label(score: int) -> str:
    if score >= 70:
        return "Competitor Leads"
    if score >= 55:
        return "Slight Competitor Edge"
    if score <= 30:
        return "LC Psych Leads"
    if score <= 45:
        return "Slight LC Psych Edge"
    return "Roughly Equal"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_directory_social_comparison(domain: str) -> dict:
    """Return a full comparison dict for *domain* vs LC Psych.

    Loads data from DB/cache via get_cached_directory_data and
    get_cached_social_data — does NOT trigger fresh scans.
    Call run_directory_scan / run_social_scan first if you want fresh data.
    """
    from seo_intel.services.directory_scraper import get_cached_directory_data
    from seo_intel.services.social_scraper import get_cached_social_data

    comp_dir = get_cached_directory_data(domain)
    lc_dir = get_cached_directory_data(LC_PSYCH_DOMAIN)

    comp_soc = get_cached_social_data(domain)
    lc_soc = get_cached_social_data(LC_PSYCH_DOMAIN)

    # Presence flags
    has_directory_data = any(_profile_present(v) for v in comp_dir.values())
    has_social_data = any(_profile_present(v) for v in comp_soc.values())
    has_lc_directory_data = any(_profile_present(v) for v in lc_dir.values())
    has_lc_social_data = any(_profile_present(v) for v in lc_soc.values())

    # Comparison rows
    dir_rows = _build_directory_comparison_rows(comp_dir, lc_dir)
    soc_rows = _build_social_comparison_rows(comp_soc, lc_soc)

    # Review panel
    comp_reviews = _review_strength(comp_dir)
    lc_reviews = _review_strength(lc_dir)

    # Scores
    dir_score = _score_directory(comp_dir, lc_dir) if has_directory_data else 50
    soc_score = _score_social(comp_soc, lc_soc) if has_social_data else 50
    rev_score = _score_reviews(comp_dir, lc_dir) if has_directory_data else 50
    overall = int(dir_score * _W_DIRECTORY + soc_score * _W_SOCIAL + rev_score * _W_REVIEW)

    scores = {
        "directory_gap_score": dir_score,
        "social_gap_score": soc_score,
        "review_gap_score": rev_score,
        "overall_visibility_score": overall,
        "directory_css": _score_css(dir_score),
        "social_css": _score_css(soc_score),
        "review_css": _score_css(rev_score),
        "overall_css": _score_css(overall),
        "directory_label": _score_label(dir_score),
        "social_label": _score_label(soc_score),
        "review_label": _score_label(rev_score),
        "overall_label": _score_label(overall),
    }

    # Gap analysis
    gap_analysis = _build_gap_analysis(dir_rows, soc_rows, scores)

    return {
        "domain": domain,
        "lc_domain": LC_PSYCH_DOMAIN,
        "has_directory_data": has_directory_data,
        "has_social_data": has_social_data,
        "has_lc_directory_data": has_lc_directory_data,
        "has_lc_social_data": has_lc_social_data,
        "directory_comparison": dir_rows,
        "social_comparison": soc_rows,
        "comp_reviews": comp_reviews,
        "lc_reviews": lc_reviews,
        "scores": scores,
        "gap_analysis": gap_analysis,
    }
