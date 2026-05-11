from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_about_us_managed_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialprofile",
            name="client_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="socialprofile",
            name="client_secret",
            field=models.TextField(blank=True),
        ),
    ]
