"""
seo_intel/management/commands/run_serpapi_for_discovered.py
------------------------------------------------------------
Fetch Google SERPs (via SerpApi) for keywords surfaced by the Keyword
Discovery Engine that are NOT yet in the KeywordSeed list.

Populates the same tables as run_serpapi_for_seeds:
    • SerpRawResult     — raw JSON response
    • CompetitorHit     — competitor domains found in organic results
    • LCPsychHit        — LC Psych's own positions in organic results
    • KeywordSuggestion — PAA and related search phrases

After completion the discovery cache is invalidated so the Keyword Discovery
page reflects the fresh rank data on the next page load.

Usage
-----
    python manage.py run_serpapi_for_discovered
    python manage.py run_serpapi_for_discovered --limit 20
    python manage.py run_serpapi_for_discovered --min-priority 50
    python manage.py run_serpapi_for_discovered --source competitor
    python manage.py run_serpapi_for_discovered --dry-run

Flags
-----
--limit N            Process at most N keywords (default: 25).
--min-priority N     Only process keywords with a discovery priority_score >= N
                     (default: 0 — all).
--source SRC         Filter to a single discovery source:
                     search_console | paa | related | competitor |
                     internal | dead_url
--stale-days N       Re-fetch keywords whose last SERP run is older than N days
                     (default: 7 — skip keywords fetched within the last week).
--dry-run            Print keywords that would be processed without calling
                     the API.
--delay SECS         Seconds to pause between API calls (default: 1.5).
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch Google SERPs for Keyword Discovery results via SerpApi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            metavar="N",
            help="Cap the number of keywords processed (default: 25).",
        )
        parser.add_argument(
            "--min-priority",
            type=int,
            default=0,
            metavar="N",
            help="Only process keywords with priority_score >= N (default: 0).",
        )
        parser.add_argument(
            "--source",
            default=None,
            metavar="SRC",
            help=(
                "Filter to a single source: search_console, paa, related, "
                "competitor, internal, dead_url"
            ),
        )
        parser.add_argument(
            "--stale-days",
            type=int,
            default=7,
            metavar="N",
            help=(
                "Skip keywords fetched within the last N days (default: 7). "
                "Use 0 to re-fetch all."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print keywords without calling the API.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
            metavar="SECS",
            help="Seconds to pause between API calls (default: 1.5).",
        )

    def handle(self, *args, **options):
        from seo_intel.models import (
            CompetitorHit,
            KeywordSuggestion,
            LCPsychHit,
            SerpRawResult,
        )
        from seo_intel.services.keyword_discovery import invalidate_cache, run_discovery
        from seo_intel.services.serpapi_client import (
            detect_competitor_hits,
            detect_lcpsych_hits,
            fetch_serp,
            parse_serp,
        )

        limit: int        = options["limit"]
        min_priority: int = options["min_priority"]
        source_filter: str | None = options["source"]
        stale_days: int   = options["stale_days"]
        dry_run: bool     = options["dry_run"]
        delay: float      = options["delay"]

        # ── 1. Get discovery results ─────────────────────────────────────────
        self.stdout.write("Running keyword discovery …")
        discovered = run_discovery(force=True)

        # ── 2. Apply filters ─────────────────────────────────────────────────
        if source_filter:
            discovered = [d for d in discovered if d["source"] == source_filter]

        if min_priority:
            discovered = [d for d in discovered if d["priority_score"] >= min_priority]

        # ── 3. Determine which keywords are "stale" (need a fresh SERP) ──────
        if stale_days > 0:
            cutoff = timezone.now() - timedelta(days=stale_days)
            recently_fetched: set[str] = set(
                SerpRawResult.objects.filter(timestamp__gte=cutoff)
                .values_list("keyword", flat=True)
                .distinct()
            )
            recently_fetched_lower = {kw.lower() for kw in recently_fetched}
            discovered = [
                d for d in discovered
                if d["keyword"].lower() not in recently_fetched_lower
            ]

        # Sort by priority descending, then cap
        discovered.sort(key=lambda d: d["priority_score"], reverse=True)
        discovered = discovered[:limit]

        total = len(discovered)

        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No discovered keywords to process "
                    "(all may be recently fetched or filtered out)."
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"DRY RUN — {total} keyword(s) would be processed:\n"
                )
            )
            for d in discovered:
                self.stdout.write(
                    f"  [{d['priority_score']:>3} pri] [{d['source']:<14}] {d['keyword']}"
                )
            return

        self.stdout.write(f"Processing {total} discovered keyword(s) …\n")

        ok_count  = 0
        err_count = 0
        errors: list[tuple[str, str]] = []

        for idx, entry in enumerate(discovered, start=1):
            kw = entry["keyword"]
            self.stdout.write(f"[{idx}/{total}] Fetching: '{kw}' … ", ending="")
            self.stdout.flush()

            try:
                raw    = fetch_serp(kw)
                parsed = parse_serp(kw, raw)
                now    = timezone.now()

                # Raw result
                SerpRawResult.objects.create(
                    keyword=kw,
                    payload={"raw": raw, "parsed": parsed},
                )

                # Competitor hits
                comp_hits = detect_competitor_hits(kw, parsed["organic"])
                for hit in comp_hits:
                    CompetitorHit.objects.create(
                        keyword=hit["keyword"],
                        competitor_domain=hit["competitor_domain"],
                        url=hit["url"],
                        title=hit["title"],
                        rank=hit["rank"],
                        timestamp=now,
                    )

                # LC Psych own hits
                own_hits = detect_lcpsych_hits(kw, parsed["organic"])
                for hit in own_hits:
                    LCPsychHit.objects.create(
                        keyword=hit["keyword"],
                        url=hit["url"],
                        title=hit["title"],
                        rank=hit["rank"],
                        timestamp=now,
                    )

                # PAA + related suggestions
                new_suggestions = 0
                for question in parsed["people_also_ask"]:
                    phrase = question.strip().lower()
                    if phrase:
                        _, created = KeywordSuggestion.objects.get_or_create(
                            suggestion=phrase,
                            defaults={
                                "source_keyword": kw,
                                "source_type": KeywordSuggestion.PAA,
                            },
                        )
                        if created:
                            new_suggestions += 1

                for query in parsed["related_searches"]:
                    phrase = query.strip().lower()
                    if phrase:
                        _, created = KeywordSuggestion.objects.get_or_create(
                            suggestion=phrase,
                            defaults={
                                "source_keyword": kw,
                                "source_type": KeywordSuggestion.RELATED,
                            },
                        )
                        if created:
                            new_suggestions += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK  ({len(parsed['organic'])} organic, "
                        f"{len(comp_hits)} competitor hit(s), "
                        f"{len(own_hits)} own hit(s), "
                        f"{new_suggestions} new suggestion(s))"
                    )
                )
                ok_count += 1

            except Exception as exc:
                msg = str(exc)
                self.stdout.write(self.style.ERROR(f"ERROR — {msg}"))
                errors.append((kw, msg))
                err_count += 1

            if idx < total:
                time.sleep(delay)

        # ── 4. Invalidate discovery cache so fresh rank data appears ────────
        invalidate_cache()
        self.stdout.write("\nDiscovery cache invalidated.")

        # ── 5. Summary ───────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(
            self.style.SUCCESS(f"Done.  Processed: {ok_count}  Errors: {err_count}")
        )
        if errors:
            self.stdout.write(self.style.ERROR("\nFailed keywords:"))
            for kw, msg in errors:
                self.stdout.write(f"  • '{kw}': {msg}")
