from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_gone410url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Modality',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('icon', models.CharField(blank=True, help_text='Optional icon class or emoji.', max_length=100)),
            ],
            options={
                'verbose_name': 'Modality',
                'verbose_name_plural': 'Modalities',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Condition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('icon', models.CharField(blank=True, help_text='Optional icon class or emoji.', max_length=100)),
            ],
            options={
                'verbose_name': 'Condition',
                'verbose_name_plural': 'Conditions',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='officelocation',
            name='modalities',
            field=models.ManyToManyField(
                blank=True,
                help_text='Therapy modalities offered at this office.',
                related_name='offices',
                to='core.modality',
            ),
        ),
        migrations.AddField(
            model_name='officelocation',
            name='conditions',
            field=models.ManyToManyField(
                blank=True,
                help_text='Conditions/presenting concerns treated at this office.',
                related_name='offices',
                to='core.condition',
            ),
        ),
    ]
