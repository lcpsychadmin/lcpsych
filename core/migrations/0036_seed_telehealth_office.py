"""Data migration: create the Telehealth virtual OfficeLocation."""
from django.db import migrations


def create_telehealth_office(apps, schema_editor):
    OfficeLocation = apps.get_model("core", "OfficeLocation")
    GeoState = apps.get_model("geo", "GeoState")

    # Only create if it doesn't already exist
    if OfficeLocation.objects.filter(slug="telehealth").exists():
        return

    office = OfficeLocation.objects.create(
        name="Telehealth",
        slug="telehealth",
        section_heading="Telehealth Therapy",
        is_virtual=True,
        is_active=True,
        order=99,
        office_hours_title="Availability",
        office_hours="By appointment",
        cta_label="Schedule an Appointment",
        cta_url="/contact-us/",
        phone_label="Phone",
        phone_number="",
        fax_label="",
        fax_number="",
        email_label="Email",
        email_address="",
    )

    # Link to all active states (KY, OH, IN)
    states = GeoState.objects.filter(slug__in=["kentucky", "ohio", "indiana"])
    office.geo_states.set(states)


def remove_telehealth_office(apps, schema_editor):
    OfficeLocation = apps.get_model("core", "OfficeLocation")
    OfficeLocation.objects.filter(slug="telehealth").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_officelocation_is_virtual"),
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_telehealth_office, remove_telehealth_office),
    ]
