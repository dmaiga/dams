with agents as (
    select * from {{ ref('stg_agents') }}
),

utilisateurs as (
    select * from {{ ref('stg_utilisateurs') }}
)

select
    a.agent_id,
    trim(coalesce(u.first_name, '') || ' ' || coalesce(u.last_name, '')) as nom_complet,
    a.type_agent,
    a.superviseur_id,
    a.est_actif,
    a.type_contrat,
    a.date_debut_fonction,
    a.date_fin_contrat
from agents a
left join utilisateurs u on a.user_id = u.user_id
