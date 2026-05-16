"""
seo_intel/services/competitor_keyword_gap.py
---------------------------------------------
Keyword Gap Engine.

Compares live SERP positions for a competitor domain vs LC Psych across
all tracked keywords, then layers in KeywordScore priority weighting.

Public API
----------
    get_keyword_gaps(domain: str) -> dict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_keyword_gaps(domain: str) -> dict:
    """Return a structured keyword gap report for *domain*.

    Returns dict with keys:
        domain           str
        keyword_gaps     list[dict]  – per-keyword comparison rows
        summary          dict        – aggregate stats
        has_data         bool        – False if no SERP data available
    """
    from seo_intel.models import CompetitorHit, LCPsychHit, KeywordScore
    from seo_settings.models import KeywordSeed

    # ── Best (lowest) rank per keyword for this competitor ────────────────
    comp_hits: dict[str, dict] = {}
    for hit in CompetitorHit.objects.filter(
        competitor_domain__icontains=domain
    ).values("keyword", "rank", "url", "title", "timestamp"):
        kw = hit["keyword"].lower()
        if kw not in comp_hits or hit["rank"] < comp_hits[kw]["rank"]:
            comp_hits[kw] = {
                "rank": hit["rank"],
                "url": hit["url"],
                "title": hit["title"],
                "timestamp": hit["timestamp"],
            }

    if not comp_hits:
        return {"domain": domain, "keyword_gaps": [], "summary": {}, "has_data": False}

    # ── Best LC Psych rank for the same keywords ──────────────────────────
    lc_hits: dict[str, dict] = {}
    for hit in LCPsychHit.objects.filter(
        keyword__in=list(comp_hits.keys())
    ).values("keyword", "rank", "url"):
        kw = hit["keyword"].lower()
        if kw not in lc_hits or hit["rank"] < lc_hits[kw]["rank"]:
            lc_hits[kw] = {"rank": hit["rank"], "url": hit["url"]}

    # ── Priority scores ───────────────────────────────────────────────────
    score_map: dict[str, int] = {
        row["keyword"].lower(): row["priority_score"]
        for row in KeywordScore.objects.filter(
            keyword__in=list(comp_hits.keys())
        ).values("keyword", "priority_score")
    }

    # ── Existing seeds (for "Add to Seeds" UI state) ─────────────────────
    existing_seeds: set[str] = {
        s.lower()
        for s in KeywordSeed.objects.filter(active=True).values_list("keyword", flat=True)
    }

    # ── Build gap rows ────────────────────────────────────────────────────
    rows: list[dict] = []
    for kw, comp in comp_hits.items():
        lc = lc_hits.get(kw)
        comp_rank = comp["rank"]
        lc_rank = lc["rank"] if lc else None

        if lc_rank is None:
            gap_type = "missing"
            gap_css = "action-red"
            action = "Create content targeting this keyword"
        elif lc_rank > comp_rank + 4:
            gap_type = "weak"
            gap_css = "action-yellow"
            action = f"Improve content — competitor #{comp_rank}, LC Psych #{lc_rank}"
        elif lc_rank <= comp_rank:
            gap_type = "winning"
            gap_css = "action-green"
            action = "Hold position — LC Psych leads"
        else:
            gap_type = "equal"
            gap_css = "action-gray"
            action = "Monitor — similar rank"

        rows.append({
            "keyword": kw,
            "comp_rank": comp_rank,
            "comp_url": comp["url"],
            "comp_title": comp["title"],
            "lc_rank": lc_rank,
            "lc_url": lc["url"] if lc else None,
            "gap_type": gap_type,
            "gap_css": gap_css,
            "priority_score": score_map.get(kw, 0),
            "recommended_action": action,
            "is_seed": kw in existing_seeds,
        })

    # Sort: missing first, then weak, then by priority score desc
    _order = {"missing": 0, "weak": 1, "equal": 2, "winning": 3}
    rows.sort(key=lambda r: (_order.get(r["gap_type"], 9), -r["priority_score"]))

    total = len(rows)
    missing_count = sum(1 for r in rows if r["gap_type"] == "missing")
    weak_count = sum(1 for r in rows if r["gap_type"] == "weak")
    winning_count = sum(1 for r in rows if r["gap_type"] == "winning")
    hp_gaps = sum(
        1 for r in rows
        if r["gap_type"] in ("missing", "weak") and r["priority_score"] >= 50
    )

    return {
        "domain": domain,
        "keyword_gaps": rows,
        "summary": {
            "total_keywords": total,
            "missing": missing_count,
            "weak": weak_count,
            "winning": winning_count,
            "equal": total - missing_count - weak_count - winning_count,
            "high_priority_gaps": hp_gaps,
            "gap_rate": round(100 * (missing_count + weak_count) / total) if total else 0,
        },
        "has_data": True,
    }
