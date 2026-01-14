from django.db import migrations, models
import ckeditor.fields


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_whatwedo"),
    ]

    operations = [
        migrations.CreateModel(
            name="AboutSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("about_title", models.CharField(default="About Us", max_length=200)),
                ("about_body", ckeditor.fields.RichTextField(blank=True, help_text="Main About Us copy.")),
                ("mission_title", models.CharField(default="Our Mission", max_length=200)),
                ("mission_body", ckeditor.fields.RichTextField(blank=True, help_text="Mission statement copy.")),
                (
                    "cta_label",
                    models.CharField(blank=True, default="Schedule Your First Appointment Today", max_length=200),
                ),
                (
                    "cta_url",
                    models.URLField(
                        blank=True,
                        default="https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
                        help_text="Optional CTA button link; leave blank to hide the button.",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "About section",
                "verbose_name_plural": "About sections",
            },
        ),
    ]
