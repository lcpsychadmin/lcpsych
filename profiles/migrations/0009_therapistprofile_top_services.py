from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0008_update_client_focus_options"),
        ("core", "0010_alter_service_excerpt_alter_service_image_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="therapistprofile",
            name="top_services",
            field=models.ManyToManyField(
                blank=True,
                help_text="Optionally choose up to three services to feature on cards.",
                related_name="featured_therapists",
                to="core.service",
            ),
        ),
    ]
