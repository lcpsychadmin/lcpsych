from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0009_therapistprofile_top_services"),
    ]

    operations = [
        migrations.AddField(
            model_name="therapistprofile",
            name="home_order",
            field=models.PositiveIntegerField(
                default=100,
                help_text="Lower numbers appear first on the homepage therapist grid.",
            ),
        ),
    ]
