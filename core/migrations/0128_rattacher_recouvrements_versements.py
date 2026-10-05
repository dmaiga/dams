from django.db import migrations


def rattacher(apps, schema_editor):
    """Rattache les anciens recouvrements à leur versement (même acteur, même horodatage)."""
    Versement = apps.get_model('core', 'VersementBancaire')
    Recouvrement = apps.get_model('core', 'RecouvrementSuperviseur')
    for v in Versement.objects.exclude(effectue_par=None):
        Recouvrement.objects.filter(
            versement__isnull=True,
            rot_id=v.effectue_par_id,
            date_recouvrement=v.date_versement_reelle,
        ).update(versement=v)


class Migration(migrations.Migration):
    dependencies = [('core', '0127_recouvrementsuperviseur_versement')]
    operations = [migrations.RunPython(rattacher, migrations.RunPython.noop)]
