"""
seo_intel/tasks.py
-------------------
Celery tasks for the weekly SEO intelligence automation pipeline.

Pipeline (run in sequence, each task independent):
    1. pull_gsc_data          — pull_search_console management command
    2. scrape_competitor_serp — scrape_competitors management command
    3. analyse_content_gaps   — run_gap_analysis management command

Each task:
  - Captures stdout/stderr from the management command
  - Logs the output via Python logging
  - Sends a summary email to SEO_INTEL_ADMIN_EMAIL

Weekly beat schedule
--------------------
The schedule is registered via CELERY_BEAT_SCHEDULE (see below) and stored in
the database via django-celery-beat. Tasks are chained: gap analysis only runs
after both data-collection tasks have completed.

Schedule:
  Monday 06:00 UTC — pull_gsc_data     (GSC data ready ~2–3 days after weekend)
  Monday 06:10 UTC — scrape_competitor_serp  (10-minute offset to spread load)
  Monday 06:30 UTC — analyse_content_gaps    (30-minute offset, runs after both)

Env vars
--------
  SEO_INTEL_ADMIN_EMAIL   Recipient for summary emails (default: DEFAULT_FROM_EMAIL)
  COMPETITORS_KEYWORDS_FILE  Path to keywords.txt for scrape_competitors
                              (default: keywords.txt in the repo root)
"""

from __future__ import annotations

import io
import logging
import os
from contextlib import redirect_stderr, redirect_stdout

from celery import shared_task
from celery.schedules import crontab
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Beat schedule — imported by lcpsych/celery.py via app.conf.beat_schedule
# ---------------------------------------------------------------------------

BEAT_SCHEDULE = {
    # Step 1: Pull fresh GSC data (Monday 06:00 UTC)
    "seo-intel-pull-gsc-weekly": {
        "task": "seo_intel.tasks.pull_gsc_data",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),
    },
    # Step 2: Scrape competitor SERPs (Monday 06:10 UTC)
    "seo-intel-scrape-serp-weekly": {
        "task": "seo_intel.tasks.scrape_competitor_serp",
        "schedule": crontab(hour=6, minute=10, day_of_week=1),
    },
    # Step 3: Content gap analysis (Monday 06:30 UTC — after both data tasks)
    "seo-intel-gap-analysis-weekly": {
        "task": "seo_intel.tasks.analyse_content_gaps",
        "schedule": crontab(hour=6, minute=30, day_of_week=1),
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _capture_command(*args, **kwargs) -> tuple[str, str]:
    """
    Run a management command and capture its stdout + stderr output.

    Returns (stdout_text, stderr_text).
    """
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        call_command(*args, **kwargs)
    return out_buf.getvalue(), err_buf.getvalue()


def _send_summary_email(subject: str, body: str) -> None:
    """Send a plain-text summary email to the SEO Intel admin address."""
    recipient = getattr(settings, "SEO_INTEL_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)
    if not recipient:
        logger.warning("SEO_INTEL_ADMIN_EMAIL not set; skipping summary email.")
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("Failed to send SEO intel summary email: %s", exc)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="seo_intel.tasks.pull_gsc_data", max_retries=2, default_retry_delay=300)
def pull_gsc_data(self, days: int = 7, row_limit: int = 1000):
    """
    Pull Search Console search analytics for the last `days` days.
    Wraps the pull_search_console management command.
    """
    logger.info("SEO Intel: starting pull_gsc_data (days=%d, row_limit=%d)", days, row_limit)
    try:
        stdout, stderr = _capture_command(
            "pull_search_console",
            days=days,
            row_limit=row_limit,
        )
    except Exception as exc:
        logger.exception("pull_gsc_data failed: %s", exc)
        _send_summary_email(
            subject="[SEO Intel] pull_gsc_data FAILED",
            body=f"Task failed with exception:\n{exc}\n",
        )
        raise self.retry(exc=exc)

    output = stdout + (f"\nSTDERR:\n{stderr}" if stderr.strip() else "")
    logger.info("pull_gsc_data output:\n%s", output)
    _send_summary_email(
        subject="[SEO Intel] GSC data pull complete",
        body=output or "(no output)",
    )
    return output


@shared_task(bind=True, name="seo_intel.tasks.scrape_competitor_serp", max_retries=2, default_retry_delay=300)
def scrape_competitor_serp(self, results: int = 10, delay: float = 1.5):
    """
    Scrape competitor SERP results for keywords listed in the keywords file.
    Wraps the scrape_competitors management command.

    The keywords file path is read from the COMPETITORS_KEYWORDS_FILE env var;
    defaults to 'keywords.txt' in the project root.
    """
    keywords_file = os.environ.get(
        "COMPETITORS_KEYWORDS_FILE",
        os.path.join(settings.BASE_DIR, "keywords.txt"),
    )

    if not os.path.exists(keywords_file):
        msg = (
            f"Keywords file not found: {keywords_file}\n"
            "Create it or set COMPETITORS_KEYWORDS_FILE env var.\n"
            "Skipping scrape_competitor_serp task."
        )
        logger.warning(msg)
        _send_summary_email(
            subject="[SEO Intel] SERP scrape skipped — no keywords file",
            body=msg,
        )
        return msg

    logger.info("SEO Intel: starting scrape_competitor_serp (file=%s)", keywords_file)
    try:
        stdout, stderr = _capture_command(
            "scrape_competitors",
            keywords_file=keywords_file,
            results=results,
            delay=delay,
        )
    except Exception as exc:
        logger.exception("scrape_competitor_serp failed: %s", exc)
        _send_summary_email(
            subject="[SEO Intel] SERP scrape FAILED",
            body=f"Task failed with exception:\n{exc}\n",
        )
        raise self.retry(exc=exc)

    output = stdout + (f"\nSTDERR:\n{stderr}" if stderr.strip() else "")
    logger.info("scrape_competitor_serp output:\n%s", output)
    _send_summary_email(
        subject="[SEO Intel] SERP scrape complete",
        body=output or "(no output)",
    )
    return output


@shared_task(bind=True, name="seo_intel.tasks.analyse_content_gaps", max_retries=2, default_retry_delay=300)
def analyse_content_gaps(self, min_impressions: int = 0):
    """
    Run the content gap analysis engine and save results to ContentGapRecord.
    Wraps the run_gap_analysis management command.
    """
    logger.info("SEO Intel: starting analyse_content_gaps (min_impressions=%d)", min_impressions)
    try:
        stdout, stderr = _capture_command(
            "run_gap_analysis",
            min_impressions=min_impressions,
            show_gaps=True,
            top=50,
        )
    except Exception as exc:
        logger.exception("analyse_content_gaps failed: %s", exc)
        _send_summary_email(
            subject="[SEO Intel] Content gap analysis FAILED",
            body=f"Task failed with exception:\n{exc}\n",
        )
        raise self.retry(exc=exc)

    output = stdout + (f"\nSTDERR:\n{stderr}" if stderr.strip() else "")
    logger.info("analyse_content_gaps output:\n%s", output)
    _send_summary_email(
        subject="[SEO Intel] Content gap analysis complete",
        body=output or "(no output)",
    )
    return output
