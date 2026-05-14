"""
Management command: run_gap_analysis
--------------------------------------
Runs the content gap analysis engine and prints a summary of results.

Usage
-----
    python manage.py run_gap_analysis
    python manage.py run_gap_analysis --min-impressions 10
    python manage.py run_gap_analysis --show-gaps          # print only true gaps
    python manage.py run_gap_analysis --show-all           # print every keyword
    python manage.py run_gap_analysis --top 50             # limit printed rows
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run content gap analysis and save results to ContentGapRecord."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-impressions",
            type=int,
            default=0,
            metavar="N",
            help=(
                "Exclude GSC keywords with fewer than N total impressions "
                "(default: 0 — include all). Competitor-sourced keywords "
                "always pass through."
            ),
        )
        parser.add_argument(
            "--show-gaps",
            action="store_true",
            help="After saving, print keywords where competitor_presence=True "
                 "and lcpsych_presence=False, sorted by search volume descending.",
        )
        parser.add_argument(
            "--show-all",
            action="store_true",
            help="Print every keyword processed, sorted by search volume descending.",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=30,
            metavar="N",
            help="Maximum number of rows to print when --show-gaps or --show-all "
                 "is used (default: 30).",
        )

    def handle(self, *args, **options):
        from seo_intel.services.content_gap_engine import run_gap_analysis

        min_impressions: int = options["min_impressions"]

        self.stdout.write("Running content gap analysis …")
        if min_impressions:
            self.stdout.write(f"  (excluding GSC keywords with < {min_impressions} impressions)")

        summary = run_gap_analysis(min_impressions=min_impressions)

        # ---- Summary table -----------------------------------------------
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done.  Keywords analysed: {summary.total}  "
                f"(created: {summary.created}, updated: {summary.updated})"
            )
        )
        self.stdout.write("")
        self.stdout.write("Recommended actions breakdown:")
        for action, count in sorted(
            summary.by_action.items(), key=lambda x: -x[1]
        ):
            bar = "█" * min(count, 40)
            self.stdout.write(f"  {action:<35} {count:>5}  {bar}")

        # ---- Optional detail rows ----------------------------------------
        if options["show_gaps"] or options["show_all"]:
            top_n: int = options["top"]

            if options["show_gaps"]:
                rows = [
                    kw for kw in summary.keywords
                    if kw.competitor_presence and not kw.lcpsych_presence
                ]
                header = f"\nTop {top_n} true content gaps (competitor ranks, LC Psych does not):"
            else:
                rows = list(summary.keywords)
                header = f"\nTop {top_n} keywords by search volume:"

            rows.sort(key=lambda k: -k.search_volume)
            rows = rows[:top_n]

            self.stdout.write(header)
            self.stdout.write(
                f"  {'#':>3}  {'Keyword':<45}  {'Vol':>6}  {'Comp':>4}  {'LCP':>3}  Action"
            )
            self.stdout.write("  " + "-" * 100)
            for i, kw in enumerate(rows, 1):
                comp_flag = "YES" if kw.competitor_presence else "no"
                lcp_flag  = "YES" if kw.lcpsych_presence  else "no"
                self.stdout.write(
                    f"  {i:>3}  {kw.keyword:<45}  {kw.search_volume:>6}  "
                    f"{comp_flag:>4}  {lcp_flag:>3}  {kw.recommended_action}"
                )
