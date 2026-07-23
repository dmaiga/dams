# Generated manually — VwMargeFournisseur gagne la dimension produit (grain fournisseur x
# produit x mois), cf. dbt_bi/models/marts/aggregates/vw_marge_fournisseur.sql. managed=False :
# aucun DDL réel, uniquement l'état de migration Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0004_vwperformanceagent_mois'),
    ]

    operations = [
        migrations.AddField(
            model_name='vwmargefournisseur',
            name='produit_id',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='vwmargefournisseur',
            name='produit_nom',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
