import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lcpsych.settings")
django.setup()

from core.models import InspirationalQuote, CompanyQuote

inspirational_defaults = {
    "quote": (
        "Say yes. Whatever it is, say yes with your whole heart & simple as it sounds, "
        "that's all the excuse life needs to grab you by the hands & start to dance."
    ),
    "author": "Brian Andreas",
}

company_defaults = {
    "quote": "Your mental health is a journey, not a destination. We're here to walk with you every step of the way.",
    "author": "L+C Psychological Services",
}

insp, insp_created = InspirationalQuote.objects.get_or_create(is_active=True, defaults=inspirational_defaults)
comp, comp_created = CompanyQuote.objects.get_or_create(is_active=True, defaults=company_defaults)

insp_updates = []
if not insp.quote:
    insp.quote = inspirational_defaults["quote"]
    insp_updates.append("quote")
if not insp.author:
    insp.author = inspirational_defaults["author"]
    insp_updates.append("author")
if not insp.is_active:
    insp.is_active = True
    insp_updates.append("is_active")
if insp_updates:
    insp.save(update_fields=insp_updates)

comp_updates = []
if not comp.quote:
    comp.quote = company_defaults["quote"]
    comp_updates.append("quote")
if not comp.author:
    comp.author = company_defaults["author"]
    comp_updates.append("author")
if not comp.is_active:
    comp.is_active = True
    comp_updates.append("is_active")
if comp_updates:
    comp.save(update_fields=comp_updates)

print(
    {
        "inspirational": {"created": insp_created, "id": insp.pk, "updated_fields": insp_updates},
        "company": {"created": comp_created, "id": comp.pk, "updated_fields": comp_updates},
    }
)
