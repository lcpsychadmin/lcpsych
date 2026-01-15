from django.core.management.base import BaseCommand

from core.models import WhatWeDoSection, WhatWeDoItem


DEFAULT_SECTION = {
    "title": "What We Do",
    "description": (
        "Sometimes the disconnection in our lives is difficult to navigate alone. "
        "We are here to work with our clients to develop their personal goals to help "
        "get their life connected. Below is a list of common issues through which we "
        "have guided and supported our clients. While the list is not exhaustive, it "
        "represents the breadth of issues for which our clinicians are trained and experienced."
    ),
    "is_active": True,
}

DEFAULT_ITEMS = [
    "Individual therapy for children, teens, and adults",
    "Couples and marriage counseling",
    "Family therapy and parenting support",
    "Anxiety, depression, and mood disorders",
    "Trauma, PTSD, and grief recovery",
    "ADHD, executive function, and learning concerns",
    "Stress management and life transitions",
    "Identity, faith, and relationship concerns",
    "Psychological testing and evaluations",
    "Telehealth across Kentucky",
]


class Command(BaseCommand):
    help = "Seed the What We Do section and bullet items"

    def handle(self, *args, **options):
        section, created = WhatWeDoSection.objects.update_or_create(
            id=1,
            defaults=DEFAULT_SECTION,
        )

        created_count = 0
        updated_count = 0
        for order, text in enumerate(DEFAULT_ITEMS):
            item, item_created = WhatWeDoItem.objects.update_or_create(
                order=order,
                defaults={"text": text, "is_active": True},
            )
            if item_created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded What We Do section (id={section.id}); items: {created_count} created, {updated_count} updated."
            )
        )
