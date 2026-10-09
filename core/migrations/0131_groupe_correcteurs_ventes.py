from django.db import migrations

GROUPE = "Correcteurs ventes"
USERNAMES = ("abdoulaye.kone", "modibo.sidibe")


def creer_groupe(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    groupe, _ = Group.objects.get_or_create(name=GROUPE)
    for username in USERNAMES:
        # iexact : « Abdoulaye.kone » et « abdoulaye.kone » désignent la même personne.
        for user in User.objects.filter(username__iexact=username):
            user.groups.add(groupe)


def supprimer_groupe(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.filter(name=GROUPE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0130_correction_scission'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(creer_groupe, supprimer_groupe),
    ]
