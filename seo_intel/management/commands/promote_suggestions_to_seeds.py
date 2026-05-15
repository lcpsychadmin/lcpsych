"""
seo_intel/management/commands/promote_suggestions_to_seeds.py
--------------------------------------------------------------
Promote KeywordSuggestion records into active KeywordSeed records.

Usage
-----
    # Dry-run: show what would be promoted
    python manage.py promote_suggestions_to_seeds --dry-run

    # Promote all unpromotd suggestions as 'service' seeds
    python manage.py promote_suggestions_to_seeds --category service

    # Promote only PAA suggestions, cap at 20
    python manage.py promote_suggestions_to_seeds --category modality --source-type paa --limit 20

    # Promote a specific phrase by exact text
    python manage.py promote_suggestions_to_seeds --category service --suggestion "therapist near me"

Flags
-----
--category CAT      Target KeywordSeed category: service | testing | modality | location
                    (default: service)
--source-type TYPE  Filter suggestions by origin: paa | related  (default: both)
--limit N           Cap the number of promotions (default: all)
--suggestion TEXT   Promote a single, exact suggestion phrase only.
--dry-run           Print what would be promoted without writing to the DB.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Promote unpromotd KeywordSuggestion records into active KeywordSeed records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            default="service",
            metavar="CAT",
            help="KeywordSeed category to assign: service, testing, modality, location "
                 "(default: service).",
        )
        parser.add_argument(
            "--source-type",
            default=None,
            metavar="TYPE",
            choices=["paa", "related"],
            help="Restrict to suggestions from 'paa' or 'related' only "
                 "(default: both).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            metavar="N",
            help="Promote at most N suggestions (default: all).",
        )
        parser.add_argument(
            "--suggestion",
            default=None,
            metavar="TEXT",
            help="Promote this exact suggestion phrase only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would happen without touching the DB.",
        )

    def handle(self, *args, **options):
        from seo_intel.models import KeywordSuggestion
        from seo_settings.models import KEYWORD_CATEGORY_CHOICES, KeywordSeed

        category: str = options["category"]
        source_type: str | None = options["source_type"]
        limit: int | None = options["limit"]
        exact_phrase: str | None = options["suggestion"]
        dry_run: bool = options["dry_run"]

        # Validate category
        valid_categories = [c for c, _ in KEYWORD_CATEGORY_CHOICES]
        if category not in valid_categories:
            self.stderr.write(
                self.style.ERROR(
                    f"Invalid category '{category}'. "
                    f"Choose from: {', '.join(valid_categories)}"
                )
            )
            return

        # Build queryset
        qs = KeywordSuggestion.objects.filter(used_as_seed=False)

        if exact_phrase:
            qs = qs.filter(suggestion__iexact=exact_phrase.strip())
        if source_type:
            qs = qs.filter(source_type=source_type)

        qs = qs.order_by("source_type", "suggestion")

        if limit:
            qs = qs[:limit]

        candidates = list(qs)
        total = len(candidates)

        if total == 0:
            self.stdout.write(self.style.WARNING("No eligible suggestions found."))
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"DRY RUN — {total} suggestion(s) would be promoted "
                    f"as [{category}] seeds:\n"
                )
            )
            for s in candidates:
                self.stdout.write(f"  [{s.source_type}] {s.suggestion}")
            return

        promoted = 0
        skipped = 0

        for suggestion in candidates:
            seed, created = KeywordSeed.objects.get_or_create(
                keyword=suggestion.suggestion,
                defaults={"category": category, "active": True},
            )
            if created:
                suggestion.used_as_seed = True
                suggestion.save(update_fields=["used_as_seed"])
                promoted += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + Promoted: '{suggestion.suggestion}'")
                )
            else:
                # Seed already exists — still mark the suggestion as used
                if not suggestion.used_as_seed:
                    suggestion.used_as_seed = True
                    suggestion.save(update_fields=["used_as_seed"])
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ~ Already a seed: '{suggestion.suggestion}' "
                        f"(category: {seed.category})"
                    )
                )

        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done.  Promoted: {promoted}  Already existed: {skipped}"
            )
        )
