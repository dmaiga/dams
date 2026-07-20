-- Grain = 1 ligne core_vente. superviseur_id/produit_id/fournisseur_id/prix_achat_unitaire
-- ne sont PAS des colonnes de core_vente : dérivés via detail_distribution -> distribution_agent
-- (superviseur) et detail_distribution -> lot_entrepot (prix achat, produit, fournisseur).
-- Voir architecte/05_Architecture.md et architecte/REFERENCE_TECHNIQUE_BI.md.
with ventes as (
    select * from {{ ref('stg_ventes') }}
),

detail as (
    select * from {{ ref('stg_detail_distribution') }}
),

distribution as (
    select * from {{ ref('stg_distribution_agent') }}
),

lots as (
    select * from {{ ref('stg_lots') }}
),

produits as (
    select * from {{ ref('stg_produits') }}
)

select
    v.vente_id,
    v.agent_id,
    d.superviseur_id,
    l.produit_id,
    l.fournisseur_id,
    v.date_vente,
    v.quantite,
    -- formule pivot pour tout KPI en kg (objectif 50kg/jour, incentive terrain) :
    -- ne jamais sommer `quantite` brut pour un produit conditionné.
    case
        when p.poids_unitaire_kg is not null then v.quantite * p.poids_unitaire_kg
        else v.quantite
    end as quantite_en_kg,
    l.prix_achat_unitaire,
    v.prix_vente_unitaire,
    (v.prix_vente_unitaire - l.prix_achat_unitaire) as marge_unitaire,
    v.quantite * v.prix_vente_unitaire as total_vente,
    v.quantite * l.prix_achat_unitaire as total_cout_achat,
    v.type_vente,
    v.mode_paiement
from ventes v
left join detail dt on v.detail_distribution_id = dt.detail_distribution_id
left join distribution d on dt.distribution_id = d.distribution_id
left join lots l on dt.lot_id = l.lot_id
left join produits p on l.produit_id = p.produit_id
