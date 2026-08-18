-- Sprint-11 (2026-08-18) : produits vendus par agent, grain = agent x produit x mois. Alimente
-- le bloc "Produits vendus" de la fiche détail agent — mdmaiga a clarifié que "par type" faisait
-- référence au nom du produit (Riz, Oignon...), pas à une vraie catégorie (Produit n'en a pas,
-- décision différée par le PO, cf. dim_produit.sql) : sert à voir quels produits contribuent le
-- plus au volume de l'agent, pas à un regroupement en familles.
-- kg_vendus en NET des pertes (cohérent avec vw_performance_agent.sql, même sprint) : une perte
-- déclarée sur une vente ne doit pas gonfler la contribution apparente de ce produit au volume
-- de l'agent.
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
    row_number() over (order by v.agent_id, v.produit_id, date_trunc('month', v.date_vente)) as ventes_agent_produit_id,
    v.agent_id,
    v.produit_id,
    p.nom as produit_nom,
    date_trunc('month', v.date_vente)::date as mois,
    sum(v.quantite_en_kg - coalesce(pe.kilo_perdu_incentive, 0)) as kg_vendus,
    sum(v.total_vente) as ca_total,
    sum(v.total_vente - v.total_cout_achat) as marge,
    count(*) as nombre_ventes
from ventes v
left join pertes pe on pe.vente_id = v.vente_id
left join produits p on p.produit_id = v.produit_id
group by v.agent_id, v.produit_id, p.nom, date_trunc('month', v.date_vente)
