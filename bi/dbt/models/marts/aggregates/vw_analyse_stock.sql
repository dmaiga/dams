-- Dashboard 5 (Stock & Fournisseur). Grain = produit x fournisseur, snapshot courant
-- (KPI-401, KPI-402 ; couvre valeur stock et jours en stock). Marge par fournisseur (KPI-403
-- à KPI-405) se construit directement sur fct_ventes + dim_fournisseur côté Metabase — grain
-- différent (vente vs lot en stock), pas de bénéfice à forcer les deux dans une seule vue.
select
    s.produit_id,
    p.nom as produit_nom,
    s.fournisseur_id,
    f.nom as fournisseur_nom,
    sum(s.quantite_restante) as quantite_restante,
    sum(s.valeur_stock) as valeur_stock,
    round(avg(s.jours_en_stock), 1) as jours_en_stock_moyen
from {{ ref('fct_stocks') }} s
left join {{ ref('dim_produit') }} p on s.produit_id = p.produit_id
left join {{ ref('dim_fournisseur') }} f on s.fournisseur_id = f.fournisseur_id
group by s.produit_id, p.nom, s.fournisseur_id, f.nom
order by valeur_stock desc nulls last
