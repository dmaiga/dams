-- Dashboard 4 (Performance Agent vs Objectif 50 kg/jour). Grain = agent (KPI-301 à KPI-306).
-- kg_par_jour = kg_vendus / jours distincts avec au moins 1 vente (pas jours calendaires du mois,
-- pour ne pas pénaliser un agent sur ses jours de repos). Seuils du statut : bi/08_Dashboard_Catalog.md
-- (Dashboard 4). Restreint aux types d'agents réellement soumis à cet objectif terrain/vente directe
-- (exclut direction/rot/entrepot/stagiaire/gestionnaire_stock, non concernés par ce KPI).
with ventes_agent as (
    select
        agent_id,
        sum(total_vente - total_cout_achat) as marge,
        sum(quantite_en_kg) as kg_vendus,
        count(distinct date_vente) as jours_actifs
    from {{ ref('fct_ventes') }}
    group by agent_id
),

incentive_agent as (
    select
        agent_id,
        sum(incentive) as incentive_totale
    from {{ ref('fct_salaires') }}
    group by agent_id
)

select
    a.agent_id,
    a.nom_complet,
    a.type_agent,
    coalesce(va.kg_vendus, 0) as kg_vendus,
    coalesce(va.jours_actifs, 0) as jours_actifs,
    case
        when coalesce(va.jours_actifs, 0) = 0 then null
        else round(va.kg_vendus / va.jours_actifs, 2)
    end as kg_par_jour,
    case
        when coalesce(va.jours_actifs, 0) = 0 then null
        when va.kg_vendus / va.jours_actifs >= 50 then 'atteint'
        when va.kg_vendus / va.jours_actifs >= 40 then 'proche'
        else 'sous_objectif'
    end as statut_objectif_50kg,
    coalesce(va.marge, 0) as marge,
    coalesce(ia.incentive_totale, 0) as incentive,
    coalesce(va.marge, 0) - coalesce(ia.incentive_totale, 0) as rentabilite_agent,
    case
        when coalesce(va.marge, 0) = 0 then null
        else round(100.0 * coalesce(ia.incentive_totale, 0) / va.marge, 2)
    end as ratio_incentive_marge_pct
from {{ ref('dim_agent') }} a
left join ventes_agent va on a.agent_id = va.agent_id
left join incentive_agent ia on a.agent_id = ia.agent_id
where a.type_agent in ('terrain', 'agent_gros', 'agent_polivalent')
order by kg_par_jour desc nulls last
