import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand

# Google shut down the /ping?sitemap= endpoint in Jan 2024.
# IndexNow is the modern replacement — supported by Bing and (experimentally) Google.
# Submit your sitemap to Google Search Console for reliable re-crawl scheduling.


class Command(BaseCommand):
    help = "Submit sitemap URL to IndexNow (Bing/Yandex; Google experimental)"

    def add_arguments(self, parser):
        parser.add_argument(
            "sitemap_url",
            nargs="?",
            default="https://www.lcpsych.com/sitemap.xml",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Google's sitemap ping endpoint was shut down in Jan 2024. "
                "Submit your sitemap via Google Search Console instead: "
                "https://search.google.com/search-console"
            )
        )
