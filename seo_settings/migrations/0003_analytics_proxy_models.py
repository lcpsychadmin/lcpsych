from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seo_settings', '0002_seocontrolpanel'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchConsoleDashboard',
            fields=[],
            options={
                'verbose_name': 'Search Console',
                'verbose_name_plural': 'Search Console',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
        migrations.CreateModel(
            name='InternalSearchDashboard',
            fields=[],
            options={
                'verbose_name': 'Internal Search',
                'verbose_name_plural': 'Internal Search',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
        migrations.CreateModel(
            name='DeadURLAnalytics',
            fields=[],
            options={
                'verbose_name': 'Dead URL Analytics',
                'verbose_name_plural': 'Dead URL Analytics',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
        migrations.CreateModel(
            name='CompetitorSERPAnalytics',
            fields=[],
            options={
                'verbose_name': 'Competitor SERP',
                'verbose_name_plural': 'Competitor SERP',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
        migrations.CreateModel(
            name='ContentGapAnalytics',
            fields=[],
            options={
                'verbose_name': 'Content Gaps',
                'verbose_name_plural': 'Content Gaps',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seo_settings.seoglobalsettings',),
        ),
    ]
