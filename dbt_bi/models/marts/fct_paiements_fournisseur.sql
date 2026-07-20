select
    paiement_id,
    fournisseur_id,
    lot_id,
    agent_id,
    montant,
    date_paiement
from {{ ref('stg_paiements_fournisseur') }}
