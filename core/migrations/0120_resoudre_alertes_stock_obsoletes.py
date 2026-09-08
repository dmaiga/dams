"""
Clôture les alertes au type_alerte obsolète « stock ».

Avant le 13/08/2026, le moteur de surveillance (monitoring) émettait une seule
alerte de type « stock » pour les trois emplacements. Le type a ensuite été
découpé en « stock_entrepot » / « stock_superviseur » / « stock_agent », mais
les anciennes lignes « stock » restées ACTIVE ne sont plus gérées par aucun
code (ni rafraîchies, ni résolues) et polluent la table. On les passe RESOLUE.
"""
from django.db import migrations
from django.utils import timezone


def resoudre_alertes_stock(apps, schema_editor):
    Alerte = apps.get_model("core", "Alerte")
    Alerte.objects.filter(type_alerte="stock", statut="ACTIVE").update(
        statut="RESOLUE",
        date_resolution=timezone.now(),
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0119_transfertportefeuilleagent_lignetransfertagent"),
    ]

    operations = [
        migrations.RunPython(resoudre_alertes_stock, noop),
    ]
