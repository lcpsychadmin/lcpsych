from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_modality_condition_office_m2m'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModalityContentBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first.')),
                ('heading', models.CharField(help_text='Section heading', max_length=200)),
                ('body', models.TextField(help_text='Paragraph text for this section')),
                ('modality', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_blocks', to='core.modality')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='ConditionContentBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first.')),
                ('heading', models.CharField(help_text='Section heading', max_length=200)),
                ('body', models.TextField(help_text='Paragraph text for this section')),
                ('condition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_blocks', to='core.condition')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
