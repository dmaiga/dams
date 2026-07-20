with source as (
    select * from {{ source('dams_prod', 'core_salaire') }}
)

select
    id as salaire_id,
    agent_id,
    date_debut,
    date_fin,
    salaire_base::numeric(10, 2) as salaire_base,
    -- pour un superviseur, contient en réalité le bonus (pas la dotation de fonction,
    -- jamais appliquée en pratique — voir chef_projet/RISQUES.md R14)
    incentive::numeric(10, 2) as incentive,
    salaire_total::numeric(10, 2) as salaire_total,
    valide
from source
