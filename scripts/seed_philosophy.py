import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lcpsych.settings")
django.setup()

from core.models import OurPhilosophy

philosophy_body = (
    "<p>These connections change throughout our lives. At times we focus on connecting to family and friends, while during other life phases we focus on connecting to school and work. We view our therapy in Northern Kentucky as a way of helping people to learn new skills and strengthen their connections.</p>"
    "<p>L+C Psychological Services offers a full line of mental health services for all ages. We provide both short-term assessment to identify treatment needs, as well as ongoing treatment in multiple modalities. We also engage collaboratively with other providers as needed to create a strong continuum of care.</p>"
)

title = "Our philosophy of treatment is that people have a need to be connected."

section, created = OurPhilosophy.objects.get_or_create(
    is_active=True,
    defaults={
        "title": title,
        "body": philosophy_body,
    },
)

updated = []
if not section.title:
    section.title = title
    updated.append("title")
if not section.body:
    section.body = philosophy_body
    updated.append("body")
if not section.is_active:
    section.is_active = True
    updated.append("is_active")

if updated:
    section.save(update_fields=updated)

print({"created": created, "section_id": section.pk, "updated_fields": updated})
