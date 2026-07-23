# Generated manually — VwPerformanceSuperviseur passe en grain superviseur x mois (cf.
# dbt_bi/models/marts/aggregates/vw_performance_superviseur.sql). managed=False : aucun DDL
# réel, uniquement l'état de migration Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0005_vwmargefournisseur_produit'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vwperformancesuperviseur',
            name='superviseur_id',
        ),
        migrations.AddField(
            model_name='vwperformancesuperviseur',
            name='superviseur_mois_id',
            field=models.IntegerField(default=0, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwperformancesuperviseur',
            name='superviseur_id',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwperformancesuperviseur',
            name='mois',
            field=models.DateField(default='2026-01-01'),
            preserve_default=False,
        ),
    ]
