# Generated manually — VwPerformanceAgent expose jours_ouvres (jours ouvrés réels du mois,
# dénominateur du KPI 50kg/jour, cf. dbt_bi/models/marts/aggregates/vw_performance_agent.sql).
# managed=False : aucun DDL réel, uniquement l'état de migration Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0006_vwperformancesuperviseur_mois'),
    ]

    operations = [
        migrations.AddField(
            model_name='vwperformanceagent',
            name='jours_ouvres',
            field=models.IntegerField(null=True),
        ),
    ]
