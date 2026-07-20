with source as (
    select * from {{ source('dams_prod', 'core_distributionagent') }}
)

select
    id as distribution_id,
    agent_terrain_id,
    superviseur_id,
    type_distribution,
    quantite_totale::numeric(10, 2) as quantite_totale,
    date_distribution::date as date_distribution
from source
