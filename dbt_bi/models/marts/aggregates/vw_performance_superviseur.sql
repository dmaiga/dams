-- Dashboard 3, partie 1 (Performance Superviseur). Grain = superviseur (KPI-201 à KPI-206).
-- Un superviseur = dim_agent filtrée type_agent='entrepot' (pas de dim_superviseur séparée,
-- voir sprints/SPRINT_2_Modeles_Dashboards.md). ca/marge_brute via fct_ventes.superviseur_id
-- (hiérarchie au moment de la vente) ; cout_equipe via fct_salaires.superviseur_id (hiérarchie
-- actuelle) — les deux sources divergent volontairement, voir commentaire fct_salaires.sql.
with ventes_superviseur as (
    select
        superviseur_id,
        sum(total_vente) as ca,
        sum(total_vente - total_cout_achat) as marge_brute
    from {{ ref('fct_ventes') }}
    where superviseur_id is not null
    group by superviseur_id
),

cout_equipe as (
    select
        superviseur_id,
        sum(salaire_total) as cout_equipe
    from {{ ref('fct_salaires') }}
    where superviseur_id is not null
    group by superviseur_id
),

agents_actifs as (
    select
        superviseur_id,
        count(distinct agent_id) as nb_agents_actifs
    from {{ ref('dim_agent') }}
    where superviseur_id is not null and est_actif
    group by superviseur_id
)

select
    sup.agent_id as superviseur_id,
    sup.nom_complet as superviseur_nom,
    coalesce(v.ca, 0) as ca,
    coalesce(v.marge_brute, 0) as marge_brute,
    coalesce(ce.cout_equipe, 0) as cout_equipe,
    coalesce(v.marge_brute, 0) - coalesce(ce.cout_equipe, 0) as rentabilite_nette,
    coalesce(aa.nb_agents_actifs, 0) as nb_agents_actifs,
    case
        when coalesce(aa.nb_agents_actifs, 0) = 0 then null
        else round(coalesce(v.ca, 0) / aa.nb_agents_actifs, 2)
    end as ca_moyen_par_agent
from {{ ref('dim_agent') }} sup
left join ventes_superviseur v on sup.agent_id = v.superviseur_id
left join cout_equipe ce on sup.agent_id = ce.superviseur_id
left join agents_actifs aa on sup.agent_id = aa.superviseur_id
where sup.type_agent = 'entrepot'
order by rentabilite_nette desc nulls last
