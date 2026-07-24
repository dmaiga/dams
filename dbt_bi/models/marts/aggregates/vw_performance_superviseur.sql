-- Dashboard "Performance Agent & Équipes", volet équipes/superviseurs (KPI-201 à KPI-206).
-- Grain = superviseur x mois (23/07/2026, dbt-4) : la version all-time précédente rendait le
-- graphique/tableau superviseur non filtrable par mois alors que le reste de la page l'est,
-- ce qui donnait l'impression trompeuse que les chiffres suivaient le mois sélectionné —
-- même pattern que vw_performance_agent (cross join superviseurs actifs x mois_actifs, pour
-- qu'un superviseur sans vente sur un mois donné reste visible avec des valeurs à 0 plutôt que
-- de disparaître). nb_agents_actifs reste un snapshot de la composition d'équipe ACTUELLE (pas
-- d'historique de rattachement agent->superviseur disponible, limite identique à
-- vw_analyse_stock) — à ne pas lire comme "agents actifs ce mois-là".
-- Un superviseur = dim_agent filtrée type_agent='entrepot' (pas de dim_superviseur séparée,
-- voir sprints/SPRINT_2_Modeles_Dashboards.md). ca/marge_brute via fct_ventes.superviseur_id
-- (hiérarchie au moment de la vente) ; cout_equipe via fct_salaires.superviseur_id (hiérarchie
-- actuelle) — les deux sources divergent volontairement, voir commentaire fct_salaires.sql.
with mois_actifs as (
    select distinct date_trunc('month', date_vente)::date as mois
    from {{ ref('fct_ventes') }}
),

superviseurs_cibles as (
    select * from {{ ref('dim_agent') }}
    where type_agent = 'entrepot'
),

superviseur_mois as (
    select s.agent_id as superviseur_id, m.mois
    from superviseurs_cibles s
    cross join mois_actifs m
),

ventes_superviseur as (
    select
        superviseur_id,
        date_trunc('month', date_vente)::date as mois,
        sum(total_vente) as ca,
        sum(total_vente - total_cout_achat) as marge_brute,
        sum(quantite_en_kg) as kg_vendus
    from {{ ref('fct_ventes') }}
    where superviseur_id is not null
    group by superviseur_id, date_trunc('month', date_vente)::date
),

cout_equipe as (
    select
        superviseur_id,
        date_trunc('month', date_debut)::date as mois,
        sum(salaire_total) as cout_equipe
    from {{ ref('fct_salaires') }}
    where superviseur_id is not null
    group by superviseur_id, date_trunc('month', date_debut)::date
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
    row_number() over (order by sm.superviseur_id, sm.mois) as superviseur_mois_id,
    sm.superviseur_id,
    sup.nom_complet as superviseur_nom,
    sm.mois,
    coalesce(v.ca, 0) as ca,
    coalesce(v.marge_brute, 0) as marge_brute,
    coalesce(v.kg_vendus, 0) as kg_vendus,
    coalesce(ce.cout_equipe, 0) as cout_equipe,
    coalesce(v.marge_brute, 0) - coalesce(ce.cout_equipe, 0) as rentabilite_nette,
    coalesce(aa.nb_agents_actifs, 0) as nb_agents_actifs,
    case
        when coalesce(aa.nb_agents_actifs, 0) = 0 then null
        else round(coalesce(v.ca, 0) / aa.nb_agents_actifs, 2)
    end as ca_moyen_par_agent
from superviseur_mois sm
join superviseurs_cibles sup on sup.agent_id = sm.superviseur_id
left join ventes_superviseur v on v.superviseur_id = sm.superviseur_id and v.mois = sm.mois
left join cout_equipe ce on ce.superviseur_id = sm.superviseur_id and ce.mois = sm.mois
left join agents_actifs aa on aa.superviseur_id = sm.superviseur_id
-- Priorité produit (24/07/2026) : le kilo vendu par l'équipe prime sur la rentabilité nette
-- pour la lecture de la performance superviseur, cf. chef_projet/BILAN_LIVRAISON_VS_VISION.md.
order by sm.mois, kg_vendus desc nulls last
