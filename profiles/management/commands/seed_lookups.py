from django.core.management.base import BaseCommand

from profiles.models import ClientFocus, LicenseType


class Command(BaseCommand):
    help = "Seed core lookup tables for therapist profiles."

    def handle(self, *args, **options):
        license_types = {
            "Psychologist": "Licensed psychologist (PhD or PsyD).",
            "Licensed Clinical Social Worker": "LCSW providing therapy services.",
            "Licensed Professional Counselor": "LPC or LPCC level counselor.",
            "Licensed Marriage and Family Therapist": "LMFT focusing on relationships and families.",
            "Psychiatric Nurse Practitioner": "PMHNP providing psychiatric services.",
        }

        client_focuses = {
            "Child & Adolescent": "Supports children and adolescents.",
            "Adult": "Works with individual adults.",
            "Couples": "Provides services to couples or partners.",
            "Families": "Supports whole family systems.",
        }

        created_lt = 0
        for name, description in license_types.items():
            _, created = LicenseType.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            created_lt += int(created)

        created_cf = 0
        for name, description in client_focuses.items():
            _, created = ClientFocus.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            created_cf += int(created)

        self.stdout.write(self.style.SUCCESS(f"Ensured {len(license_types)} license types (created {created_lt})."))
        self.stdout.write(self.style.SUCCESS(f"Ensured {len(client_focuses)} client focus options (created {created_cf})."))
