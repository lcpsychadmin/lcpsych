from django.core.management.base import BaseCommand
from core.models import OfficeLocation


class Command(BaseCommand):
    help = "Seed the initial Florence, KY office location."

    def handle(self, *args, **options):
        office, created = OfficeLocation.objects.get_or_create(
            slug="florence-ky",
            defaults={
                "name": "Florence, KY",
                "section_heading": "Our Florence, Kentucky Office",
                "address_line1": "6900 Houston Rd.",
                "address_line2": "Building 500 Suite 11",
                "address_city": "Florence",
                "address_state": "KY",
                "address_zip": "41042",
                "map_embed_url": (
                    "https://maps.google.com/maps?q=6900%20houston%20rd."
                    "%20Florence%2C%20KY%2041091&t=m&z=15&output=embed&iwloc=near"
                ),
                "directions_url": (
                    "https://maps.google.com/maps/dir//6900+Houston+Rd+Florence,"
                    "+KY+41042/@39.0086253,-84.647614,15z/data=!4m5!4m4!1m0!1m2!1m1!"
                    "1s0x8841c7da6f65d4c7:0xa64ac61629ef897f"
                ),
                "phone_number": "859-525-4911",
                "fax_number": "859-525-6446",
                "office_hours": "Mon \u2013 Thurs: 8AM \u2013 9PM\nFriday: 8AM \u2013 5PM\nSaturday: 8AM \u2013 2PM",
                "cta_url": "https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
                "cta_label": "Schedule Online",
                "is_active": True,
                "order": 0,
            },
        )
        action = "Created" if created else "Already exists"
        self.stdout.write(self.style.SUCCESS(f"{action}: {office.name} (pk={office.pk})"))
