"""
seo_intel/views/actions.py
----------------------------
POST-only action views for the SERP Intelligence pipeline.

Covers the management commands added in the seo_intel app that are not
already handled by seo_settings/views/actions.py:
  • run_serpapi_for_seeds — fetches SERPs for active keyword seeds
  • score_keywords        — scores all keywords and upserts KeywordScore rows

All views:
  * Require an authenticated staff / superuser (returns 401/403 JSON on failure)
  * Accept POST only (returns 405 JSON otherwise)
  * Call the management command synchronously and capture output
  * Return JSON {"status": "ok"} on success or {"status": "error", "message": "..."} on failure
"""
from __future__ import annotations

import logging
from contextlib import redirect_stderr, redirect_stdout
from functools import wraps
from io import StringIO

from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared guards
# ---------------------------------------------------------------------------

def _require_staff_post(view_func):
    """Decorator: enforce authenticated-staff + POST-only. Returns JSON on failure."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Login required"}, status=401)
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)
        if request.method != "POST":
            return JsonResponse({"status": "error", "message": "POST required"}, status=405)
        return view_func(request, *args, **kwargs)
    return wrapper


def _run_command(*args, **kwargs) -> tuple[str, str]:
    """Run a management command capturing stdout/stderr. Returns (stdout, stderr)."""
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        call_command(*args, **kwargs)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Action: run_serpapi_for_seeds
# ---------------------------------------------------------------------------

@_require_staff_post
def run_serpapi(request) -> JsonResponse:
    """Trigger run_serpapi_for_seeds for active keyword seeds.

    Accepts an optional ``limit`` POST parameter (int, clamped to 1–50,
    defaults to 5) so ad-hoc runs from the dashboard don't hammer the API.
    """
    try:
        raw_limit = request.POST.get("limit", "5")
        try:
            limit = max(1, min(int(raw_limit), 50))
        except (TypeError, ValueError):
            limit = 5

        stdout, stderr = _run_command("run_serpapi_for_seeds", limit=limit)
        logger.info("run_serpapi stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_serpapi stderr: %s", stderr[:500])
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("run_serpapi failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: score_keywords
# ---------------------------------------------------------------------------

@_require_staff_post
def score_keywords(request) -> JsonResponse:
    """Trigger score_keywords — scores / upserts KeywordScore for every seed."""
    try:
        stdout, stderr = _run_command("score_keywords")
        logger.info("score_keywords stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("score_keywords stderr: %s", stderr[:500])
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("score_keywords failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: run_serpapi_for_discovered
# ---------------------------------------------------------------------------

@_require_staff_post
def run_serpapi_for_discovered(request) -> JsonResponse:
    """Run SerpApi for discovered keywords not yet in the seed list.

    Accepts optional POST parameters:
        limit       int  — max keywords to process (default 25, max 50)
        min_priority int — only keywords with priority_score >= this (default 0)
        source      str  — filter to one discovery source
        stale_days  int  — skip keywords fetched within this many days (default 7)
    """
    try:
        raw_limit = request.POST.get("limit", "25")
        try:
            limit = max(1, min(int(raw_limit), 50))
        except (TypeError, ValueError):
            limit = 25

        raw_min = request.POST.get("min_priority", "0")
        try:
            min_priority = max(0, int(raw_min))
        except (TypeError, ValueError):
            min_priority = 0

        raw_stale = request.POST.get("stale_days", "7")
        try:
            stale_days = max(0, int(raw_stale))
        except (TypeError, ValueError):
            stale_days = 7

        source = request.POST.get("source", "").strip() or None

        kwargs: dict = {
            "limit": limit,
            "min_priority": min_priority,
            "stale_days": stale_days,
        }
        if source:
            kwargs["source"] = source

        stdout, stderr = _run_command("run_serpapi_for_discovered", **kwargs)
        logger.info("run_serpapi_for_discovered stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_serpapi_for_discovered stderr: %s", stderr[:500])

        # Parse processed / error counts from command output for the response
        import re
        m = re.search(r"Processed:\s*(\d+)\s+Errors:\s*(\d+)", stdout)
        processed = int(m.group(1)) if m else 0
        errors    = int(m.group(2)) if m else 0

        return JsonResponse({
            "status": "ok",
            "processed": processed,
            "errors": errors,
            "output": stdout[-1000:],   # last 1 KB for debugging
        })
    except Exception as exc:
        logger.exception("run_serpapi_for_discovered failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: run_serpapi_selected  (batch fetch for manually-chosen keywords)
# ---------------------------------------------------------------------------

@_require_staff_post
def run_serpapi_selected(request) -> JsonResponse:
    """Run SerpApi for a caller-supplied list of keywords.

    Accepts ``keywords`` POST param — a comma-separated string of keyword phrases.
    Calls the serpapi_client functions directly (same as run_serpapi_for_keyword)
    so results are available immediately in the response without a subprocess.
    Invalidates the discovery cache on completion.
    """
    import time as _time

    raw_keywords = request.POST.get("keywords", "")
    keywords = [kw.strip() for kw in raw_keywords.split(",") if kw.strip()]

    if not keywords:
        return JsonResponse(
            {"status": "error", "message": "No keywords provided."},
            status=400,
        )

    # Hard cap to protect API credits
    MAX_BATCH = 50
    if len(keywords) > MAX_BATCH:
        keywords = keywords[:MAX_BATCH]

    try:
        from django.utils import timezone

        from seo_intel.models import CompetitorHit, LCPsychHit, SerpRawResult
        from seo_intel.services.keyword_discovery import invalidate_cache
        from seo_intel.services.serpapi_client import (
            detect_competitor_hits,
            detect_lcpsych_hits,
            fetch_serp,
            parse_serp,
        )

        ok_count  = 0
        err_count = 0
        detail: list[dict] = []

        for i, kw in enumerate(keywords):
            try:
                raw    = fetch_serp(kw)
                parsed = parse_serp(kw, raw)
                now    = timezone.now()

                SerpRawResult.objects.create(
                    keyword=kw,
                    payload={"raw": raw, "parsed": parsed},
                )

                comp_hits = detect_competitor_hits(kw, parsed["organic"])
                for hit in comp_hits:
                    CompetitorHit.objects.create(
                        keyword=kw,
                        competitor_domain=hit["competitor_domain"],
                        url=hit["url"],
                        title=hit.get("title", ""),
                        rank=hit["rank"],
                        timestamp=now,
                    )

                lc_hits = detect_lcpsych_hits(kw, parsed["organic"])
                for hit in lc_hits:
                    LCPsychHit.objects.create(
                        keyword=kw,
                        url=hit["url"],
                        title=hit.get("title", ""),
                        rank=hit["rank"],
                        timestamp=now,
                    )

                detail.append({
                    "keyword": kw,
                    "organic": len(parsed["organic"]),
                    "competitors": len(comp_hits),
                    "lc_hits": len(lc_hits),
                })
                ok_count += 1
                logger.info(
                    "run_serpapi_selected: %r — %d organic, %d comp, %d lc",
                    kw, len(parsed["organic"]), len(comp_hits), len(lc_hits),
                )
            except Exception as exc:
                logger.exception("run_serpapi_selected failed for %r: %s", kw, exc)
                err_count += 1

            # Brief delay between calls to be a polite API consumer
            if i < len(keywords) - 1:
                _time.sleep(1.5)

        invalidate_cache()

        return JsonResponse({
            "status": "ok",
            "processed": ok_count,
            "errors": err_count,
            "detail": detail,
        })
    except Exception as exc:
        logger.exception("run_serpapi_selected outer error: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: run_serpapi_for_keyword  (single-keyword fetch from SERP Explorer)
# ---------------------------------------------------------------------------

@_require_staff_post
def run_serpapi_for_keyword(request) -> JsonResponse:
    """Fetch a fresh SERP for a single keyword and persist the results.

    Accepts a required ``keyword`` POST parameter.  Calls the serpapi service
    functions directly (no management command wrapper) so the response returns
    once the fetch is complete, keeping the caller informed of errors.
    """
    keyword = request.POST.get("keyword", "").strip()
    if not keyword:
        return JsonResponse(
            {"status": "error", "message": "keyword parameter is required"},
            status=400,
        )

    try:
        from django.utils import timezone
        from seo_intel.models import CompetitorHit, LCPsychHit, SerpRawResult
        from seo_intel.services.serpapi_client import (
            detect_competitor_hits,
            detect_lcpsych_hits,
            fetch_serp,
            parse_serp,
        )

        raw = fetch_serp(keyword)
        parsed = parse_serp(keyword, raw)
        now = timezone.now()

        SerpRawResult.objects.create(
            keyword=keyword,
            payload={"raw": raw, "parsed": parsed},
        )

        comp_hits = detect_competitor_hits(keyword, parsed["organic"])
        for hit in comp_hits:
            CompetitorHit.objects.create(
                keyword=keyword,
                competitor_domain=hit["competitor_domain"],
                url=hit["url"],
                title=hit.get("title", ""),
                rank=hit["rank"],
                timestamp=now,
            )

        lc_hits = detect_lcpsych_hits(keyword, parsed["organic"])
        for hit in lc_hits:
            LCPsychHit.objects.create(
                keyword=keyword,
                url=hit["url"],
                title=hit.get("title", ""),
                rank=hit["rank"],
                timestamp=now,
            )

        organic_count = len(parsed.get("organic", []))
        logger.info(
            "run_serpapi_for_keyword: %r — %d organic, %d comp hits, %d lc hits",
            keyword, organic_count, len(comp_hits), len(lc_hits),
        )
        if request.headers.get('HX-Request'):
            return render(request, 'seo_intel/partials/_action_status.html', {
                'status': 'ok',
                'message': f'Fetched: {organic_count} organic, {len(comp_hits)} competitor, {len(lc_hits)} LC hits ✓',
            })
        return JsonResponse({
            "status": "ok",
            "organic_count": organic_count,
            "comp_hits": len(comp_hits),
            "lc_hits": len(lc_hits),
        })
    except Exception as exc:
        logger.exception("run_serpapi_for_keyword failed for %r: %s", keyword, exc)
        if request.headers.get('HX-Request'):
            return render(request, 'seo_intel/partials/_action_status.html',
                          {'status': 'error', 'message': str(exc)})
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)
