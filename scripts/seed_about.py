import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lcpsych.settings")
django.setup()

from core.models import AboutSection

about_body = (
    '<p class="vc_custom_heading vc_do_custom_heading">At L+C Psychological Services, we seek to provide an environment that is supportive and allows you to feel connected emotionally.</p>'
    '<p>We know that connections in life are what power our relationships in all aspects of our lives. Our hope is that you will experience these positive connections with our clinicians and gain the skills needed to improve all other connections in your life.</p>'
    '<p>L+C Psychological Services is proud to serve our clients providing psychological evaluation and therapy in Northern Kentucky and online therapy in Kentucky to adults, adolescents, and children. L+C Psychological Services was born from the vision of Dr. Kirk Little and Dr. Suzanne Collins following their work together for over a decade at Little Psychological Services.</p>'
)

mission_body = (
    '<p>Our mission at L+C Psychological Services is to provide a comfortable and safe environment for those who need to reconnect in their lives. We are dedicated psychologists and therapists providing guidance and support to clients seeking to heal and grow. We believe that we are able to connect with our clients to help them to be their best selves.</p>'
)

section, created = AboutSection.objects.get_or_create(
    is_active=True,
    defaults={
        "about_title": "About Us",
        "about_body": about_body,
        "mission_title": "Our Mission",
        "mission_body": mission_body,
        "cta_label": "Schedule Your First Appointment Today",
        "cta_url": "https://www.therapyportal.com/p/lcpsych41042/appointments/availability/",
    },
)
updated = []
if not section.about_body:
    section.about_body = about_body
    updated.append("about_body")
if not section.mission_body:
    section.mission_body = mission_body
    updated.append("mission_body")
if not section.about_title:
    section.about_title = "About Us"
    updated.append("about_title")
if not section.mission_title:
    section.mission_title = "Our Mission"
    updated.append("mission_title")
if not section.cta_label:
    section.cta_label = "Schedule Your First Appointment Today"
    updated.append("cta_label")
if not section.cta_url:
    section.cta_url = "https://www.therapyportal.com/p/lcpsych41042/appointments/availability/"
    updated.append("cta_url")
if not section.is_active:
    section.is_active = True
    updated.append("is_active")
if updated:
    section.save(update_fields=updated)

print({"created": created, "section_id": section.pk, "updated_fields": updated})
