from django.core.management.base import BaseCommand
from django.contrib.sitemaps import ping_google


class Command(BaseCommand):
    help = "Ping Google to notify of sitemap updates"

    def add_arguments(self, parser):
        parser.add_argument(
            "sitemap_url",
            nargs="?",
            default="https://www.lcpsych.com/sitemap.xml",
        )

    def handle(self, *args, **options):
        url = options["sitemap_url"]
        try:
            ping_google(url)
            self.stdout.write(self.style.SUCCESS(f"Pinged Google with {url}"))
        except Exception as exc:
            self.stderr.write(f"ping_google failed: {exc}")
