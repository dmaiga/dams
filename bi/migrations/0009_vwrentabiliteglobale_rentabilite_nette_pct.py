# Generated manually — VwRentabiliteGlobale expose rentabilite_nette_pct (KPI marge nette %,
# cf. dbt_bi/models/marts/aggregates/vw_rentabilite_globale.sql). managed=False : aucun DDL
# réel, uniquement l'état de migration Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0008_ajustementprixachat_lot'),
    ]

    operations = [
        migrations.AddField(
            model_name='vwrentabiliteglobale',
            name='rentabilite_nette_pct',
            field=models.DecimalField(decimal_places=2, max_digits=5, null=True),
        ),
    ]
