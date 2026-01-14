from django.core.management.base import BaseCommand

from core.models import FeeCategory, PaymentFeeRow


class Command(BaseCommand):
    help = "Seed payment fee rows for the Payment Options table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing payment fee rows before seeding defaults.",
        )

    def handle(self, *args, **options):
        if options.get("reset"):
            deleted, _ = PaymentFeeRow.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing payment fee rows."))

        rows = [
            # Professional services
            {
                "name": "Initial Evaluation (1 hour diagnostic interview)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 10,
                "doctoral_fee": "$195",
                "masters_fee": "$170",
                "supervised_fee": "$135",
            },
            {
                "name": "Psychotherapy Session (55 minute)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 20,
                "doctoral_fee": "$185",
                "masters_fee": "$160",
                "supervised_fee": "$125",
            },
            {
                "name": "Psychotherapy Session (30 minute)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 30,
                "doctoral_fee": "$95",
                "masters_fee": "$80",
                "supervised_fee": "$65",
            },
            {
                "name": "Group Therapy Session (60 min)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 40,
                "doctoral_fee": "$50",
                "masters_fee": "$40",
                "supervised_fee": "$40",
            },
            {
                "name": "Psychological Assessment (testing/scoring/interpretation/report writing)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 50,
                "doctoral_fee": "$200/hour",
                "masters_fee": "N/A",
                "supervised_fee": "$200/hour",
            },
            {
                "name": "Court Related Work (deposition, testimony, reports, prep, travel, etc)",
                "category": FeeCategory.PROFESSIONAL,
                "order": 60,
                "doctoral_fee": "$250/hour",
                "masters_fee": "$225/hour",
                "supervised_fee": "$225/hour",
            },
            # Miscellaneous
            {
                "name": "Missed Appointment/Late Cancellation (less than 24 hours notice)",
                "category": FeeCategory.MISC,
                "order": 10,
                "masters_fee": "$95",
            },
            {
                "name": "Returned Check Fee",
                "category": FeeCategory.MISC,
                "order": 20,
                "masters_fee": "$50 (plus bank costs)",
            },
            {
                "name": "Psychological Testing Protocol Fees",
                "category": FeeCategory.MISC,
                "order": 30,
                "doctoral_fee": "Varies based on assessment",
            },
            {
                "name": "General Letters (requested by patient)",
                "category": FeeCategory.MISC,
                "order": 40,
                "doctoral_fee": "$30 (based on 15 minutes); additional charges for lengthy letters or summaries",
            },
            {
                "name": "Phone Calls",
                "category": FeeCategory.MISC,
                "order": 50,
                "doctoral_fee": "$30 per 15 minutes",
            },
            {
                "name": "Medical Records (beyond 1 free copy)",
                "category": FeeCategory.MISC,
                "order": 60,
                "doctoral_fee": "$1 per page",
            },
            {
                "name": "No payment at time of service",
                "category": FeeCategory.MISC,
                "order": 70,
                "doctoral_fee": "$10",
            },
            {
                "name": "Late Payments (60 days past service date)",
                "category": FeeCategory.MISC,
                "order": 80,
                "doctoral_fee": "$10 per month",
            },
        ]

        created = 0
        for row in rows:
            defaults = {
                "order": row.get("order", 0),
                "doctoral_fee": row.get("doctoral_fee", ""),
                "masters_fee": row.get("masters_fee", ""),
                "supervised_fee": row.get("supervised_fee", ""),
                "notes": row.get("notes", ""),
            }
            obj, was_created = PaymentFeeRow.objects.update_or_create(
                name=row["name"],
                category=row["category"],
                defaults=defaults,
            )
            created += 1 if was_created else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(rows)} payment fee rows ({created} created, {len(rows) - created} updated)."
            )
        )
