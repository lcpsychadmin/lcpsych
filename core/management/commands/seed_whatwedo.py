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
    "Anxiety",
    "Depression",
    "ADHD",
    "Phobias",
    "Trauma & Abuse",
    "Autism Spectrum",
    "Grief",
    "Social Skills",
    "Life Transitions",
    "Divorce Issues",
    "Behavior Problems",
    "Family Difficulties",
    "Relationship Issues",
    "Academic Problems",
    "Personality Disorders",
    "Coping Skills",
    "Testing & Evaluation",
    "Stress Management",
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

        # Remove any stale items beyond the seeded list length
        WhatWeDoItem.objects.filter(order__gte=len(DEFAULT_ITEMS)).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded What We Do section (id={section.pk}); items: {created_count} created, {updated_count} updated."
            )
        )
