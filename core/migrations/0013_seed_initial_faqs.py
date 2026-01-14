from django.db import migrations


FAQ_SEED = [
    {
        "question": "What insurance do you accept?",
        "answer": (
            "<ul><li>We accept most major insurances, including, but not limited to: "
            "Anthem Blue Cross &amp; Blue Shield, Humana, Medical Mutual, etc. "
            "We do accept Medicare. We do <strong>not</strong> accept Medicaid. "
            "Please call the office to verify your specific benefits.</li></ul>"
        ),
        "order": 1,
    },
    {
        "question": "What should I expect at the first appointment?",
        "answer": (
            "<ul><li>You should expect to be greeted and welcomed by your psychologist. "
            "The session will be approximately 55 minutes. This time will be used to discuss "
            "your presenting concerns, gather some background information, and make a therapeutic plan."  # noqa: E501
            "</li></ul>"
        ),
        "order": 2,
    },
    {
        "question": "What if I feel nervous about coming to therapy?",
        "answer": (
            "<ul><li>Many people feel nervous when they start therapy, as it is a new and different "
            "experience for them. You will be welcomed and guided through the entire process by your therapist."  # noqa: E501
            "</li></ul>"
        ),
        "order": 3,
    },
    {
        "question": "What is the cost of attending therapy?",
        "answer": (
            "<ul><li>An initial intake session is $240 and subsequent therapy sessions are $210. "
            "Testing and assessments are based on the hours needed to complete the assessment."  # noqa: E501
            "</li></ul>"
        ),
        "order": 4,
    },
]


def seed(apps, schema_editor):
    FAQItem = apps.get_model("core", "FAQItem")
    if FAQItem.objects.exists():
        return
    for item in FAQ_SEED:
        FAQItem.objects.create(
            question=item["question"],
            answer=item["answer"],
            order=item["order"],
            is_active=True,
        )


def unseed(apps, schema_editor):
    FAQItem = apps.get_model("core", "FAQItem")
    FAQItem.objects.filter(question__in=[i["question"] for i in FAQ_SEED]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_faqitem"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
