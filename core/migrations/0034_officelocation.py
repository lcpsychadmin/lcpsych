from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_seed_insurance_logos'),
        ('geo', '0001_initial'),
        ('profiles', '0013_therapistprofile_locations'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficeLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200, help_text="Short display name, e.g. 'Florence, KY'")),
                ('slug', models.SlugField(max_length=200, unique=True, help_text='URL slug for /contact-us/<slug>/')),
                ('section_heading', models.CharField(max_length=255, blank=True, help_text="Hero heading for this office's contact page. Defaults to the office name.")),
                ('map_embed_url', models.URLField(max_length=1000, blank=True, help_text='Full Google Maps embed URL for the iframe src.')),
                ('directions_url', models.URLField(max_length=1000, blank=True, help_text="Google Maps directions URL for the 'Get Directions' button.")),
                ('address_line1', models.CharField(max_length=200, blank=True, help_text="Street address (e.g. '6900 Houston Rd.')")),
                ('address_line2', models.CharField(max_length=200, blank=True, help_text="Suite/building (e.g. 'Building 500 Suite 11')")),
                ('address_city', models.CharField(max_length=100, blank=True)),
                ('address_state', models.CharField(max_length=50, blank=True, help_text="Two-letter state code (e.g. 'KY')")),
                ('address_zip', models.CharField(max_length=20, blank=True)),
                ('office_hours_title', models.CharField(max_length=200, default='Office hours')),
                ('office_hours', models.TextField(blank=True, help_text="One entry per line, e.g. 'Mon – Thurs: 8AM – 9PM'.")),
                ('phone_label', models.CharField(max_length=100, default='Office')),
                ('phone_number', models.CharField(max_length=50, blank=True)),
                ('fax_label', models.CharField(max_length=100, default='Fax')),
                ('fax_number', models.CharField(max_length=50, blank=True)),
                ('email_label', models.CharField(max_length=100, default='Email')),
                ('email_address', models.EmailField(blank=True)),
                ('cta_label', models.CharField(max_length=120, default='Schedule Online')),
                ('cta_url', models.URLField(max_length=500, blank=True, default='https://www.therapyportal.com/p/lcpsych41042/appointments/availability/')),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')),
                ('therapists', models.ManyToManyField(
                    blank=True,
                    help_text='Therapists who see clients at this location.',
                    related_name='offices',
                    to='profiles.therapistprofile',
                )),
                ('geo_states', models.ManyToManyField(
                    blank=True,
                    help_text='States served from this office (for areas-served linking).',
                    related_name='offices',
                    to='geo.geostate',
                )),
                ('geo_locations', models.ManyToManyField(
                    blank=True,
                    help_text='Specific cities/counties served from this office.',
                    related_name='offices',
                    to='geo.geolocation',
                )),
            ],
            options={
                'verbose_name': 'Office location',
                'verbose_name_plural': 'Office locations',
                'ordering': ['order', 'name'],
            },
        ),
    ]
