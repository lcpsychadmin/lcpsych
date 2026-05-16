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
import threading
import time as _time
import uuid
from functools import wraps
from io import StringIO

from django.core.management import call_command
from django.db import connections
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
    call_command(*args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# In-process job registry for long-running background tasks
# ---------------------------------------------------------------------------

# job_id -> {status, _ts, [processed, errors, message, output, ...]}
_jobs: dict[str, dict] = {}


def _start_job(fn, *args) -> str:
    """Spawn fn(job_id, *args) in a daemon thread. Returns the new job_id."""
    now = _time.time()
    # Prune finished jobs older than 1 hour
    stale = [jid for jid, j in list(_jobs.items()) if now - j.get("_ts", now) > 3600]
    for jid in stale:
        _jobs.pop(jid, None)

    job_id = uuid.uuid4().hex
    _jobs[job_id] = {"status": "running", "_ts": now}
    t = threading.Thread(target=fn, args=(job_id, *args), daemon=True)
    t.start()
    return job_id


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
# Action: run_competitor_crawl
# ---------------------------------------------------------------------------

def _bg_run_competitor_crawl(job_id: str, domain: str, limit: int) -> None:
    from seo_intel.services.competitor_crawler import crawl_competitor, invalidate_crawl
    try:
        invalidate_crawl(domain)
        pages = crawl_competitor(domain, max_pages=limit, force=True)
        logger.info("run_competitor_crawl: %s — %d pages crawled", domain, len(pages))
        _jobs[job_id] = {
            "status": "done",
            "pages":  len(pages),
            "_ts":    _time.time(),
        }
    except BaseException as exc:
        logger.exception("run_competitor_crawl bg failed for %s: %s", domain, exc)
        _jobs[job_id] = {"status": "error", "message": str(exc), "_ts": _time.time()}
    finally:
        connections.close_all()


@_require_staff_post
def run_competitor_crawl(request) -> JsonResponse:
    """Queue a background crawl for a single competitor domain.

    Returns {"status": "queued", "job_id": "..."} immediately.
    Poll actions/job-status/<job_id>/ to track completion.
    """
    from seo_intel.services.competitor_crawler import crawl_competitor, invalidate_crawl  # noqa: F401

    domain = request.POST.get("domain", "").strip()
    if not domain:
        return JsonResponse({"status": "error", "message": "domain is required"}, status=400)

    try:
        raw_limit = request.POST.get("limit", "50")
        try:
            limit = max(1, min(int(raw_limit), 200))
        except (TypeError, ValueError):
            limit = 50

        job_id = _start_job(_bg_run_competitor_crawl, domain, limit)
        return JsonResponse({"status": "queued", "job_id": job_id})
    except Exception as exc:
        logger.exception("run_competitor_crawl failed for %s: %s", domain, exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: run_serpapi_for_discovered
# ---------------------------------------------------------------------------

def _bg_run_serpapi_for_discovered(job_id: str, kwargs: dict) -> None:
    import re
    try:
        stdout, stderr = _run_command("run_serpapi_for_discovered", **kwargs)
        logger.info("run_serpapi_for_discovered stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_serpapi_for_discovered stderr: %s", stderr[:500])
        m = re.search(r"Processed:\s*(\d+)\s+Errors:\s*(\d+)", stdout)
        processed = int(m.group(1)) if m else 0
        errors    = int(m.group(2)) if m else 0
        _jobs[job_id] = {
            "status":    "done",
            "processed": processed,
            "errors":    errors,
            "output":    stdout[-1000:],
            "_ts":       _time.time(),
        }
    except BaseException as exc:
        logger.exception("run_serpapi_for_discovered bg failed: %s", exc)
        _jobs[job_id] = {"status": "error", "message": str(exc), "_ts": _time.time()}
    finally:
        connections.close_all()


@_require_staff_post
def run_serpapi_for_discovered(request) -> JsonResponse:
    """Queue a background SerpApi run for discovered keywords.

    Returns {"status": "queued", "job_id": "..."} immediately.
    Poll actions/job-status/<job_id>/ to track completion.

    Accepts optional POST parameters:
        limit        int  — max keywords to process (default 25, max 50)
        min_priority int  — only keywords with priority_score >= this (default 0)
        source       str  — filter to one discovery source
        stale_days   int  — skip keywords fetched within this many days (default 7)
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
            "limit":        limit,
            "min_priority": min_priority,
            "stale_days":   stale_days,
        }
        if source:
            kwargs["source"] = source

        job_id = _start_job(_bg_run_serpapi_for_discovered, kwargs)
        return JsonResponse({"status": "queued", "job_id": job_id})
    except Exception as exc:
        logger.exception("run_serpapi_for_discovered failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Action: run_serpapi_selected  (batch fetch for manually-chosen keywords)
# ---------------------------------------------------------------------------

def _bg_run_serpapi_selected(job_id: str, keywords: list[str]) -> None:
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
        logger.info("run_serpapi_selected starting for %d keyword(s)", len(keywords))

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
                    "keyword":     kw,
                    "organic":     len(parsed["organic"]),
                    "competitors": len(comp_hits),
                    "lc_hits":     len(lc_hits),
                })
                ok_count += 1
                logger.info(
                    "run_serpapi_selected: %r — %d organic, %d comp, %d lc",
                    kw, len(parsed["organic"]), len(comp_hits), len(lc_hits),
                )
            except Exception as exc:
                logger.exception("run_serpapi_selected failed for %r: %s", kw, exc)
                err_count += 1

            if i < len(keywords) - 1:
                _time.sleep(1.5)

        invalidate_cache()
        _jobs[job_id] = {
            "status":    "done",
            "processed": ok_count,
            "errors":    err_count,
            "detail":    detail,
            "_ts":       _time.time(),
        }
    except BaseException as exc:
        logger.exception("run_serpapi_selected bg failed: %s", exc)
        _jobs[job_id] = {"status": "error", "message": str(exc), "_ts": _time.time()}
    finally:
        connections.close_all()


@_require_staff_post
def run_serpapi_selected(request) -> JsonResponse:
    """Queue a background SerpApi run for a caller-supplied list of keywords.

    Returns {"status": "queued", "job_id": "..."} immediately.
    Poll actions/job-status/<job_id>/ to track completion.
    """
    raw_keywords = request.POST.get("keywords", "")
    keywords = [kw.strip() for kw in raw_keywords.split(",") if kw.strip()]

    if not keywords:
        return JsonResponse(
            {"status": "error", "message": "No keywords provided."},
            status=400,
        )

    MAX_BATCH = 50
    if len(keywords) > MAX_BATCH:
        keywords = keywords[:MAX_BATCH]

    job_id = _start_job(_bg_run_serpapi_selected, keywords)
    return JsonResponse({"status": "queued", "job_id": job_id})


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


# ---------------------------------------------------------------------------
# Action: poll_job_status  (GET — check background job progress)
# ---------------------------------------------------------------------------

def poll_job_status(request, job_id: str) -> JsonResponse:
    """Return the current status of a background job.

    Response shapes:
        {"status": "running"}
        {"status": "done", "processed": N, "errors": N, ...}
        {"status": "error", "message": "..."}
        {"status": "unknown"}  — job_id not found (may have expired)
    """
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Login required"}, status=401)
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)

    job = dict(_jobs.get(job_id, {"status": "unknown"}))
    job.pop("_ts", None)   # internal field — don't expose
    job.pop("detail", None)  # potentially large — omit from poll responses
    return JsonResponse(job)
