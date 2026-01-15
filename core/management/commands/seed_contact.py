from django.core.management.base import BaseCommand

from core.models import ContactInfo


DEFAULTS = {
    "heading": "Proud to Serve Cincinnati/Northern Kentucky",
    "map_embed_url": "https://maps.google.com/maps?q=6900%20houston%20rd.%20Florence%2C%20KY%2041091&t=m&z=15&output=embed&iwloc=near",
    "directions_url": "https://maps.google.com/maps/dir//6900+Houston+Rd+Florence,+KY+41042/@39.0086253,-84.647614,15z/data=!4m5!4m4!1m0!1m2!1m1!1s0x8841c7da6f65d4c7:0xa64ac61629ef897f",
    "office_title": "Our Office",
    "office_address": "6900 Houston Rd.\nBuilding 500 Suite 11\nFlorence, KY 41042",
    "office_hours_title": "Office Hours",
    "office_hours": "Mon - Thurs: 8AM - 9PM\nFriday: 8AM - 5PM\nSaturday: 8AM - 2PM",
    "contact_title": "Contact Us",
    "phone_label": "Office",
    "phone_number": "859-525-4911",
    "fax_label": "Fax",
    "fax_number": "859-525-6446",
    "email_label": "Front Office",
    "email_address": "",
    "cta_label": "Schedule Online",
    "cta_url": "https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
    "is_active": True,
}


class Command(BaseCommand):
    help = "Seed the default contact info block for the homepage"

    def handle(self, *args, **options):
        contact, created = ContactInfo.objects.update_or_create(
            id=1,
            defaults=DEFAULTS,
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} ContactInfo (id={contact.id})"))
