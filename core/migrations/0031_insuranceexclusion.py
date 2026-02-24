from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_seed_insurance_providers"),
    ]

    operations = [
        migrations.CreateModel(
            name="InsuranceExclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True)),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Display ordering in the non-accepted list.",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["order", "name", "id"],
                "verbose_name": "Insurance exclusion",
                "verbose_name_plural": "Insurance exclusions",
            },
        ),
    ]
