with source as (
    select * from {{ source('dams_prod', 'core_fournisseur') }}
)

select
    id as fournisseur_id,
    nom
from source
