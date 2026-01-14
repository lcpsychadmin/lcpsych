from django.db import migrations, models
import ckeditor.fields


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_aboutsection"),
    ]

    operations = [
        migrations.CreateModel(
            name="OurPhilosophy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "title",
                    models.CharField(
                        default="Our philosophy of treatment is that people have a need to be connected.", max_length=255
                    ),
                ),
                (
                    "body",
                    ckeditor.fields.RichTextField(blank=True, help_text="Displayed under the philosophy heading."),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Our philosophy",
                "verbose_name_plural": "Our philosophy",
            },
        ),
    ]
