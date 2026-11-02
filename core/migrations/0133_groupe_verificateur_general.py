from django.db import migrations

GROUPE = "Vérificateur général"


def creer_groupe(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.get_or_create(name=GROUPE)


def supprimer_groupe(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.filter(name=GROUPE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0132_groupe_suivi_stock_agents'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(creer_groupe, supprimer_groupe),
    ]
