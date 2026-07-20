with source as (
    select * from {{ source('dams_prod', 'core_vente') }}
)

select
    id as vente_id,
    agent_id,
    client_id,
    detail_distribution_id,
    stagiaire_id,
    type_vente,
    mode_paiement,
    quantite::numeric(10, 2) as quantite,
    prix_vente_unitaire::numeric(10, 2) as prix_vente_unitaire,
    date_vente::date as date_vente,
    ancienne_vente,
    est_supprime
from source
where est_supprime = false
