-- Dashboard "Agents", volet hebdomadaire (24/07/2026, S-702) : miroir de
-- vw_performance_agent.sql mais grain = agent x semaine ISO (lundi-dimanche). Postgres
-- date_trunc('week', x) tronque déjà au lundi de la semaine ISO, pas de calcul manuel requis.
-- Mêmes règles que le grain mensuel : agents_cibles restreint à
-- type_agent in ('terrain','agent_gros','agent_polivalent') and est_actif (agent désactivé
-- absent du dashboard), jours_ouvres = lundi-samedi réels de la semaine (jamais 6 fixe, une
-- semaine en bord de période de données peut être partielle).
-- Pas d'incentive/ratio ici : fct_salaires est à grain mensuel (date_debut = début de mois de
-- paie), sommer par semaine n'aurait pas de sens — voir bi/views.py dashboard_agents pour la
-- façon dont la "rentabilité" hebdo est assimilée à la marge brute (sans retrait incentive).
with semaines_actives as (
    select distinct date_trunc('week', date_vente)::date as semaine
    from {{ ref('fct_ventes') }}
),

jours_ouvres_hebdo as (
    select
        sa.semaine,
        count(*) filter (where extract(isodow from jour) != 7) as jours_ouvres
    from semaines_actives sa
    cross join lateral generate_series(
        sa.semaine, (sa.semaine + interval '6 days')::date, interval '1 day'
    ) as jour
    group by sa.semaine
),

agents_cibles as (
    select * from {{ ref('dim_agent') }}
    where type_agent in ('terrain', 'agent_gros', 'agent_polivalent') and est_actif
),

agent_semaine as (
    select a.agent_id, s.semaine
    from agents_cibles a
    cross join semaines_actives s
),

ventes_agent as (
    select
        agent_id,
        date_trunc('week', date_vente)::date as semaine,
        sum(total_vente - total_cout_achat) as marge,
        sum(quantite_en_kg) as kg_vendus,
        count(distinct date_vente) as jours_actifs
    from {{ ref('fct_ventes') }}
    group by agent_id, date_trunc('week', date_vente)::date
)

select
    row_number() over (order by ase.agent_id, ase.semaine) as agent_semaine_id,
    ase.agent_id,
    a.nom_complet,
    a.type_agent,
    a.superviseur_id,
    sup.nom_complet as superviseur_nom,
    ase.semaine,
    coalesce(va.kg_vendus, 0) as kg_vendus,
    coalesce(va.jours_actifs, 0) as jours_actifs,
    jo.jours_ouvres,
    case
        when coalesce(jo.jours_ouvres, 0) = 0 then 0
        else round(coalesce(va.kg_vendus, 0) / jo.jours_ouvres, 2)
    end as kg_par_jour,
    case
        when coalesce(jo.jours_ouvres, 0) = 0 then 'sous_objectif'
        when coalesce(va.kg_vendus, 0) / jo.jours_ouvres >= 50 then 'atteint'
        when coalesce(va.kg_vendus, 0) / jo.jours_ouvres >= 40 then 'proche'
        else 'sous_objectif'
    end as statut_objectif_50kg,
    coalesce(va.marge, 0) as marge
from agent_semaine ase
join agents_cibles a on a.agent_id = ase.agent_id
left join {{ ref('dim_agent') }} sup on sup.agent_id = a.superviseur_id
left join ventes_agent va on va.agent_id = ase.agent_id and va.semaine = ase.semaine
left join jours_ouvres_hebdo jo on jo.semaine = ase.semaine
order by ase.semaine, kg_par_jour desc nulls last
