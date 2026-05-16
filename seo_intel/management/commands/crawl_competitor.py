"""
Management command: crawl_competitor
--------------------------------------
Crawls one or all active competitor domains and caches the results.

Usage
-----
    python manage.py crawl_competitor
    python manage.py crawl_competitor --domain psychologytoday.com
    python manage.py crawl_competitor --max-pages 200 --force
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crawl active competitor domains and cache page-level signals for the analysis engine."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="",
            help="Specific domain to crawl (default: all active CompetitorDomain records).",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=200,
            dest="max_pages",
            help="Maximum HTML pages to crawl per domain (default: 200).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force re-crawl even when cached results already exist.",
        )

    def handle(self, *args, **options):
        from seo_settings.models import CompetitorDomain
        from seo_intel.services.competitor_crawler import crawl_competitor

        domain = options["domain"].strip()
        max_pages = options["max_pages"]
        force = options["force"]

        if domain:
            domains = [domain]
        else:
            domains = list(
                CompetitorDomain.objects.filter(active=True).values_list("domain", flat=True)
            )

        if not domains:
            self.stdout.write(self.style.WARNING("No active competitor domains found."))
            return

        for d in domains:
            self.stdout.write(f"Crawling {d} (max {max_pages} pages, force={force})...")
            try:
                pages = crawl_competitor(d, max_pages=max_pages, force=force)
                self.stdout.write(
                    self.style.SUCCESS(f"  OK  {d}: {len(pages)} pages crawled and cached.")
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  ERR {d}: {exc}")
                )
