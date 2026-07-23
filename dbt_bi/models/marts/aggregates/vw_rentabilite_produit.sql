-- Dashboard 2 (Rentabilité Produit). Grain = produit x mois (KPI-101 à KPI-106) — aligné sur
-- le pattern vw_marge_fournisseur (clé surrogate row_number, base = CTE de ventes) pour
-- permettre le filtre mois côté Django. Conséquence acceptée : un produit sans vente sur un
-- mois donné n'a pas de ligne pour ce mois (comme les fournisseurs dans vw_marge_fournisseur).
-- rotation_stock = CA produit / stock moyen (valeur) — approxime KPI-105, stock moyen calculé
-- sur le snapshot courant de fct_stocks faute d'historique quotidien (limite actée Sprint 1,
-- donc identique pour tous les mois d'un même produit).
with ventes_produit as (
    select
        produit_id,
        date_trunc('month', date_vente)::date as mois,
        sum(total_vente) as ca,
        sum(total_cout_achat) as cout_achat,
        sum(total_vente - total_cout_achat) as marge,
        sum(quantite_en_kg) as quantite_vendue_kg
    from {{ ref('fct_ventes') }}
    where produit_id is not null
    group by produit_id, date_trunc('month', date_vente)::date
),

stock_moyen_produit as (
    select
        produit_id,
        avg(valeur_stock) as stock_moyen
    from {{ ref('fct_stocks') }}
    group by produit_id
)

select
    row_number() over (order by vp.produit_id, vp.mois) as produit_mois_id,
    vp.produit_id,
    p.nom as produit_nom,
    vp.mois,
    vp.ca,
    vp.cout_achat,
    vp.marge,
    case
        when vp.ca = 0 then null
        else round(100.0 * vp.marge / vp.ca, 2)
    end as marge_pct,
    vp.quantite_vendue_kg,
    sm.stock_moyen,
    case
        when coalesce(sm.stock_moyen, 0) = 0 then null
        else round(vp.ca / sm.stock_moyen, 2)
    end as rotation_stock
from ventes_produit vp
left join {{ ref('dim_produit') }} p on p.produit_id = vp.produit_id
left join stock_moyen_produit sm on p.produit_id = sm.produit_id
order by vp.mois, marge desc nulls last
