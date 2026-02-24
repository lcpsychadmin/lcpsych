from django.db import migrations

PROVIDERS = [
    "Aetna",
    "Anthem BCBS",
    "Humana",
    "Lyra",
    "Medical Mutual",
    "Medicare",
    "MedBen",
    "Optum",
    "Tricare",
    "United Healthcare",
    "Western & Southern",
]


def seed_providers(apps, schema_editor):
    Provider = apps.get_model("core", "InsuranceProvider")
    for order, name in enumerate(PROVIDERS, start=1):
        Provider.objects.update_or_create(name=name, defaults={"order": order, "is_active": True})


def unseed_providers(apps, schema_editor):
    Provider = apps.get_model("core", "InsuranceProvider")
    Provider.objects.filter(name__in=PROVIDERS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_insuranceprovider"),
    ]

    operations = [
        migrations.RunPython(seed_providers, reverse_code=unseed_providers),
    ]
