-- Dashboard 2 (Rentabilité Produit). Grain = produit (KPI-101 à KPI-106).
-- rotation_stock = CA produit / stock moyen (valeur) — approxime KPI-105, stock moyen calculé
-- sur le snapshot courant de fct_stocks faute d'historique quotidien (limite actée Sprint 1).
with ventes_produit as (
    select
        produit_id,
        sum(total_vente) as ca,
        sum(total_cout_achat) as cout_achat,
        sum(total_vente - total_cout_achat) as marge,
        sum(quantite_en_kg) as quantite_vendue_kg
    from {{ ref('fct_ventes') }}
    where produit_id is not null
    group by produit_id
),

stock_moyen_produit as (
    select
        produit_id,
        avg(valeur_stock) as stock_moyen
    from {{ ref('fct_stocks') }}
    group by produit_id
)

select
    p.produit_id,
    p.nom as produit_nom,
    coalesce(vp.ca, 0) as ca,
    coalesce(vp.cout_achat, 0) as cout_achat,
    coalesce(vp.marge, 0) as marge,
    case
        when coalesce(vp.ca, 0) = 0 then null
        else round(100.0 * vp.marge / vp.ca, 2)
    end as marge_pct,
    coalesce(vp.quantite_vendue_kg, 0) as quantite_vendue_kg,
    sm.stock_moyen,
    case
        when coalesce(sm.stock_moyen, 0) = 0 then null
        else round(coalesce(vp.ca, 0) / sm.stock_moyen, 2)
    end as rotation_stock
from {{ ref('dim_produit') }} p
left join ventes_produit vp on p.produit_id = vp.produit_id
left join stock_moyen_produit sm on p.produit_id = sm.produit_id
order by marge desc nulls last
