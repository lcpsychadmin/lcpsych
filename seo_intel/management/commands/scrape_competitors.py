"""
Management command: scrape_competitors
---------------------------------------
Reads a keyword list file and scrapes top SERP results for each keyword
using the Google Custom Search JSON API, storing results in CompetitorSERPResult.

Usage
-----
    python manage.py scrape_competitors keywords.txt
    python manage.py scrape_competitors keywords.txt --delay 3.0
    python manage.py scrape_competitors keywords.txt --results 10 --dry-run

Keyword file format
-------------------
One keyword per line. Lines starting with # are treated as comments and skipped.
Blank lines are skipped.

Example keywords.txt:
    # Therapy keywords
    therapist near me
    anxiety therapist los angeles
    # Depression keywords
    depression treatment california

Required env vars
-----------------
    GOOGLE_CSE_API_KEY   — Google API key with Custom Search API enabled
    GOOGLE_CSE_ID        — Programmable Search Engine ID (cx)

Rate limits
-----------
The Google Custom Search JSON API allows 100 free queries/day.
The default --delay of 1.5 seconds between keywords keeps bursts under
control and avoids HTTP 429 responses. Each keyword costs 1 quota unit
(2 if requesting >10 results).
"""

from __future__ import annotations

import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Scrape Google SERP for a list of keywords and save to CompetitorSERPResult."

    def add_arguments(self, parser):
        parser.add_argument(
            "keywords_file",
            type=str,
            help="Path to a text file with one keyword per line (#-prefixed lines are comments).",
        )
        parser.add_argument(
            "--results",
            type=int,
            default=10,
            metavar="N",
            help="Number of SERP results to fetch per keyword (default: 10, max: 20).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
            metavar="SECONDS",
            help="Seconds to wait between keyword requests (default: 1.5).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse the keyword file and print what would be scraped, but make no API calls.",
        )

    def handle(self, *args, **options):
        from seo_intel.services.serp_scraper import scrape_keyword, save_serp_results

        keywords_path = Path(options["keywords_file"])
        if not keywords_path.exists():
            raise CommandError(f"Keywords file not found: {keywords_path}")

        # Parse keywords file
        raw_lines = keywords_path.read_text(encoding="utf-8").splitlines()
        keywords = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.strip().startswith("#")
        ]

        if not keywords:
            raise CommandError(f"No keywords found in {keywords_path}")

        self.stdout.write(
            f"Found {len(keywords)} keyword(s) in {keywords_path.name}."
        )

        if options["dry_run"]:
            for i, kw in enumerate(keywords, 1):
                self.stdout.write(f"  [{i:>3}] {kw}")
            self.stdout.write(self.style.WARNING("Dry run — no API calls made."))
            return

        num_results: int = min(options["results"], 20)
        delay: float = options["delay"]

        total_created = 0
        total_updated = 0
        total_errors = 0

        for i, keyword in enumerate(keywords, 1):
            prefix = f"[{i}/{len(keywords)}]"
            self.stdout.write(f"{prefix} Scraping: {keyword!r} …", ending="")
            self.stdout.flush()

            try:
                rows = scrape_keyword(keyword, num_results=num_results)
                created, updated = save_serp_results(keyword, rows)
                total_created += created
                total_updated += updated
                self.stdout.write(
                    f" {len(rows)} results → "
                    f"{created} created, {updated} updated"
                )
            except Exception as exc:
                total_errors += 1
                self.stdout.write("")  # newline after the …
                self.stderr.write(
                    self.style.ERROR(f"  ERROR scraping {keyword!r}: {exc}")
                )

            # Rate-limit — skip sleep after the last keyword
            if i < len(keywords):
                time.sleep(delay)

        self.stdout.write("")
        if total_errors:
            self.stdout.write(
                self.style.WARNING(
                    f"Completed with {total_errors} error(s).  "
                    f"Created: {total_created}  Updated: {total_updated}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Created: {total_created}  Updated: {total_updated}  "
                    f"Total stored: {total_created + total_updated}"
                )
            )
