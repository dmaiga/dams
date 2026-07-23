# Generated manually — nouvelle vue bi_.vw_rentabilite_journaliere (grain jour, graphique de
# tendance de Santé Globale uniquement), cf.
# dbt_bi/models/marts/aggregates/vw_rentabilite_journaliere.sql. managed=False : aucun DDL réel.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bi', '0009_vwrentabiliteglobale_rentabilite_nette_pct'),
    ]

    operations = [
        migrations.CreateModel(
            name='VwRentabiliteJournaliere',
            fields=[
                ('jour', models.DateField(primary_key=True, serialize=False)),
                ('ca', models.DecimalField(decimal_places=2, max_digits=15)),
                ('cout_achat', models.DecimalField(decimal_places=2, max_digits=15)),
                ('marge_brute', models.DecimalField(decimal_places=2, max_digits=15)),
                ('cout_depenses', models.DecimalField(decimal_places=2, max_digits=15)),
            ],
            options={
                'db_table': 'bi_"."vw_rentabilite_journaliere',
                'managed': False,
            },
        ),
    ]
