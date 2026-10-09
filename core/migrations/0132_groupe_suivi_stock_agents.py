from django.db import migrations

GROUPE = "Suivi stock agents"
USERNAMES = ("jeanclaude.sup",)


def creer_groupe(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    groupe, _ = Group.objects.get_or_create(name=GROUPE)
    for username in USERNAMES:
        for user in User.objects.filter(username__iexact=username):
            user.groups.add(groupe)


def supprimer_groupe(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.filter(name=GROUPE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0131_groupe_correcteurs_ventes'),
    ]

    operations = [
        migrations.RunPython(creer_groupe, supprimer_groupe),
    ]
