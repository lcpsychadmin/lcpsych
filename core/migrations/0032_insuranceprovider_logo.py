from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_insuranceexclusion"),
    ]

    operations = [
        migrations.AddField(
            model_name="insuranceprovider",
            name="logo",
            field=models.ImageField(blank=True, help_text="Optional uploaded logo shown on the insurance page.", null=True, upload_to="insurance/logos/"),
        ),
        migrations.AddField(
            model_name="insuranceprovider",
            name="logo_url",
            field=models.URLField(blank=True, help_text="Optional external logo URL if not uploading a file."),
        ),
    ]
