# Sprint 3 — Dashboards finaux + validation métier (19–25 juillet 2026)

> ℹ️ **Avance anticipée (17/07/2026, pendant que le build Docker/WSL2 du Sprint 2 finissait).** Le SQL sous-jacent de 4 des 6 stories du backlog est déjà couvert par les vues `vw_*` livrées en avance de phase pour le Sprint 2 (`dbt/models/marts/aggregates/`, voir [SPRINT_2_Modeles_Dashboards.md](SPRINT_2_Modeles_Dashboards.md)) :
> - **S-102** (rentabilité nette) → `vw_rentabilite_globale.rentabilite_nette`
> - **S-302** (coût équipe réel superviseur) → `vw_performance_superviseur.cout_equipe`
> - **S-402** (agents déficitaires) → filtre `vw_performance_agent.rentabilite_agent < 0`, pas de nouvelle vue nécessaire
> - **S-502** (rotation de stock) → `vw_rentabilite_produit.rotation_stock` (proxy stock actuel, limite documentée ci-dessous)
>
> **S-103** (courbe mensuelle) et **S-202** (produits vendus à perte) sont aussi couverts par les données existantes (`vw_rentabilite_globale` par mois ; `vw_rentabilite_produit.marge < 0`) mais restent des **visualisations Metabase**, pas du SQL — bloquées comme le reste du sprint sur la disponibilité du conteneur Metabase. Rien de tout ceci ne remplace la session de validation Direction (Jeu 22) ni le sign-off, qui restent le vrai jalon de sortie du sprint.

> ℹ️ **Ajusté après Sprint 1.** `fct_stocks` est un **snapshot courant** (1 ligne par lot), pas un historique quotidien — `KPI-105` (rotation de stock) ne peut pas calculer une vraie valeur de stock moyenne sur la période. S-502 devra utiliser la valeur de stock **actuelle** comme proxy (documenté comme limitation, pas silencieusement approximé) ; un historique quotidien via `dbt snapshot` reste une amélioration Sprint 2+ si jugée nécessaire. Par ailleurs, `KPI-306` (volume agent en kg) a été corrigé dans [bi/07_Dictionnaire_KPI_Technique.md](../bi/07_Dictionnaire_KPI_Technique.md) : utiliser `fct_ventes.quantite_en_kg`, jamais `quantite` brut (mélange kg/cartons selon le produit).

**Objectif** : dashboards polis, tous les KPI visibles, sign-off Direction.
**Jalon Roadmap** : G3 — *Validation Direction*
**Owner sprint** : BI Dev (exécution) / PO (gate)

---

## Backlog du sprint

Voir détail complet dans [owner/02_Backlog.md](../owner/02_Backlog.md).

| # | Story | Priorité |
|---|-------|----------|
| S-102 | KPI Rentabilité nette (marge − salaires − dépenses) | 🔴 MUST |
| S-103 | Courbe d'évolution mensuelle (jan → juin) | 🔴 MUST |
| S-202 | Produits vendus à perte (prix vente < prix achat) | 🔴 MUST |
| S-302 | Coût équipe réel par superviseur (salaires + incentives) | 🔴 MUST |
| S-402 | KPI Agents déficitaires (incentive > marge générée) | 🔴 MUST |
| S-502 | Rotation de stock par produit (CA / stock moyen) | 🔴 MUST |
| — | Affinage : filtres interactifs, couleurs, alertes visuelles 🔴🟡🟢 | 🟡 SHOULD |

---

## Plan jour par jour

| Jour | Livrable | Owner | Validation |
|------|----------|-------|------------|
| Lun 19 – Mar 20 | Requêtes optimisées (< 1s si possible), filtres interactifs, couleurs cohérentes | BI Dev | PO |
| Mer 21 | Les ~25 KPI MVP vérifiés présents dans les dashboards, drill-down ajouté | BI Dev | Architecte (perf) |
| Jeu 22 | **Réunion direction** : walkthrough, validation des chiffres, feedback capturé | PO + Chef Projet | Directeur + Mahamane |
| Ven 23 | `dbt docs generate`, README dbt, glossaire, template Excel exportable | Architecte | Chef Projet |

---

## Definition of Done du sprint

Sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable — *pour un KPI* et *pour une Session de Validation Métier* :

- [ ] Chaque KPI : définition écrite, formule SQL testée, cible/seuil documenté, entré dans le Dictionnaire KPI ([bi/07_Dictionnaire_KPI_Technique.md](../bi/07_Dictionnaire_KPI_Technique.md) + [bi/07_Dictionnaire_KPI_Metier.md](../bi/07_Dictionnaire_KPI_Metier.md)) — *formule SQL testée en local pour KPI-001–009, 101–106, 201–206, 301–306, 401–402 (17/07) ; définition/cible déjà documentées depuis avant Sprint 1, rien à changer ici*
- [ ] Session de validation : invitation Direction + 2 superviseurs min, checklist "chiffres cohérents ?" / "anomalies ?" passée
- [ ] Notes prises + tickets créés pour tout changement demandé
- [ ] Signature d'approbation obtenue

## Gate de sortie (G3)

- [ ] 5 dashboards finalisés
- [ ] ~25 KPI MVP opérationnels
- [ ] Sign-off Direction obtenu
- [ ] Anomalies découvertes documentées (produits déficitaires, superviseurs à restructurer)

**Décision** : GO Sprint 4 / NO-GO (bloquants à documenter dans [chef_projet/RISQUES.md](../chef_projet/RISQUES.md))

---

## Rétrospective

- Qu'est-ce qui a bien marché ?
- Qu'est-ce qui a bloqué ?
- Statut : READY FOR GO-LIVE ? 🟢 / 🟡 / 🔴
- Ajustements pour Sprint 4 :
