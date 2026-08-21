with source as (
    select * from {{ source('dams_prod', 'core_reglesalaire') }}
)

select
    id as regle_salaire_id,
    type_agent,
    dotation_fonction::numeric(10, 2) as dotation_fonction,
    incentive_par_kg::numeric(10, 2) as incentive_par_kg,
    incentive_par_carton::numeric(10, 2) as incentive_par_carton,
    actif
from source
where actif
