-- Sprint-11 suite (26/08/2026) : miroir hebdomadaire (semaine ISO lundi-dimanche, comme
-- vw_performance_agent_semaine.sql) de vw_ventes_agent_produit.sql — grain = agent x produit x
-- semaine. Demandé pour que le bloc "Produits vendus" et les courbes de tendance de la fiche
-- détail équipe (bi/views.py::dashboard_superviseur_detail) suivent la semaine sélectionnée au
-- lieu de rester figés sur le grain mensuel. Même règle kg net des pertes que le grain mensuel.
with ventes as (
    select * from {{ ref('fct_ventes') }}
),

pertes as (
    select * from {{ ref('stg_pertes') }}
),

produits as (
    select * from {{ ref('dim_produit') }}
)

select
    row_number() over (order by v.agent_id, v.produit_id, date_trunc('week', v.date_vente)) as ventes_agent_produit_semaine_id,
    v.agent_id,
    v.produit_id,
    p.nom as produit_nom,
    date_trunc('week', v.date_vente)::date as semaine,
    sum(v.quantite_en_kg - coalesce(pe.kilo_perdu_incentive, 0)) as kg_vendus,
    sum(v.total_vente) as ca_total,
    sum(v.total_vente - v.total_cout_achat) as marge,
    count(*) as nombre_ventes
from ventes v
left join pertes pe on pe.vente_id = v.vente_id
left join produits p on p.produit_id = v.produit_id
group by v.agent_id, v.produit_id, p.nom, date_trunc('week', v.date_vente)
