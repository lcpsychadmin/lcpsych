from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0011_category_and_post_categories'),
        ('profiles', '0013_therapistprofile_locations'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='therapist_author',
            field=models.ForeignKey(
                blank=True,
                help_text='The therapist profile to credit and feature in the "About the Author" section.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='authored_posts',
                to='profiles.therapistprofile',
            ),
        ),
    ]
