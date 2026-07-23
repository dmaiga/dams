# Generated manually — VwPerformanceAgent passe en grain agent x mois, avec exposition du
# superviseur (cf. dbt_bi/models/marts/aggregates/vw_performance_agent.sql). managed=False :
# aucun DDL réel, uniquement l'état de migration Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0003_vwrentabiliteproduit_mois'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vwperformanceagent',
            name='agent_id',
        ),
        migrations.AddField(
            model_name='vwperformanceagent',
            name='agent_mois_id',
            field=models.IntegerField(default=0, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwperformanceagent',
            name='agent_id',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vwperformanceagent',
            name='superviseur_id',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='vwperformanceagent',
            name='superviseur_nom',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='vwperformanceagent',
            name='mois',
            field=models.DateField(default='2026-01-01'),
            preserve_default=False,
        ),
    ]
