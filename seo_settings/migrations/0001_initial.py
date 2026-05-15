from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SEOGlobalSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enable_search_console', models.BooleanField(default=False, verbose_name='Enable Search Console')),
                ('enable_internal_search_tracking', models.BooleanField(default=False, verbose_name='Enable internal search tracking')),
                ('enable_dead_url_logging', models.BooleanField(default=False, verbose_name='Enable dead URL / 404 logging')),
                ('enable_competitor_scraping', models.BooleanField(default=False, verbose_name='Enable competitor scraping')),
                ('enable_gap_analysis', models.BooleanField(default=False, verbose_name='Enable gap analysis')),
                ('search_console_property_url', models.URLField(blank=True, verbose_name='Search Console property URL')),
                ('google_client_email', models.CharField(blank=True, max_length=254, verbose_name='Google service account email')),
                ('google_private_key', models.TextField(blank=True, verbose_name='Google private key (PEM)')),
                ('url_removal_token', models.CharField(blank=True, max_length=255, verbose_name='URL removal token')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last updated')),
            ],
            options={
                'verbose_name': 'Global SEO settings',
                'verbose_name_plural': 'Global SEO settings',
            },
        ),
        migrations.CreateModel(
            name='CompetitorDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=253, unique=True, verbose_name='Domain')),
                ('label', models.CharField(blank=True, max_length=200, verbose_name='Label')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Competitor domain',
                'verbose_name_plural': 'Competitor domains',
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='KeywordSeed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=500, verbose_name='Keyword')),
                ('category', models.CharField(
                    choices=[('service', 'Service'), ('testing', 'Testing'), ('modality', 'Modality'), ('location', 'Location')],
                    max_length=20,
                    verbose_name='Category',
                )),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Keyword seed',
                'verbose_name_plural': 'Keyword seeds',
                'ordering': ['category', 'keyword'],
            },
        ),
    ]
