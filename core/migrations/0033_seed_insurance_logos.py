from django.db import migrations


def seed_logo_urls(apps, schema_editor):
    Provider = apps.get_model("core", "InsuranceProvider")
    name_to_domain = {
        "Aetna": "aetna.com",
        "Anthem BCBS": "anthem.com",
        "Humana": "humana.com",
        "Lyra": "lyrahealth.com",
        "Medical Mutual": "medmutual.com",
        "Medicare": "medicare.gov",
        "MedBen": "medben.com",
        "Optum": "optum.com",
        "Tricare": "tricare.mil",
        "United Healthcare": "uhc.com",
        "Western & Southern": "westernsouthern.com",
    }

    for name, domain in name_to_domain.items():
        logo_url = f"https://logo.clearbit.com/{domain}"
        for provider in Provider.objects.filter(name__iexact=name):
            if getattr(provider, "logo", None) and provider.logo:
                continue
            if provider.logo_url:
                continue
            provider.logo_url = logo_url
            provider.save(update_fields=["logo_url", "updated"] if hasattr(provider, "updated") else ["logo_url"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_insuranceprovider_logo"),
    ]

    operations = [
        migrations.RunPython(seed_logo_urls, noop),
    ]
