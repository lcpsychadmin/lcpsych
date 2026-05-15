"""
seo_intel/management/commands/run_serpapi_for_seeds.py
---------------------------------------------------------
Fetch Google SERPs (via SerpApi) for every active KeywordSeed and store the
raw JSON in SerpRawResult.

Usage
-----
    python manage.py run_serpapi_for_seeds
    python manage.py run_serpapi_for_seeds --limit 10
    python manage.py run_serpapi_for_seeds --category service
    python manage.py run_serpapi_for_seeds --dry-run

Flags
-----
--limit N        Process at most N keywords (useful for testing with the
                 free tier's 100-search quota).
--category CAT   Only process seeds with this category
                 (service | testing | modality | location).
--dry-run        Print keywords that would be processed without calling
                 the API.
--delay SECS     Seconds to wait between API calls (default: 1.5).
"""

from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch Google SERPs for active KeywordSeed records via SerpApi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            metavar="N",
            help="Cap the number of keywords processed (default: all).",
        )
        parser.add_argument(
            "--category",
            default=None,
            metavar="CAT",
            help="Filter to a single category: service, testing, modality, location.",
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
        from django.utils import timezone
        from seo_intel.models import CompetitorHit, KeywordSuggestion, LCPsychHit, SerpRawResult
        from seo_intel.services.serpapi_client import (
            detect_competitor_hits,
            detect_lcpsych_hits,
            fetch_serp,
            parse_serp,
        )
        from seo_settings.models import KeywordSeed

        dry_run: bool = options["dry_run"]
        limit: int | None = options["limit"]
        category: str | None = options["category"]
        delay: float = options["delay"]

        # --- Load seeds ---
        qs = KeywordSeed.objects.filter(active=True).order_by("category", "keyword")
        if category:
            qs = qs.filter(category=category)
        if limit:
            qs = qs[:limit]

        seeds = list(qs)
        total = len(seeds)

        if total == 0:
            self.stdout.write(self.style.WARNING("No active keyword seeds found."))
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f"DRY RUN — {total} keyword(s) would be processed:\n")
            )
            for seed in seeds:
                self.stdout.write(f"  [{seed.category}] {seed.keyword}")
            return

        self.stdout.write(f"Processing {total} keyword seed(s) …\n")

        ok_count = 0
        err_count = 0
        errors: list[tuple[str, str]] = []

        for idx, seed in enumerate(seeds, start=1):
            kw = seed.keyword
            self.stdout.write(f"[{idx}/{total}] Fetching: '{kw}' … ", ending="")
            self.stdout.flush()

            try:
                raw = fetch_serp(kw)
                parsed = parse_serp(kw, raw)

                now = timezone.now()

                SerpRawResult.objects.create(
                    keyword=kw,
                    payload={
                        "raw": raw,
                        "parsed": parsed,
                    },
                )

                # Detect and persist competitor hits
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

                # Detect and persist LC Psych own hits
                own_hits = detect_lcpsych_hits(kw, parsed["organic"])
                for hit in own_hits:
                    LCPsychHit.objects.create(
                        keyword=hit["keyword"],
                        url=hit["url"],
                        title=hit["title"],
                        rank=hit["rank"],
                        timestamp=now,
                    )

                organic_count = len(parsed["organic"])
                paa_count = len(parsed["people_also_ask"])
                rs_count = len(parsed["related_searches"])

                # Save PAA and related search phrases as keyword suggestions
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
                        f"OK  ({organic_count} organic, {paa_count} PAA, "
                        f"{rs_count} related, "
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

        # --- Summary ---
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(
            self.style.SUCCESS(f"Done.  Processed: {ok_count}  Errors: {err_count}")
        )
        if errors:
            self.stdout.write(self.style.ERROR("\nFailed keywords:"))
            for kw, msg in errors:
                self.stdout.write(f"  • '{kw}': {msg}")
