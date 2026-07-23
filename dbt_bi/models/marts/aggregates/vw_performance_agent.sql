-- Dashboard "Performance Agent & Équipes" (KPI-301 à KPI-306). Grain = agent x mois (dbt-3,
-- 23/07/2026) : un agent actif sans AUCUNE vente sur un mois donné doit rester visible avec
-- kg_par_jour=0 et statut 'sous_objectif' — c'est précisément le cas à signaler (KPI-402) —
-- donc contrairement à vw_rentabilite_produit/vw_marge_fournisseur, la base n'est pas les
-- ventes mais un produit cartésien agents actifs x mois_actifs (mois_actifs = mois distincts
-- où l'entreprise a eu au moins une vente, pour ne pas générer de mois vides/futurs).
-- agents_cibles restreint à est_actif=true (23/07/2026, dbt-5) : un agent désactivé ne doit
-- plus apparaître du tout sur ce dashboard (ni dans le tableau agents, ni dans le calcul de
-- nb_agents_actifs de vw_performance_superviseur) — décision produit, quitte à perdre
-- l'historique de performance d'un agent parti (à distinguer de la paie, cf.
-- paie/services/agent_eligibilite.py, qui doit au contraire couvrir les agents partis pour ne
-- pas sous-évaluer un mois déjà travaillé).
-- kg_par_jour (23/07/2026, dbt-6) : objectif recalculé sur le mois, pas sur une moyenne des
-- seuls jours vendus — le dashboard étant maintenant une représentation mensuelle, diviser par
-- jours_actifs masquait un agent qui n'a travaillé que quelques jours dans le mois (rate élevé
-- sur peu de jours = statut 'atteint' à tort). Dénominateur = jours ouvrés RÉELS du mois filtré
-- (lundi-samedi, dimanche exclu — convention déjà en place, cf. utils/calendrier.py), pas une
-- approximation fixe 4 semaines x 6 jours = 24, pour rester exact même sur un mois de 28/30/31
-- jours ou un mois partiel. jours_actifs (jours avec au moins 1 vente) est conservé à titre
-- informatif mais n'entre plus dans le calcul du statut. Seuils : bi/08_Dashboard_Catalog.md
-- (Dashboard 4). Restreint aux types d'agents réellement soumis à cet objectif terrain/vente
-- directe (exclut direction/rot/entrepot/stagiaire/gestionnaire_stock).
-- superviseur_id/nom = hiérarchie actuelle (comme vw_performance_superviseur.cout_equipe),
-- exposés pour permettre le filtre par superviseur côté Django.
with mois_actifs as (
    select distinct date_trunc('month', date_vente)::date as mois
    from {{ ref('fct_ventes') }}
),

jours_ouvres_mensuel as (
    select
        ma.mois,
        count(*) filter (where extract(isodow from jour) != 7) as jours_ouvres
    from mois_actifs ma
    cross join lateral generate_series(
        ma.mois, (ma.mois + interval '1 month - 1 day')::date, interval '1 day'
    ) as jour
    group by ma.mois
),

agents_cibles as (
    select * from {{ ref('dim_agent') }}
    where type_agent in ('terrain', 'agent_gros', 'agent_polivalent') and est_actif
),

agent_mois as (
    select a.agent_id, m.mois
    from agents_cibles a
    cross join mois_actifs m
),

ventes_agent as (
    select
        agent_id,
        date_trunc('month', date_vente)::date as mois,
        sum(total_vente - total_cout_achat) as marge,
        sum(quantite_en_kg) as kg_vendus,
        count(distinct date_vente) as jours_actifs
    from {{ ref('fct_ventes') }}
    group by agent_id, date_trunc('month', date_vente)::date
),

incentive_agent as (
    select
        agent_id,
        date_trunc('month', date_debut)::date as mois,
        sum(incentive) as incentive_totale
    from {{ ref('fct_salaires') }}
    group by agent_id, date_trunc('month', date_debut)::date
)

select
    row_number() over (order by am.agent_id, am.mois) as agent_mois_id,
    am.agent_id,
    a.nom_complet,
    a.type_agent,
    a.superviseur_id,
    sup.nom_complet as superviseur_nom,
    am.mois,
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
    coalesce(va.marge, 0) as marge,
    coalesce(ia.incentive_totale, 0) as incentive,
    coalesce(va.marge, 0) - coalesce(ia.incentive_totale, 0) as rentabilite_agent,
    case
        when coalesce(va.marge, 0) = 0 then null
        else round(100.0 * coalesce(ia.incentive_totale, 0) / va.marge, 2)
    end as ratio_incentive_marge_pct
from agent_mois am
join agents_cibles a on a.agent_id = am.agent_id
left join {{ ref('dim_agent') }} sup on sup.agent_id = a.superviseur_id
left join ventes_agent va on va.agent_id = am.agent_id and va.mois = am.mois
left join incentive_agent ia on ia.agent_id = am.agent_id and ia.mois = am.mois
left join jours_ouvres_mensuel jo on jo.mois = am.mois
order by am.mois, kg_par_jour desc nulls last
