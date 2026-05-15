from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_intel', '0007_keywordsuggestion'),
    ]

    operations = [
        migrations.CreateModel(
            name='KeywordScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=500, unique=True)),
                ('search_demand_score', models.IntegerField(default=0)),
                ('competitor_pressure_score', models.IntegerField(default=0)),
                ('lcpsych_presence_score', models.IntegerField(default=0)),
                ('local_intent_score', models.IntegerField(default=0)),
                ('commercial_intent_score', models.IntegerField(default=0)),
                ('priority_score', models.IntegerField(default=0)),
                ('timestamp', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Keyword score',
                'verbose_name_plural': 'Keyword scores',
                'ordering': ['-priority_score'],
                'indexes': [
                    models.Index(fields=['-priority_score'], name='seo_intel_ks2_priority_idx'),
                    models.Index(fields=['keyword'], name='seo_intel_ks2_keyword_idx'),
                ],
            },
        ),
    ]
