"""
Management command to seed the geo database tables from geo/areas_served.py.

Usage
-----
  python manage.py seed_geo              # create-or-update, skip existing
  python manage.py seed_geo --truncate   # wipe all geo data first, then seed

This command is safe to re-run.  Records already in the database are updated
(not duplicated) unless --truncate is passed.
"""

from django.core.management.base import BaseCommand

from geo.areas_served import AREAS_SERVED
from geo.models import GeoContentBlock, GeoLocation, GeoState


class Command(BaseCommand):
    help = "Seed geo states, cities, and counties from areas_served.py"

    def add_arguments(self, parser):
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Delete all existing geo records before seeding.",
        )

    def handle(self, *args, **options):
        if options["truncate"]:
            deleted_states, _ = GeoState.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted_states} existing geo state records (cascades to locations/blocks).")
            )

        state_count = 0
        location_count = 0
        block_count = 0

        for state_slug, state_data in AREAS_SERVED.items():
            seo = state_data.get("seo", {})

            state_obj, created = GeoState.objects.update_or_create(
                slug=state_slug,
                defaults={
                    "name": state_data.get("name", state_slug.title()),
                    "abbreviation": state_data.get("abbreviation", ""),
                    "seo_title": seo.get("title_template", ""),
                    "seo_description": seo.get("meta_description", ""),
                    "hero_heading": seo.get("hero_heading", ""),
                    "hero_subheading": seo.get("hero_subheading", ""),
                    "og_image_url": seo.get("og_image_url", ""),
                    "is_active": True,
                },
            )
            state_count += 1
            verb = "Created" if created else "Updated"
            self.stdout.write(f"  {verb} state: {state_obj}")

            # Seed state content blocks (skip if already populated for this state)
            if created or not state_obj.content_blocks.filter(state=state_obj).exists():
                state_obj.content_blocks.filter(state=state_obj).delete()
                for i, block in enumerate(state_data.get("content_blocks", [])):
                    GeoContentBlock.objects.create(
                        state=state_obj,
                        order=i,
                        heading=block["heading"],
                        body=block["body"],
                    )
                    block_count += 1

            # Seed counties
            for county_slug, county_data in state_data.get("counties", {}).items():
                seo = county_data.get("seo", {})
                loc_obj, loc_created = GeoLocation.objects.update_or_create(
                    state=state_obj,
                    slug=county_slug,
                    defaults={
                        "name": county_data.get("name", county_slug.replace("-", " ").title()),
                        "location_type": GeoLocation.COUNTY,
                        "seo_title": seo.get("title_template", ""),
                        "seo_description": seo.get("meta_description", ""),
                        "hero_heading": seo.get("hero_heading", ""),
                        "hero_subheading": seo.get("hero_subheading", ""),
                        "og_image_url": seo.get("og_image_url", ""),
                        "is_active": True,
                    },
                )
                location_count += 1

                if loc_created or not loc_obj.content_blocks.exists():
                    loc_obj.content_blocks.all().delete()
                    for i, block in enumerate(county_data.get("content_blocks", [])):
                        GeoContentBlock.objects.create(
                            location=loc_obj,
                            order=i,
                            heading=block["heading"],
                            body=block["body"],
                        )
                        block_count += 1

            # Seed cities
            for city_slug, city_data in state_data.get("cities", {}).items():
                seo = city_data.get("seo", {})
                loc_obj, loc_created = GeoLocation.objects.update_or_create(
                    state=state_obj,
                    slug=city_slug,
                    defaults={
                        "name": city_data.get("name", city_slug.replace("-", " ").title()),
                        "location_type": GeoLocation.CITY,
                        "seo_title": seo.get("title_template", ""),
                        "seo_description": seo.get("meta_description", ""),
                        "hero_heading": seo.get("hero_heading", ""),
                        "hero_subheading": seo.get("hero_subheading", ""),
                        "og_image_url": seo.get("og_image_url", ""),
                        "is_active": True,
                    },
                )
                location_count += 1

                if loc_created or not loc_obj.content_blocks.exists():
                    loc_obj.content_blocks.all().delete()
                    for i, block in enumerate(city_data.get("content_blocks", [])):
                        GeoContentBlock.objects.create(
                            location=loc_obj,
                            order=i,
                            heading=block["heading"],
                            body=block["body"],
                        )
                        block_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {state_count} states, {location_count} locations, "
                f"{block_count} content blocks seeded."
            )
        )

        # Grant all geo model permissions to the admin group so admin-group users
        # can access /admin/geo/ without needing is_superuser.
        from django.contrib.auth.models import Group, Permission
        admin_group, _ = Group.objects.get_or_create(name="admin")
        geo_perms = Permission.objects.filter(content_type__app_label="geo")
        admin_group.permissions.add(*geo_perms)
        self.stdout.write(self.style.SUCCESS("Admin group geo permissions ensured."))
