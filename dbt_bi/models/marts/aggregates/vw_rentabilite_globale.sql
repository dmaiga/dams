-- Dashboard 1 (Santé Globale). Grain = mois. Rentabilité nette = marge brute - salaires - dépenses
-- (KPI-001 à KPI-009, bi/07_Dictionnaire_KPI_Technique.md). full outer join car un mois peut avoir
-- des ventes sans dépenses (ou l'inverse) sans que la ligne mois disparaisse.
-- salaires_pct/depenses_pct (20/07/2026) : KPI-006/008, ajoutés pour que l'app bi n'ait plus à
-- recalculer ces ratios en Python (règle "aucun ratio recalculé côté Django").
-- rentabilite_nette_pct (23/07/2026) : même règle, pour le KPI marge nette % de la 2e section
-- du dashboard Santé Globale (priorité de cette phase = marge brute, marge nette = vue
-- complémentaire, cf. décision produit du 23/07/2026).
-- cout_salaires (23/07/2026, dbt-3) restreint à type_agent in ('terrain', 'agent_gros') —
-- décision produit : le KPI global de coût salarial ne couvre que les agents "détail"/"gros",
-- pas les superviseurs (leur coût équipe est suivi séparément via KPI-203/vw_performance_superviseur)
-- ni les agents polyvalents (hors périmètre de ce KPI).
with ventes_mensuel as (
    select
        date_trunc('month', date_vente)::date as mois,
        sum(total_vente) as ca,
        sum(total_cout_achat) as cout_achat,
        sum(total_vente - total_cout_achat) as marge_brute
    from {{ ref('fct_ventes') }}
    group by 1
),

salaires_mensuel as (
    select
        date_trunc('month', date_debut)::date as mois,
        sum(salaire_total) as cout_salaires
    from {{ ref('fct_salaires') }}
    where type_agent in ('terrain', 'agent_gros')
    group by 1
),

depenses_mensuel as (
    select
        date_trunc('month', date_depense)::date as mois,
        sum(montant) as cout_depenses
    from {{ ref('fct_depenses') }}
    group by 1
)

select
    coalesce(v.mois, s.mois, d.mois) as mois,
    coalesce(v.ca, 0) as ca,
    coalesce(v.cout_achat, 0) as cout_achat,
    coalesce(v.marge_brute, 0) as marge_brute,
    case
        when coalesce(v.ca, 0) = 0 then null
        else round(100.0 * v.marge_brute / v.ca, 2)
    end as marge_pct,
    coalesce(s.cout_salaires, 0) as cout_salaires,
    case
        when coalesce(v.ca, 0) = 0 then null
        else round(100.0 * coalesce(s.cout_salaires, 0) / v.ca, 2)
    end as salaires_pct,
    coalesce(d.cout_depenses, 0) as cout_depenses,
    case
        when coalesce(v.ca, 0) = 0 then null
        else round(100.0 * coalesce(d.cout_depenses, 0) / v.ca, 2)
    end as depenses_pct,
    coalesce(v.marge_brute, 0) - coalesce(s.cout_salaires, 0) - coalesce(d.cout_depenses, 0) as rentabilite_nette,
    case
        when coalesce(v.ca, 0) = 0 then null
        else round(
            100.0 * (
                coalesce(v.marge_brute, 0) - coalesce(s.cout_salaires, 0) - coalesce(d.cout_depenses, 0)
            ) / v.ca,
            2
        )
    end as rentabilite_nette_pct
from ventes_mensuel v
full outer join salaires_mensuel s on v.mois = s.mois
full outer join depenses_mensuel d on coalesce(v.mois, s.mois) = d.mois
order by mois
