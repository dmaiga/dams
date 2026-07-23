-- Dashboard 1 (Santé Globale), volet graphique uniquement (23/07/2026, dbt-8). Grain = jour.
-- Sert exclusivement au graphique de tendance quand un mois précis est filtré : le grain
-- mensuel de vw_rentabilite_globale réduit alors la série à un seul point, ce qui rend un
-- graphique de "tendance" absurde. Pas de salaires ici (fct_salaires.date_debut représente une
-- période de paie, pas un jour précis — non pertinent à ce grain) ; le reste de l'app (KPI,
-- filtres, autres dashboards) reste au grain mensuel, ce modèle ne sert QUE ce graphique.
with ventes_quotidien as (
    select
        date_vente as jour,
        sum(total_vente) as ca,
        sum(total_cout_achat) as cout_achat,
        sum(total_vente - total_cout_achat) as marge_brute
    from {{ ref('fct_ventes') }}
    group by 1
),

depenses_quotidien as (
    select
        date_depense as jour,
        sum(montant) as cout_depenses
    from {{ ref('fct_depenses') }}
    group by 1
)

select
    coalesce(v.jour, d.jour) as jour,
    coalesce(v.ca, 0) as ca,
    coalesce(v.cout_achat, 0) as cout_achat,
    coalesce(v.marge_brute, 0) as marge_brute,
    coalesce(d.cout_depenses, 0) as cout_depenses
from ventes_quotidien v
full outer join depenses_quotidien d on v.jour = d.jour
order by jour
