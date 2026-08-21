-- Réécrit le 21/08/2026 (dbt-8) : indépendant de core_salaire. L'app ne génère plus de
-- Salaire de façon régulière (lecture "en direct" via CalculatorSalaire.calcul_salaire_mamy
-- dans paie/services/salaire_liste_service.py et bi/views.py::dashboard_agent_detail, cf.
-- paie/APP_PAIE.md) et l'utilisateur n'a pas de cron sur son serveur mutualisé pour maintenir
-- core_salaire à jour : ce modèle recalcule donc intégralement salaire_base/incentive/
-- salaire_total à chaque `dbt run`, à partir de fct_ventes/stg_pertes/stg_produits/
-- stg_regle_salaire — jamais lu depuis core_salaire. Réplique les trois calculateurs de
-- paie/services/salaire_calculator.py (calcul_salaire_mamy / calcul_salaire_gros /
-- calcul_salaire_superviseur) ; toute évolution de ces règles doit être répercutée ici aussi
-- (duplication OLTP/BI assumée, cf. paie/APP_PAIE.md).
-- Grain = agent x mois, mois = mois_actifs (mois avec >= 1 vente société, comme
-- vw_performance_agent.sql). Pas de proratisation jours travaillés (déjà le cas avant ce
-- correctif, dbt-7 2026-08-03) : le fixe théorique mamy est toujours utilisé au grain mensuel.
-- Éligibilité = paie/services/agent_eligibilite.py::agents_eligibles_periode, RÉPLIQUÉE À
-- L'IDENTIQUE, SANS borne supplémentaire sur date_debut_fonction (tentative initiale du
-- 21/08/2026, retirée le même jour après vérification empirique contre l'app live : un agent
-- actif embauché après le mois n'obtient PAS un fixe fantôme côté Django, mais un fixe
-- proratisé à 0 via get_jours_travailles_mois — cf. mamy_calcul plus bas, qui réplique cette
-- proratisation. Exclure la ligne au lieu de la neutraliser désynchronisait le nombre d'agents
-- affiché ici de celui de l'app (42 vs 29 constaté sur juin 2026).
-- superviseur_id = hiérarchie ACTUELLE (core_agent.superviseur_id), à distinguer du
-- superviseur_id de fct_ventes qui reflète la hiérarchie au moment de la distribution du lot.
-- Superviseur, salaire_base/incentive vs salaire_total (R14, cf. paie/APP_PAIE.md et
-- stg_salaires.sql) : salaire_base ici = Agent.salaire_base_personnel uniquement (comme
-- CalculatorSalaire.get_salaire_base — RegleSalaire n'a pas de champ salaire_base/montant_base/
-- salaire_fixe, seul le override personnel compte), incentive = bonus. dotation_fonction est
-- injectée dans salaire_total mais PAS dans salaire_base+incentive, exactement comme côté
-- Django (bug connu, jamais appliquée en pratique) — ne pas "corriger" cet écart ici, le test
-- salaire_total = salaire_base + incentive de _marts.yml l'accepte déjà en warn pour ce cas.
with mois_actifs as (
    select distinct date_trunc('month', date_vente)::date as mois
    from {{ ref('fct_ventes') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
),

ventes as (
    select * from {{ ref('fct_ventes') }}
),

pertes as (
    select * from {{ ref('stg_pertes') }}
),

produits as (
    select * from {{ ref('stg_produits') }}
),

regles as (
    select * from {{ ref('stg_regle_salaire') }}
),

agent_mois as (
    select
        a.agent_id,
        a.type_agent,
        a.superviseur_id,
        a.salaire_base_personnel,
        a.date_debut_fonction,
        a.date_creation,
        m.mois,
        (m.mois + interval '1 month - 1 day')::date as date_fin_mois
    from agents a
    cross join mois_actifs m
    where a.type_agent in ('terrain', 'agent_gros', 'entrepot')
      and (
        a.est_actif
        or (
            (a.date_debut_fonction is not null or a.date_fin_contrat is not null)
            and (a.date_debut_fonction is null or a.date_debut_fonction <= (m.mois + interval '1 month - 1 day')::date)
            and (a.date_fin_contrat is null or a.date_fin_contrat >= m.mois)
        )
      )
),

-- ===== MAMIES (terrain) =====
mamy_detail as (
    select
        v.agent_id,
        date_trunc('month', v.date_vente)::date as mois,
        v.quantite,
        v.quantite_en_kg,
        p.taux_incentive as produit_taux_incentive,
        coalesce(pe.kilo_perdu_incentive, 0) as kilo_perdu_incentive
    from ventes v
    left join produits p on p.produit_id = v.produit_id
    left join pertes pe on pe.vente_id = v.vente_id
),

mamy_agrege as (
    select
        agent_id,
        mois,
        sum(quantite_en_kg) as kilo_total,
        sum(kilo_perdu_incentive) as kilo_perdu,
        sum(case when produit_taux_incentive is null then quantite_en_kg else 0 end) as kilo_au_kg,
        sum(case when produit_taux_incentive is null then kilo_perdu_incentive else 0 end) as kilo_perdu_au_kg,
        sum(case when produit_taux_incentive is not null then quantite * produit_taux_incentive else 0 end) as incentive_taux_dedie
    from mamy_detail
    group by agent_id, mois
),

-- Proratisation (paie/services/salaire_calculator.py::get_jours_travailles_mois +
-- calcul_salaire_mamy) : réplique exactement la règle Django, y compris son cas de bord —
-- un agent SANS date_debut_fonction n'est jamais proratisé (fixe théorique plein, même si
-- date_creation est récente) ; un agent AVEC date_debut_fonction postérieure au mois obtient
-- jours_travailles=0 -> fixe proratisé à 0 (pas exclu de la grille, cf. commentaire agent_mois
-- plus haut).
mamy_calcul as (
    select
        am.agent_id,
        am.mois,
        case when (coalesce(ma.kilo_total, 0) - coalesce(ma.kilo_perdu, 0)) >= 750 then 20000 else 10000 end as salaire_base_theorique,
        case
            when am.date_debut_fonction is not null and jt.jours_travailles < jt.total_jours_mois
                then round(
                    (case when (coalesce(ma.kilo_total, 0) - coalesce(ma.kilo_perdu, 0)) >= 750 then 20000 else 10000 end)
                    * jt.jours_travailles::numeric / jt.total_jours_mois
                )
            else (case when (coalesce(ma.kilo_total, 0) - coalesce(ma.kilo_perdu, 0)) >= 750 then 20000 else 10000 end)
        end as salaire_base,
        (coalesce(ma.kilo_au_kg, 0) - coalesce(ma.kilo_perdu_au_kg, 0)) * coalesce(r.incentive_par_kg, 0)
            + coalesce(ma.incentive_taux_dedie, 0) as incentive,
        coalesce(ma.kilo_total, 0) as kilo_total
    from agent_mois am
    left join mamy_agrege ma on ma.agent_id = am.agent_id and ma.mois = am.mois
    cross join lateral (select incentive_par_kg from regles where type_agent = 'terrain' limit 1) r
    cross join lateral (
        select
            (am.date_fin_mois - am.mois) + 1 as total_jours_mois,
            greatest(0, (
                least(am.date_fin_mois, current_date)
                - greatest(am.mois, coalesce(am.date_debut_fonction, am.date_creation))
            ) + 1) as jours_travailles
    ) jt
    where am.type_agent = 'terrain'
),

-- ===== AGENTS GROS =====
gros_agrege as (
    select
        agent_id,
        date_trunc('month', date_vente)::date as mois,
        sum(quantite) as cartons
    from ventes
    group by agent_id, date_trunc('month', date_vente)::date
),

gros_calcul as (
    select
        am.agent_id,
        am.mois,
        0::numeric(10, 2) as salaire_base,
        case
            when coalesce(g.cartons, 0) < 150 then coalesce(g.cartons, 0) * coalesce(r.incentive_par_carton, 0)
            when coalesce(g.cartons, 0) < 200 then 50000
            else 90000
        end as incentive
    from agent_mois am
    left join gros_agrege g on g.agent_id = am.agent_id and g.mois = am.mois
    cross join lateral (select incentive_par_carton from regles where type_agent = 'agent_gros' limit 1) r
    where am.type_agent = 'agent_gros'
),

-- ===== SUPERVISEURS =====
-- kilo_total_mamies = kilo BRUT (pas net des pertes) des mamies actives sous ce superviseur,
-- décision explicite (paie/APP_PAIE.md §1.quater, "hors périmètre" pour le bonus superviseur).
kilo_mamies_par_superviseur as (
    select
        a.superviseur_id,
        mc.mois,
        sum(mc.kilo_total) as kilo_total_mamies
    from mamy_calcul mc
    join agents a on a.agent_id = mc.agent_id
    where a.type_agent = 'terrain' and a.est_actif
    group by a.superviseur_id, mc.mois
),

superviseur_calcul as (
    select
        am.agent_id,
        am.mois,
        coalesce(am.salaire_base_personnel, 0) as salaire_base,
        coalesce(km.kilo_total_mamies, 0) as kilo_total_mamies,
        coalesce(r.dotation_fonction, 0) as dotation,
        case
            when coalesce(km.kilo_total_mamies, 0) < 18000 then 0
            when coalesce(km.kilo_total_mamies, 0) < 27000 then 0.04
            when coalesce(km.kilo_total_mamies, 0) < 37000 then 0.06
            else 0.08
        end as taux_bonus
    from agent_mois am
    left join kilo_mamies_par_superviseur km on km.superviseur_id = am.agent_id and km.mois = am.mois
    cross join lateral (select dotation_fonction from regles where type_agent = 'superviseur' limit 1) r
    where am.type_agent = 'entrepot'
),

assemble as (
    select
        am.agent_id,
        am.type_agent,
        am.superviseur_id,
        am.mois as date_debut,
        am.date_fin_mois as date_fin,
        case
            when am.type_agent = 'terrain' then mc.salaire_base
            when am.type_agent = 'agent_gros' then gc.salaire_base
            when am.type_agent = 'entrepot' then sc.salaire_base
        end as salaire_base,
        case
            when am.type_agent = 'terrain' then mc.incentive
            when am.type_agent = 'agent_gros' then gc.incentive
            when am.type_agent = 'entrepot' then sc.kilo_total_mamies * sc.taux_bonus
        end as incentive,
        case
            when am.type_agent = 'terrain' then mc.salaire_base + mc.incentive
            when am.type_agent = 'agent_gros' then gc.salaire_base + gc.incentive
            when am.type_agent = 'entrepot' then sc.salaire_base + sc.dotation + sc.kilo_total_mamies * sc.taux_bonus
        end as salaire_total
    from agent_mois am
    left join mamy_calcul mc on am.type_agent = 'terrain' and mc.agent_id = am.agent_id and mc.mois = am.mois
    left join gros_calcul gc on am.type_agent = 'agent_gros' and gc.agent_id = am.agent_id and gc.mois = am.mois
    left join superviseur_calcul sc on am.type_agent = 'entrepot' and sc.agent_id = am.agent_id and sc.mois = am.mois
)

select
    row_number() over (order by agent_id, date_debut) as salaire_id,
    agent_id,
    superviseur_id,
    type_agent,
    date_debut,
    date_fin,
    salaire_base::numeric(10, 2) as salaire_base,
    incentive::numeric(10, 2) as incentive,
    salaire_total::numeric(10, 2) as salaire_total,
    -- Pas de notion de "validé" : ce modèle est un recalcul live à chaque run, distinct du
    -- verrouillage optionnel côté Django (Salaire.valide, cf. paie/APP_PAIE.md).
    false as valide
from assemble
