"""
seo_intel/services/competitor_modality_testing.py
---------------------------------------------------
Modality & Testing Coverage Engine.

Compares which therapy modalities and testing services a competitor
advertises (from crawled pages) versus what LC Psych offers (from seed
keywords).

Public API
----------
    get_modality_testing(domain: str) -> dict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ── Curated modality items: (match_keyword, display_label, group) ─────────
_MODALITY_ITEMS: list[tuple[str, str, str]] = [
    # Evidence-Based
    ("cbt",                       "Cognitive Behavioral Therapy (CBT)",   "Evidence-Based"),
    ("cognitive behavioral",      "Cognitive Behavioral",                  "Evidence-Based"),
    ("dbt",                       "Dialectical Behavior Therapy (DBT)",    "Evidence-Based"),
    ("dialectical",               "Dialectical Behavioral",                "Evidence-Based"),
    # Trauma
    ("emdr",                      "EMDR",                                  "Trauma"),
    ("cpt",                       "Cognitive Processing Therapy (CPT)",    "Trauma"),
    ("prolonged exposure",        "Prolonged Exposure",                    "Trauma"),
    ("trauma-focused",            "Trauma-Focused",                        "Trauma"),
    ("trauma-informed",           "Trauma-Informed",                       "Trauma"),
    # Third Wave
    ("act",                       "Acceptance & Commitment (ACT)",         "Third Wave"),
    ("acceptance and commitment", "Acceptance & Commitment (ACT)",         "Third Wave"),
    ("mindfulness",               "Mindfulness-Based",                     "Third Wave"),
    ("mbct",                      "MBCT",                                  "Third Wave"),
    # Depth / Relational
    ("psychodynamic",             "Psychodynamic",                         "Depth"),
    ("psychoanalytic",            "Psychoanalytic",                        "Depth"),
    ("attachment-based",          "Attachment-Based",                      "Relational"),
    ("attachment based",          "Attachment-Based",                      "Relational"),
    ("gottman",                   "Gottman Method",                        "Relational"),
    ("emotionally focused",       "Emotionally Focused (EFT)",             "Relational"),
    ("internal family systems",   "Internal Family Systems (IFS)",         "Parts-Based"),
    # Somatic / Expressive
    ("somatic",                   "Somatic / Body-Based",                  "Somatic"),
    ("play therapy",              "Play Therapy",                          "Child/Expressive"),
    ("art therapy",               "Art Therapy",                           "Child/Expressive"),
    # Brief / Behavioral
    ("solution focused",          "Solution-Focused (SFBT)",               "Brief"),
    ("motivational interviewing", "Motivational Interviewing",             "Brief"),
    ("exposure therapy",          "Exposure Therapy",                      "Behavioral"),
    ("behavioral activation",     "Behavioral Activation",                 "Behavioral"),
    # Systemic
    ("family systems",            "Family Systems",                        "Systemic"),
    ("narrative therapy",         "Narrative Therapy",                     "Systemic"),
    ("interpersonal therapy",     "Interpersonal Therapy (IPT)",           "Systemic"),
]


# ── Curated testing items: (match_keyword, display_label, group) ──────────
_TESTING_ITEMS: list[tuple[str, str, str]] = [
    # Developmental
    ("adhd testing",                   "ADHD Testing",                      "Developmental"),
    ("adhd assessment",                "ADHD Assessment",                   "Developmental"),
    ("adhd evaluation",                "ADHD Evaluation",                   "Developmental"),
    ("autism testing",                 "Autism Testing",                    "Developmental"),
    ("autism evaluation",              "Autism Evaluation",                 "Developmental"),
    ("asd testing",                    "ASD Testing",                       "Developmental"),
    ("asd evaluation",                 "ASD Evaluation",                    "Developmental"),
    # Core
    ("psychological testing",         "Psychological Testing",             "Core"),
    ("psychological evaluation",      "Psychological Evaluation",          "Core"),
    ("diagnostic evaluation",         "Diagnostic Evaluation",             "Core"),
    ("diagnostic testing",            "Diagnostic Testing",                "Core"),
    # Neuropsychological
    ("neuropsychological testing",    "Neuropsychological Testing",        "Neuro"),
    ("neuropsychological evaluation", "Neuropsychological Evaluation",     "Neuro"),
    ("neuropsychology",               "Neuropsychology",                   "Neuro"),
    # Cognitive
    ("cognitive assessment",          "Cognitive Assessment",              "Cognitive"),
    ("cognitive testing",             "Cognitive Testing",                 "Cognitive"),
    ("iq testing",                    "IQ Testing",                        "Cognitive"),
    # Academic
    ("psychoeducational evaluation",  "Psychoeducational Evaluation",      "Academic"),
    ("learning disability",           "Learning Disability Eval",          "Academic"),
    ("gifted testing",                "Gifted Testing",                    "Academic"),
    ("academic testing",              "Academic Testing",                  "Academic"),
    # Clinical
    ("personality testing",           "Personality Testing",               "Clinical"),
    ("personality assessment",        "Personality Assessment",            "Clinical"),
    ("behavioral assessment",         "Behavioral Assessment",             "Clinical"),
]


def _comp_kw_counts(pages: list[dict], category: str) -> dict[str, int]:
    """Return {keyword: page_count} for *category* keyword hits across pages."""
    counts: dict[str, int] = {}
    for page in pages:
        for kw in page.get("keyword_hits", {}).get(category, []):
            kl = kw.lower()
            counts[kl] = counts.get(kl, 0) + 1
    return counts


def _lc_seed_kws(seed_category: str) -> set[str]:
    """Return lowercased active seed keywords for *seed_category*."""
    try:
        from seo_settings.models import KeywordSeed
        return {
            kw.lower()
            for kw in KeywordSeed.objects.filter(
                active=True, category=seed_category
            ).values_list("keyword", flat=True)
        }
    except Exception:
        logger.debug("modality_testing: could not load KeywordSeed", exc_info=True)
        return set()


def _build_matrix(
    items: list[tuple[str, str, str]],
    comp_counts: dict[str, int],
    lc_kws: set[str],
) -> list[dict]:
    """Build a comparison matrix row for each unique (match_key, label, group)."""
    seen_labels: set[str] = set()
    rows: list[dict] = []
    for match_kw, label, group in items:
        if label in seen_labels:
            continue
        seen_labels.add(label)

        # Competitor: keyword or any comp_count key contains match_kw (or vice-versa)
        comp_count = sum(
            v for k, v in comp_counts.items()
            if match_kw in k or k in match_kw
        )
        has_comp = comp_count > 0

        # LC Psych: any seed contains match_kw (or vice-versa)
        has_lc = any(match_kw in seed or seed in match_kw for seed in lc_kws)

        if has_comp and has_lc:
            status, css = "both", "score-high"
        elif has_comp:
            status, css = "competitor-only", "score-low"
        elif has_lc:
            status, css = "lc-only", "score-mid"
        else:
            status, css = "neither", "score-none"

        rows.append({
            "keyword": match_kw,
            "label": label,
            "group": group,
            "competitor_count": comp_count,
            "has_competitor": has_comp,
            "has_lc": has_lc,
            "status": status,
            "status_css": css,
        })
    return rows


def _summarise(matrix: list[dict]) -> dict:
    total = len(matrix)
    comp_has = sum(1 for r in matrix if r["has_competitor"])
    lc_has = sum(1 for r in matrix if r["has_lc"])
    gaps = sum(1 for r in matrix if r["status"] == "competitor-only")
    both = sum(1 for r in matrix if r["status"] == "both")
    return {
        "total_items": total,
        "competitor_count": comp_has,
        "lcpsych_count": lc_has,
        "gap_count": gaps,
        "shared_count": both,
        "comp_pct": round(100 * comp_has / total) if total else 0,
        "lc_pct": round(100 * lc_has / total) if total else 0,
    }


def get_modality_testing(domain: str) -> dict:
    """Return modality and testing coverage comparison for *domain*.

    Returns dict with keys:
        domain              str
        has_data            bool
        modality_matrix     list[dict]
        testing_matrix      list[dict]
        modality_summary    dict
        testing_summary     dict
        recommendations     list[dict]
    """
    from seo_intel.services.competitor_crawler import get_cached_crawl

    pages = get_cached_crawl(domain) or []
    if not pages:
        return {
            "domain": domain,
            "has_data": False,
            "modality_matrix": [],
            "testing_matrix": [],
            "modality_summary": {},
            "testing_summary": {},
            "recommendations": [],
        }

    comp_mod = _comp_kw_counts(pages, "modalities")
    comp_test = _comp_kw_counts(pages, "testing")
    lc_mod = _lc_seed_kws("modality")
    lc_test = _lc_seed_kws("testing")

    modality_matrix = _build_matrix(_MODALITY_ITEMS, comp_mod, lc_mod)
    testing_matrix = _build_matrix(_TESTING_ITEMS, comp_test, lc_test)

    # Sort: competitor-only gaps first
    _order = {"competitor-only": 0, "both": 1, "lc-only": 2, "neither": 3}
    modality_matrix.sort(key=lambda r: _order[r["status"]])
    testing_matrix.sort(key=lambda r: _order[r["status"]])

    mod_summary = _summarise(modality_matrix)
    test_summary = _summarise(testing_matrix)

    # Recommendations
    recs: list[dict] = []
    for row in modality_matrix:
        if row["status"] == "competitor-only":
            recs.append({
                "category": "modality",
                "item": row["label"],
                "action": f"Add {row['label']} page",
                "priority": "High",
                "priority_css": "action-red",
                "description": (
                    f"Competitor advertises {row['label']} across "
                    f"{row['competitor_count']} page(s) — LC Psych has no matching seed or page."
                ),
            })
    for row in testing_matrix:
        if row["status"] == "competitor-only":
            recs.append({
                "category": "testing",
                "item": row["label"],
                "action": f"Add {row['label']} page",
                "priority": "High",
                "priority_css": "action-red",
                "description": (
                    f"Competitor promotes {row['label']} across "
                    f"{row['competitor_count']} page(s) — LC Psych has no matching seed or page."
                ),
            })

    return {
        "domain": domain,
        "has_data": True,
        "modality_matrix": modality_matrix,
        "testing_matrix": testing_matrix,
        "modality_summary": mod_summary,
        "testing_summary": test_summary,
        "recommendations": recs[:25],
    }
