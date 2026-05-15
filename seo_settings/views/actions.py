"""
seo_settings/views/actions.py
------------------------------
POST-only admin action views.  Each view:
  * requires an authenticated staff user (enforced by admin_site.admin_view wrapper)
  * calls the corresponding management command or performs a DB delete
  * returns JSON {"status": "ok"} on success or {"status": "error", "message": "..."} on failure

These functions are wired into SEOControlPanelAdmin.get_urls() in admin.py.
"""
from __future__ import annotations

import logging
import os
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def _require_post(request) -> JsonResponse | None:
    """Return a 405 response if the request is not POST, else None."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST required"}, status=405)
    return None


def _require_staff(request) -> JsonResponse | None:
    """Return a 403 JSON response if user is not authenticated staff/superuser."""
    if not request.user.is_authenticated or not (
        request.user.is_staff or request.user.is_superuser
    ):
        return JsonResponse({"status": "error", "message": "Forbidden"}, status=403)
    return None


def _run_command(*args, **kwargs) -> tuple[str, str]:
    """Run a management command, capturing stdout/stderr. Returns (stdout, stderr)."""
    out = StringIO()
    err = StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        call_command(*args, **kwargs)
    return out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Run actions
# ---------------------------------------------------------------------------

def run_search_console_pull(request) -> JsonResponse:
    """Pull Search Console search analytics via the pull_search_console command."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        stdout, stderr = _run_command("pull_search_console")
        logger.info("run_search_console_pull stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_search_console_pull stderr: %s", stderr[:500])
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("run_search_console_pull failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


def run_competitor_scrape(request) -> JsonResponse:
    """Scrape competitor SERPs via the scrape_competitors command."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        # Prefer active KeywordSeed records from the DB; fall back to a
        # keywords file only if COMPETITORS_KEYWORDS_FILE is explicitly set.
        custom_file = os.environ.get("COMPETITORS_KEYWORDS_FILE")
        if custom_file:
            if not os.path.exists(custom_file):
                msg = f"Keywords file not found: {custom_file}."
                logger.warning("run_competitor_scrape: %s", msg)
                return JsonResponse({"status": "error", "message": msg}, status=400)
            stdout, stderr = _run_command("scrape_competitors", custom_file)
        else:
            stdout, stderr = _run_command("scrape_competitors", from_db=True)
        logger.info("run_competitor_scrape stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_competitor_scrape stderr: %s", stderr[:500])
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("run_competitor_scrape failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


def run_gap_analysis(request) -> JsonResponse:
    """Run the content gap analysis via the run_gap_analysis command."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        stdout, stderr = _run_command("run_gap_analysis")
        logger.info("run_gap_analysis stdout: %s", stdout[:500])
        if stderr.strip():
            logger.warning("run_gap_analysis stderr: %s", stderr[:500])
        if request.headers.get('HX-Target'):
            return render(request, 'seo_intel/partials/_action_status.html',
                          {'status': 'ok', 'message': 'Gap analysis complete ✓'})
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("run_gap_analysis failed: %s", exc)
        if request.headers.get('HX-Target'):
            return render(request, 'seo_intel/partials/_action_status.html',
                          {'status': 'error', 'message': str(exc)})
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Clear actions
# ---------------------------------------------------------------------------

def clear_dead_urls(request) -> JsonResponse:
    """Delete all DeadURLHit records."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        from seo_intel.models import DeadURLHit
        count, _ = DeadURLHit.objects.all().delete()
        logger.info("clear_dead_urls: deleted %d records", count)
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("clear_dead_urls failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


def clear_internal_search(request) -> JsonResponse:
    """Delete all InternalSearchQuery records."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        from seo_intel.models import InternalSearchQuery
        count, _ = InternalSearchQuery.objects.all().delete()
        logger.info("clear_internal_search: deleted %d records", count)
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("clear_internal_search failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


def clear_competitor_results(request) -> JsonResponse:
    """Delete all CompetitorSERPResult records."""
    if (bad := _require_staff(request)):
        return bad
    if (bad := _require_post(request)):
        return bad
    try:
        from seo_intel.models import CompetitorSERPResult
        count, _ = CompetitorSERPResult.objects.all().delete()
        logger.info("clear_competitor_results: deleted %d records", count)
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        logger.exception("clear_competitor_results failed: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)
