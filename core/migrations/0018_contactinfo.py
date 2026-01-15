# Generated manually to add ContactInfo model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_companyquote_inspirationalquote"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "heading",
                    models.CharField(
                        default="Proud to Serve Cincinnati/Northern Kentucky",
                        max_length=255,
                    ),
                ),
                (
                    "map_embed_url",
                    models.URLField(
                        blank=True,
                        default="https://maps.google.com/maps?q=6900%20houston%20rd.%20Florence%2C%20KY%2041091&t=m&z=15&output=embed&iwloc=near",
                        help_text="Full Google Maps embed URL for the iframe src.",
                        max_length=1000,
                    ),
                ),
                (
                    "directions_url",
                    models.URLField(
                        blank=True,
                        default="https://maps.google.com/maps/dir//6900+Houston+Rd+Florence,+KY+41042/@39.0086253,-84.647614,15z/data=!4m5!4m4!1m0!1m2!1m1!1s0x8841c7da6f65d4c7:0xa64ac61629ef897f",
                        help_text="Link for the 'Get Directions' button.",
                        max_length=1000,
                    ),
                ),
                ("office_title", models.CharField(default="Our Office", max_length=200)),
                (
                    "office_address",
                    models.TextField(
                        default="6900 Houston Rd.\nBuilding 500 Suite 11\nFlorence, KY 41042",
                        help_text="Supports line breaks to split the address.",
                    ),
                ),
                ("office_hours_title", models.CharField(default="Office Hours", max_length=200)),
                (
                    "office_hours",
                    models.TextField(
                        default="Mon - Thurs: 8AM - 9PM\nFriday: 8AM - 5PM\nSaturday: 8AM - 2PM",
                        help_text="One entry per line. Bold labels can be added in the template.",
                    ),
                ),
                ("contact_title", models.CharField(default="Contact Us", max_length=200)),
                ("phone_label", models.CharField(default="Office", max_length=100)),
                ("phone_number", models.CharField(default="859-525-4911", max_length=50)),
                ("fax_label", models.CharField(default="Fax", max_length=100)),
                ("fax_number", models.CharField(default="859-525-6446", max_length=50)),
                ("email_label", models.CharField(default="Front Office", max_length=100)),
                ("email_address", models.EmailField(blank=True, default="", max_length=254)),
                ("cta_label", models.CharField(default="Schedule Online", max_length=120)),
                (
                    "cta_url",
                    models.URLField(
                        blank=True,
                        default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
                        max_length=500,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Contact info",
                "verbose_name_plural": "Contact info",
            },
        ),
    ]
