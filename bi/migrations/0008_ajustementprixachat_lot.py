# Generated manually — AjustementPrixAchat pointe désormais directement sur LotEntrepot
# (fournisseur/produit/année/mois dérivés du lot côté dbt) au lieu d'un fournisseur/année/mois
# saisis à la main + reference_lot en texte libre. Table vide en production (0 lignes au
# 23/07/2026) : pas de migration de données nécessaire.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0106_add_agent_terrain_direct_to_affectation'),
        ('bi', '0007_vwperformanceagent_jours_ouvres'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ajustementprixachat',
            name='fournisseur',
        ),
        migrations.RemoveField(
            model_name='ajustementprixachat',
            name='produit',
        ),
        migrations.RemoveField(
            model_name='ajustementprixachat',
            name='reference_lot',
        ),
        migrations.RemoveField(
            model_name='ajustementprixachat',
            name='annee',
        ),
        migrations.RemoveField(
            model_name='ajustementprixachat',
            name='mois',
        ),
        migrations.AddField(
            model_name='ajustementprixachat',
            name='lot',
            field=models.ForeignKey(
                default=None,
                help_text="Lot dont le prix d'achat a été renégocié après réception — "
                "fournisseur, produit, année et mois en sont dérivés automatiquement, rien "
                "d'autre à ressaisir.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ajustements_prix_achat',
                to='core.lotentrepot',
                verbose_name='Lot',
            ),
            preserve_default=False,
        ),
    ]
