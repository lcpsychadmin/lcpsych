from django.db import migrations, models
import ckeditor.fields


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_seed_initial_faqs"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatWeDoSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(default="What We Do", max_length=200)),
                (
                    "description",
                    ckeditor.fields.RichTextField(
                        blank=True, help_text="Intro text shown above the bullet list."
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "What we do section",
                "verbose_name_plural": "What we do sections",
            },
        ),
        migrations.CreateModel(
            name="WhatWeDoItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("text", models.CharField(max_length=200)),
                ("order", models.PositiveIntegerField(default=0, help_text="Display ordering for the list.")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["order", "id"],
                "verbose_name": "What we do item",
                "verbose_name_plural": "What we do items",
            },
        ),
    ]
