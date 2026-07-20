-- dbt-1 (2026-07-20) : aucune ligne de fct_salaires ne doit précéder la date_debut_fonction
-- de l'agent concerné (prorata paie, REFERENCE_TECHNIQUE_BI.md §1.5/§2.10). Test échoue
-- (retourne des lignes) si la correction de fct_salaires.sql est un jour régressée.
select
    s.salaire_id,
    s.agent_id,
    s.date_debut,
    a.date_debut_fonction
from {{ ref('fct_salaires') }} s
left join {{ ref('stg_agents') }} a on s.agent_id = a.agent_id
where a.date_debut_fonction is not null
  and s.date_debut < a.date_debut_fonction
