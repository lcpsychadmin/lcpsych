from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_intel', '0004_serprawresult'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitorHit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=500)),
                ('competitor_domain', models.CharField(max_length=253)),
                ('url', models.URLField(max_length=2000)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('rank', models.IntegerField()),
                ('timestamp', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'Competitor hit',
                'verbose_name_plural': 'Competitor hits',
                'ordering': ['-timestamp', 'rank'],
                'indexes': [
                    models.Index(fields=['keyword'], name='seo_intel_c_keyword_idx'),
                    models.Index(fields=['competitor_domain'], name='seo_intel_c_domain_idx'),
                    models.Index(fields=['-timestamp'], name='seo_intel_c_ts_idx'),
                ],
            },
        ),
    ]
