from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seo_settings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SEOControlPanel',
            fields=[],
            options={
                'verbose_name': 'Control Panel',
                'verbose_name_plural': 'Control Panel',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
    ]
