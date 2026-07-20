-- Grain = 1 ligne par lot (snapshot courant, pas d'historique quotidien natif — limite actée
-- dans sprints/SPRINT_1_Fondations.md, dbt snapshot à évaluer en Sprint 2).
-- Quantité vendue recalculée depuis Vente (équivalent DetailDistribution.quantite_restante_calculee),
-- PAS depuis le champ stocké quantite_vendue qui peut être désynchronisé selon le chemin de vente
-- emprunté côté DAMS (architecte/REFERENCE_TECHNIQUE_BI.md §4.1, R13).
with lots as (
    select * from {{ ref('stg_lots') }}
),

detail as (
    select * from {{ ref('stg_detail_distribution') }}
),

ventes as (
    select * from {{ ref('stg_ventes') }}
),

vendu_par_lot as (
    select
        dt.lot_id,
        sum(v.quantite) as quantite_vendue_recalculee
    from ventes v
    inner join detail dt on v.detail_distribution_id = dt.detail_distribution_id
    group by dt.lot_id
),

pertes_par_lot as (
    select
        lot_id,
        sum(quantite_perdue) as quantite_perdue_totale
    from {{ ref('stg_pertes') }}
    group by lot_id
)

select
    l.lot_id,
    l.produit_id,
    l.fournisseur_id,
    l.quantite_initiale,
    l.quantite_restante,
    coalesce(vpl.quantite_vendue_recalculee, 0) as quantite_vendue,
    coalesce(ppl.quantite_perdue_totale, 0) as quantite_perdue,
    l.prix_achat_unitaire,
    l.quantite_restante * l.prix_achat_unitaire as valeur_stock,
    l.date_reception,
    (current_date - l.date_reception) as jours_en_stock
from lots l
left join vendu_par_lot vpl on l.lot_id = vpl.lot_id
left join pertes_par_lot ppl on l.lot_id = ppl.lot_id
