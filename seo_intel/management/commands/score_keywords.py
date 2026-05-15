"""
seo_intel/management/commands/score_keywords.py
------------------------------------------------
Compute and persist keyword priority scores for every known keyword.

The command aggregates data from five sources in a single DB pass, scores each
keyword via the ``keyword_scoring`` service, then upserts ``KeywordScore``
records.  At the end it prints the top-20 highest-priority keywords.

Usage
-----
    python manage.py score_keywords
    python manage.py score_keywords --top 30
    python manage.py score_keywords --dry-run
"""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Avg, Sum


class Command(BaseCommand):
    help = "Score all known keywords by SEO priority and persist results."

    def add_arguments(self, parser):
        parser.add_argument(
            "--top",
            type=int,
            default=20,
            metavar="N",
            help="Number of top-priority keywords to print at the end (default: 20).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute scores but do not save to the database.",
        )

    def handle(self, *args, **options):
        from seo_intel.models import (
            CompetitorHit,
            KeywordScore,
            KeywordSuggestion,
            LCPsychHit,
            SearchConsoleQuery,
        )
        from seo_intel.services.keyword_scoring import load_geo_terms, score_keyword
        from seo_settings.models import KeywordSeed

        top_n: int = options["top"]
        dry_run: bool = options["dry_run"]

        # ── 1. Build GSC aggregates (impressions / clicks per query) ─────────
        self.stdout.write("Loading GSC data …")
        gsc_stats: dict[str, dict] = {}
        gsc_qs = SearchConsoleQuery.objects.values("query").annotate(
            impressions=Sum("impressions"),
            clicks=Sum("clicks"),
            avg_position=Avg("position"),
        )
        for row in gsc_qs:
            gsc_stats[row["query"]] = {
                "impressions": row["impressions"] or 0,
                "clicks": row["clicks"] or 0,
                "avg_position": row["avg_position"] or 0.0,
            }

        # ── 2. Build competitor rank lookup ───────────────────────────────────
        self.stdout.write("Loading competitor hit data …")
        competitor_ranks: dict[str, list[int]] = defaultdict(list)
        for kw, rank in CompetitorHit.objects.values_list("keyword", "rank"):
            competitor_ranks[kw].append(rank)

        # ── 3. Build LC Psych rank lookup ─────────────────────────────────────
        self.stdout.write("Loading LC Psych hit data …")
        lcpsych_ranks: dict[str, list[int]] = defaultdict(list)
        for kw, rank in LCPsychHit.objects.values_list("keyword", "rank"):
            lcpsych_ranks[kw].append(rank)

        # ── 4. Collect all distinct keywords ──────────────────────────────────
        self.stdout.write("Collecting keyword universe …")
        keywords: set[str] = set()
        keywords.update(gsc_stats.keys())
        keywords.update(competitor_ranks.keys())
        keywords.update(lcpsych_ranks.keys())
        keywords.update(
            KeywordSeed.objects.filter(active=True).values_list("keyword", flat=True)
        )
        keywords.update(
            KeywordSuggestion.objects.values_list("suggestion", flat=True)
        )

        total = len(keywords)
        self.stdout.write(f"Found {total} distinct keyword(s) across all sources.\n")

        if total == 0:
            self.stdout.write(self.style.WARNING("Nothing to score."))
            return

        # ── 5. Load geo terms once ────────────────────────────────────────────
        geo_terms = load_geo_terms()

        # ── 6. Score and persist ──────────────────────────────────────────────
        results: list[dict] = []
        saved = 0

        for keyword in keywords:
            scored = score_keyword(
                keyword,
                gsc_stats=gsc_stats,
                competitor_ranks=competitor_ranks,
                lcpsych_ranks=lcpsych_ranks,
                geo_terms=geo_terms,
            )
            results.append(scored)

            if not dry_run:
                KeywordScore.objects.update_or_create(
                    keyword=keyword,
                    defaults={
                        "search_demand_score": scored["search_demand_score"],
                        "competitor_pressure_score": scored["competitor_pressure_score"],
                        "lcpsych_presence_score": scored["lcpsych_presence_score"],
                        "local_intent_score": scored["local_intent_score"],
                        "commercial_intent_score": scored["commercial_intent_score"],
                        "priority_score": scored["priority_score"],
                    },
                )
                saved += 1

        # ── 7. Print top-N ────────────────────────────────────────────────────
        results.sort(key=lambda r: r["priority_score"], reverse=True)
        top = results[:top_n]

        label = "DRY RUN — " if dry_run else ""
        self.stdout.write(
            "\n" + "─" * 72 + "\n"
            + f"{label}Top {len(top)} keywords by priority score\n"
            + "─" * 72
        )

        col_w = 42
        header = (
            f"{'Keyword':<{col_w}} {'Pri':>4}  "
            f"{'Demand':>6}  {'Comp':>5}  {'LC':>4}  {'Local':>6}  {'Comm':>5}"
        )
        self.stdout.write(header)
        self.stdout.write("─" * 72)

        for r in top:
            kw_display = r["keyword"]
            if len(kw_display) > col_w:
                kw_display = kw_display[: col_w - 1] + "…"
            line = (
                f"{kw_display:<{col_w}} {r['priority_score']:>4}  "
                f"{r['search_demand_score']:>6}  "
                f"{r['competitor_pressure_score']:>5}  "
                f"{r['lcpsych_presence_score']:>4}  "
                f"{r['local_intent_score']:>6}  "
                f"{r['commercial_intent_score']:>5}"
            )
            self.stdout.write(line)

        self.stdout.write("─" * 72)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN — no records written ({total} scored)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone. {saved} KeywordScore record(s) saved/updated."
                )
            )
