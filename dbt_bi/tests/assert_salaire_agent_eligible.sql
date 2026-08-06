-- Réalignement 06/08/2026 : remplace assert_salaire_apres_date_debut_fonction
-- (dbt-1, 2026-07-20), qui vérifiait l'ancien "pivot du prorata paie" —
-- philosophie d'éligibilité par dates de contrat, abandonnée côté application
-- le 05/08/2026 (paie/services/agent_eligibilite.py::agents_eligibles_periode,
-- voir paie/APP_PAIE.md §1.ter). Garder ce test sous son ancienne forme
-- ferait échouer dbt sur des données désormais légitimes (agent est_actif=True
-- avec une ligne de salaire antérieure à date_debut_fonction).
--
-- Vérifie à la place que fct_salaires ne retient aucune ligne pour un agent
-- inéligible selon la règle actuelle : est_actif=True (toujours éligible,
-- quelles que soient ses dates de contrat) OU agent désactivé dont la fenêtre
-- d'emploi connue (date_debut_fonction -> date_fin_contrat) chevauche la
-- période de la ligne de salaire (rattrapage historique). Comme fct_salaires
-- applique déjà ce même filtre dans son WHERE, ce test ne doit jamais
-- retourner de ligne tant que le modèle reste aligné avec la règle
-- applicative — garde-fou anti-régression, pas une contrainte nouvelle.
select
    s.salaire_id,
    s.agent_id,
    s.date_debut,
    s.date_fin,
    a.est_actif,
    a.date_debut_fonction,
    a.date_fin_contrat
from {{ ref('fct_salaires') }} s
left join {{ ref('stg_agents') }} a on s.agent_id = a.agent_id
where not (
    coalesce(a.est_actif, false)
    or (
        (a.date_debut_fonction is not null or a.date_fin_contrat is not null)
        and (a.date_debut_fonction is null or a.date_debut_fonction <= s.date_fin)
        and (a.date_fin_contrat is null or a.date_fin_contrat >= s.date_debut)
    )
)
