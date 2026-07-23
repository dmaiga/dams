-- superviseur_id ici = hiérarchie ACTUELLE (core_agent.superviseur_id), à distinguer du
-- superviseur_id de fct_ventes qui reflète la hiérarchie au moment de la distribution du lot.
-- Correction (dbt-1, 2026-07-20) : le régime de paie a évolué (prorata au départ, puis
-- fixe+incentive introduits à des mois précis) — un agent entré en mars ne doit générer
-- aucun coût salarial en janvier/février. On exclut donc toute ligne de salaire dont
-- date_debut précède agent.date_debut_fonction (pivot du prorata paie, voir
-- architecte/REFERENCE_TECHNIQUE_BI.md §1.5/§2.10). Si date_debut_fonction est NULL
-- (non renseignée), la ligne est conservée : pas de proratisation possible faute de donnée,
-- cohérent avec le comportement du calculateur de paie actuel. Cascade automatique (ref())
-- dans vw_rentabilite_globale (KPI-005/006/009) et vw_performance_superviseur (KPI-203/204).
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
    a.type_agent,
    s.date_debut,
    s.date_fin,
    s.salaire_base,
    s.incentive,
    s.salaire_total,
    s.valide
from salaires s
left join agents a on s.agent_id = a.agent_id
where a.date_debut_fonction is null or s.date_debut >= a.date_debut_fonction
