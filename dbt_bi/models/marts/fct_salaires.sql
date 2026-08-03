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
-- Nouveau régime terrain (dbt-7, 2026-08-03) : à partir du 2026-05-01, le fixe agent terrain
-- n'est plus statique — il dépend du kg réalisé sur la période de la ligne de salaire
-- (>= 750 kg -> 20000, sinon 10000), cf. paie/services/salaire_calculator.py::calcul_salaire_mamy.
-- Recalculé ici plutôt que lu depuis salaire_base stocké : garantit un KPI cohérent avec la
-- règle même si une ligne a été générée avant le déploiement du nouveau calculateur.
-- Zéro avant mai (dbt-7, 2026-08-03, décision produit) : toute ligne salaire dont date_debut <
-- 2026-05-01 est ramenée à 0 (salaire_base, incentive, salaire_total), tous types d'agent
-- confondus. Les montants stockés avant cette date sont jugés caducs par la direction (régimes
-- de paie qui ont changé plusieurs fois sans être fiables rétroactivement) — le KPI de coût
-- salarial ne doit refléter que la période à partir de laquelle le calcul est jugé fiable.
-- Conséquence assumée : cout_salaires dans vw_rentabilite_globale et cout_equipe dans
-- vw_performance_superviseur chutent à 0 pour toute période antérieure à mai 2026.
with salaires as (
    select * from {{ ref('stg_salaires') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
),

ventes as (
    select * from {{ ref('fct_ventes') }}
),

kg_par_salaire as (
    select
        s.salaire_id,
        coalesce(sum(v.quantite_en_kg), 0) as kg_realise
    from salaires s
    left join ventes v
        on v.agent_id = s.agent_id
        and v.date_vente between s.date_debut and s.date_fin
    group by s.salaire_id
),

fixe_recalcule as (
    select
        s.salaire_id,
        (a.type_agent = 'terrain' and s.date_debut >= date '2026-05-01') as regime_kg_applicable,
        case
            when a.type_agent = 'terrain' and s.date_debut >= date '2026-05-01'
                then case when k.kg_realise >= 750 then 20000 else 10000 end
            else s.salaire_base
        end as salaire_base
    from salaires s
    left join agents a on s.agent_id = a.agent_id
    left join kg_par_salaire k on k.salaire_id = s.salaire_id
)

select
    s.salaire_id,
    s.agent_id,
    a.superviseur_id,
    a.type_agent,
    s.date_debut,
    s.date_fin,
    case when s.date_debut < date '2026-05-01' then 0 else f.salaire_base end as salaire_base,
    case when s.date_debut < date '2026-05-01' then 0 else s.incentive end as incentive,
    case
        when s.date_debut < date '2026-05-01' then 0
        -- salaire_total recalculé seulement quand le régime kg s'applique (terrain) ;
        -- sinon le montant stocké reste la source de vérité (cf. R14, superviseur non concerné ici).
        when f.regime_kg_applicable then f.salaire_base + s.incentive
        else s.salaire_total
    end as salaire_total,
    s.valide
from salaires s
left join agents a on s.agent_id = a.agent_id
left join fixe_recalcule f on f.salaire_id = s.salaire_id
where a.date_debut_fonction is null or s.date_debut >= a.date_debut_fonction
