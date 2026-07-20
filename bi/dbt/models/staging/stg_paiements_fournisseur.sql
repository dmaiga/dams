with source as (
    select * from {{ source('dams_prod', 'core_paiementfournisseur') }}
)

select
    id as paiement_id,
    fournisseur_id,
    lot_id,
    -- champ actif ; le champ "superviseur" existe sur la source mais est déprécié,
    -- jamais écrit par les flux actuels (architecte/REFERENCE_TECHNIQUE_BI.md §1.24) — ignoré ici
    effectue_par_id as agent_id,
    montant::numeric(12, 2) as montant,
    date_paiement,
    est_supprime
from source
where est_supprime = false
