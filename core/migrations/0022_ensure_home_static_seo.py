from django.db import migrations


def ensure_static_seo_entries(apps, schema_editor):
    StaticPageSEO = apps.get_model("core", "StaticPageSEO")
    defaults = [
        ("home", "Home"),
        ("our-team", "Our Team"),
        ("about-us", "About Us"),
        ("services", "Services"),
        ("insurance", "Insurance & Payment"),
        ("contact-us", "Contact Us"),
        ("faq", "Frequently Asked Questions"),
    ]
    for slug, page_name in defaults:
        StaticPageSEO.objects.get_or_create(slug=slug, defaults={"page_name": page_name})


def remove_home_entry(apps, schema_editor):
    StaticPageSEO = apps.get_model("core", "StaticPageSEO")
    StaticPageSEO.objects.filter(slug="home").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_staticpageseo_image_file"),
    ]

    operations = [
        migrations.RunPython(ensure_static_seo_entries, remove_home_entry),
    ]
