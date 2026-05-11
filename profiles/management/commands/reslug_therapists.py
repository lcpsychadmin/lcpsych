"""
Management command to regenerate TherapistProfile slugs from first_name + last_name.
Safe to run multiple times — skips profiles where the slug already matches the
expected first-last pattern and the name hasn't changed.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from profiles.models import TherapistProfile


class Command(BaseCommand):
    help = "Regenerate therapist slugs from first_name + last_name."

    def handle(self, *args, **options):
        updated = 0
        skipped = 0

        for profile in TherapistProfile.objects.select_related("user").order_by("pk"):
            name_base = slugify(
                f"{profile.first_name} {profile.last_name}".strip()
            )
            if not name_base:
                self.stdout.write(
                    self.style.WARNING(
                        f"  SKIP pk={profile.pk} — no name set (slug stays '{profile.slug}')"
                    )
                )
                skipped += 1
                continue

            if profile.slug == name_base:
                self.stdout.write(f"  OK   {profile.slug}")
                skipped += 1
                continue

            # Generate a unique slug
            candidate = name_base
            counter = 2
            while (
                TherapistProfile.objects.filter(slug=candidate)
                .exclude(pk=profile.pk)
                .exists()
            ):
                candidate = f"{name_base}-{counter}"
                counter += 1

            old_slug = profile.slug
            profile.slug = candidate
            # Use update_fields to bypass the save() guard (slug is already set)
            TherapistProfile.objects.filter(pk=profile.pk).update(slug=candidate)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  UPDATED pk={profile.pk} '{old_slug}' → '{candidate}'"
                )
            )
            updated += 1

        self.stdout.write(f"\nDone — {updated} updated, {skipped} skipped.")
