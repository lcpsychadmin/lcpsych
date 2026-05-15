from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_intel', '0005_competitorhit'),
    ]

    operations = [
        migrations.CreateModel(
            name='LCPsychHit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=500)),
                ('url', models.URLField(max_length=2000)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('rank', models.IntegerField()),
                ('timestamp', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'LC Psych SERP hit',
                'verbose_name_plural': 'LC Psych SERP hits',
                'ordering': ['-timestamp', 'rank'],
                'indexes': [
                    models.Index(fields=['keyword'], name='seo_intel_lc_keyword_idx'),
                    models.Index(fields=['-timestamp'], name='seo_intel_lc_ts_idx'),
                    models.Index(fields=['rank'], name='seo_intel_lc_rank_idx'),
                ],
            },
        ),
    ]
