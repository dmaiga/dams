-- superviseur_id ici = hiérarchie ACTUELLE (core_agent.superviseur_id), à distinguer du
-- superviseur_id de fct_ventes qui reflète la hiérarchie au moment de la distribution du lot.
with salaires as (
    select * from {{ ref('stg_salaires') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
)

select
    s.salaire_id,
    s.agent_id,
    a.superviseur_id,
    s.date_debut,
    s.date_fin,
    s.salaire_base,
    s.incentive,
    s.salaire_total,
    s.valide
from salaires s
left join agents a on s.agent_id = a.agent_id
