# Audit — Groupe « Vérificateur général » : points de vigilance

**Date** : 02/11/2026 · **Statut** : à traiter (décision à prendre par mdmaiga)

## Périmètre livré

Groupe Django `Vérificateur général` (migration `core.0133`, helpers dans `core/services/acces.py`).
Menu direction restreint à : Tableau de Bord, Agents, Produits, Suivi des Distributions, Fournisseurs,
Ventes, Analyse Opérationnelle, Surveillance, BI. Rémunération, FINANCE, CHAMPS (DAMS AGRO) et ADMIN
sont masqués (`direction/templates/base_admin.html`). Seuls `mdmaiga` et les superusers gardent le
menu complet, même si le membre du groupe est aussi agent direction.

## Alertes

1. **Menu masqué ≠ accès bloqué.** Seuls sont réellement refusés (403) : `/direction/paie/`
   (`SalaireLectureView`) et `/champs/` (`core/middleware.py`, `PREFIXES_FERMES_VERIFICATEUR`). Les
   écrans FINANCE (versements, dépenses, factures fournisseurs, solde superviseurs), les autres
   pages de paie (génération, validation, exports) et ADMIN (réaffectation, corrections) restent
   atteignables par URL directe. Plusieurs sont accessibles à tout utilisateur connecté
   (`@login_required` seul) — lacune antérieure à ce groupe, non propre à lui.
   *Piste* : ajouter leurs préfixes à `PREFIXES_FERMES_VERIFICATEUR`.
2. **Données de salaire sur d'autres écrans.** La fiche détail d'un agent (`agent_detail`) et les
   pages BI (fiche agent, `incentive_projetee`) peuvent afficher des informations de rémunération,
   ouvertes au groupe. À arbitrer.
3. **Lecture seule non garantie.** Les écrans ouverts au groupe ont été contrôlés pour l'accès, pas
   pour l'absence de boutons d'action (POST) : à vérifier page par page.
4. **BI non testée avec données.** Les vues `bi_.vw_*` (dbt) n'existent pas en base de test : le test
   ne couvre que la garde d'accès (`_est_utilisateur_autorise`).
5. **Membre à double rôle.** `modibo.sidibe1` est agent direction et membre du groupe : il perd
   FINANCE/CHAMPS/Rémunération. Le retirer du groupe s'il en a besoin.

## Fichiers touchés

`core/services/acces.py`, `core/context_processors.py`, `core/middleware.py`, `core/views.py`
(redirection à la connexion), `core/migrations/0133_groupe_verificateur_general.py`,
`direction/views.py`, `bi/views.py`, `surveillance/mixins.py`, `paie/views.py`,
`direction/test_verificateur_general.py`.
