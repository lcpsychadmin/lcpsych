"""
One-time command: copy linked Page content into Service.body
for any service that has a page FK but no body content.
"""

from django.core.management.base import BaseCommand

from core.models import Service


class Command(BaseCommand):
    help = "Populate Service.body from linked Page content where body is empty."

    def handle(self, *args, **options):
        seeded = 0
        skipped = 0
        for service in Service.objects.select_related("page").all():
            if service.body:
                self.stdout.write(f"  skip (has body): {service.title}")
                skipped += 1
                continue
            if not service.page:
                self.stdout.write(f"  skip (no page):  {service.title}")
                skipped += 1
                continue
            html = service.page.content_html
            if not html:
                self.stdout.write(self.style.WARNING(f"  skip (empty page html): {service.title}"))
                skipped += 1
                continue
            service.body = html
            service.save(update_fields=["body"])
            self.stdout.write(self.style.SUCCESS(f"  seeded: {service.title}"))
            seeded += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone. {seeded} seeded, {skipped} skipped."))
