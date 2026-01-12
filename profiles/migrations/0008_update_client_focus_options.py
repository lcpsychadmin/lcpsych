from django.db import migrations


def forwards(apps, schema_editor):
    ClientFocus = apps.get_model('profiles', 'ClientFocus')

    rename_map = {
        'Child': 'Child & Adolescent',
        'Children': 'Child & Adolescent',
        'Teens': 'Child & Adolescent',
        'Adults': 'Adult',
    }

    for old_name, new_name in rename_map.items():
        try:
            focus = ClientFocus.objects.get(name=old_name)
            focus.name = new_name
            if new_name == 'Child & Adolescent' and not focus.description:
                focus.description = 'Supports children and adolescents.'
            if new_name == 'Adult' and not focus.description:
                focus.description = 'Works with individual adults.'
            focus.save()
        except ClientFocus.DoesNotExist:
            continue

    ClientFocus.objects.get_or_create(
        name='Child & Adolescent',
        defaults={'description': 'Supports children and adolescents.'},
    )
    ClientFocus.objects.get_or_create(
        name='Adult',
        defaults={'description': 'Works with individual adults.'},
    )


def backwards(apps, schema_editor):
    # No-op: retain normalized client focus names
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('profiles', '0007_therapistprofile_services'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
