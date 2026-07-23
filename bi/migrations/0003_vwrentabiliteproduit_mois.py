# Generated manually — VwRentabiliteProduit passe en grain produit x mois (cf.
# dbt_bi/models/marts/aggregates/vw_rentabilite_produit.sql). managed=False : aucun DDL réel,
# uniquement l'état de migration Django (même principe que 0002_vwdepensescategorie.py).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0002_vwdepensescategorie'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vwrentabiliteproduit',
            name='produit_id',
        ),
        migrations.AddField(
            model_name='vwrentabiliteproduit',
            name='produit_mois_id',
            field=models.IntegerField(default=0, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwrentabiliteproduit',
            name='produit_id',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwrentabiliteproduit',
            name='mois',
            field=models.DateField(default='2026-01-01'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='vwrentabiliteproduit',
            name='produit_nom',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
