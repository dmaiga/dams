with source as (
    select * from {{ source('dams_prod', 'core_perte') }}
)

select
    id as perte_id,
    lot_id,
    quantite_perdue::numeric(10, 2) as quantite_perdue,
    date_perte::date as date_perte
from source
