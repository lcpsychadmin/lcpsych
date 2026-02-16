from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def create_default_category(apps, schema_editor):
    Category = apps.get_model('blog', 'Category')
    if not Category.objects.exists():
        Category.objects.create(name='General', slug='general')


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_post_feature_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='post',
            name='categories',
            field=models.ManyToManyField(blank=True, related_name='posts', to='blog.category'),
        ),
        migrations.RunPython(create_default_category, migrations.RunPython.noop),
    ]
