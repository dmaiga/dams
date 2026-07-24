-- Dashboard "Agents", volet équipes hebdomadaire (24/07/2026, S-702) : miroir de
-- vw_performance_superviseur.sql mais grain = superviseur x semaine ISO (lundi-dimanche, cf.
-- vw_performance_agent_semaine.sql pour le détail de date_trunc('week', ...)). cout_equipe /
-- rentabilite_nette / ca_moyen_par_agent ne sont pas repris ici : fct_salaires est mensuel et
-- ces colonnes ne sont de toute façon plus affichées sur le dashboard (priorité kilo vendu,
-- cf. chef_projet/BILAN_LIVRAISON_VS_VISION.md).
with semaines_actives as (
    select distinct date_trunc('week', date_vente)::date as semaine
    from {{ ref('fct_ventes') }}
),

superviseurs_cibles as (
    select * from {{ ref('dim_agent') }}
    where type_agent = 'entrepot'
),

superviseur_semaine as (
    select s.agent_id as superviseur_id, sa.semaine
    from superviseurs_cibles s
    cross join semaines_actives sa
),

ventes_superviseur as (
    select
        superviseur_id,
        date_trunc('week', date_vente)::date as semaine,
        sum(total_vente) as ca,
        sum(total_vente - total_cout_achat) as marge_brute,
        sum(quantite_en_kg) as kg_vendus
    from {{ ref('fct_ventes') }}
    where superviseur_id is not null
    group by superviseur_id, date_trunc('week', date_vente)::date
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
    row_number() over (order by ss.superviseur_id, ss.semaine) as superviseur_semaine_id,
    ss.superviseur_id,
    sup.nom_complet as superviseur_nom,
    ss.semaine,
    coalesce(v.ca, 0) as ca,
    coalesce(v.marge_brute, 0) as marge_brute,
    coalesce(v.kg_vendus, 0) as kg_vendus,
    coalesce(aa.nb_agents_actifs, 0) as nb_agents_actifs
from superviseur_semaine ss
join superviseurs_cibles sup on sup.agent_id = ss.superviseur_id
left join ventes_superviseur v on v.superviseur_id = ss.superviseur_id and v.semaine = ss.semaine
left join agents_actifs aa on aa.superviseur_id = ss.superviseur_id
order by ss.semaine, kg_vendus desc nulls last
