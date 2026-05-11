from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("geo", "0005_georegion"),
    ]

    operations = [
        migrations.AddField(
            model_name="georegion",
            name="offices",
            field=models.ManyToManyField(
                blank=True,
                help_text="Physical offices that serve this region.",
                related_name="regions",
                to="core.officelocation",
            ),
        ),
    ]
