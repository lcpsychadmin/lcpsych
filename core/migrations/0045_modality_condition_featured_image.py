from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_modality_condition_content_blocks'),
    ]

    operations = [
        migrations.AddField(
            model_name='modality',
            name='featured_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='modalities/',
                help_text='Card background image for the listing page.',
            ),
        ),
        migrations.AddField(
            model_name='condition',
            name='featured_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='conditions/',
                help_text='Card background image for the listing page.',
            ),
        ),
    ]
