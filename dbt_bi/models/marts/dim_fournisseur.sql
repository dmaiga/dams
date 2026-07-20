select
    fournisseur_id,
    nom
from {{ ref('stg_fournisseurs') }}
