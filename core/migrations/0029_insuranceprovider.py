from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_alter_analyticsevent_event_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="InsuranceProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("order", models.PositiveIntegerField(default=0, help_text="Display ordering in the accepted list.")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Insurance provider",
                "verbose_name_plural": "Insurance providers",
                "ordering": ["order", "name", "id"],
            },
        ),
    ]
