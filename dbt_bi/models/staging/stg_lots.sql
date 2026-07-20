with source as (
    select * from {{ source('dams_prod', 'core_lotentrepot') }}
)

select
    id as lot_id,
    produit_id,
    fournisseur_id,
    quantite_initiale::numeric(10, 2) as quantite_initiale,
    quantite_restante::numeric(10, 2) as quantite_restante,
    prix_achat_unitaire::numeric(10, 2) as prix_achat_unitaire,
    date_reception::date as date_reception
from source
