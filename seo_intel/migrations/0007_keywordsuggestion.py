from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo_intel', '0006_lcpsychit'),
    ]

    operations = [
        migrations.CreateModel(
            name='KeywordSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_keyword', models.CharField(max_length=500)),
                ('suggestion', models.CharField(max_length=500, unique=True)),
                ('source_type', models.CharField(
                    choices=[('paa', 'People Also Ask'), ('related', 'Related Search')],
                    max_length=10,
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('used_as_seed', models.BooleanField(
                    default=False,
                    help_text='True once this suggestion has been promoted to a KeywordSeed.',
                )),
            ],
            options={
                'verbose_name': 'Keyword suggestion',
                'verbose_name_plural': 'Keyword suggestions',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['source_type'], name='seo_intel_ks_type_idx'),
                    models.Index(fields=['used_as_seed'], name='seo_intel_ks_seed_idx'),
                    models.Index(fields=['-timestamp'], name='seo_intel_ks_ts_idx'),
                ],
            },
        ),
    ]
