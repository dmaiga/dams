# Sprints – DAMS BI MVP

**Propriétaire** : Chef de Projet
**Audience** : solo — tous les rôles (PO, Architecte, BI Dev, Chef Projet) sont portés par la même personne (Mahamane)
**Fréquence mise à jour** : Chaque sprint (hebdomadaire)

---

## Cadence

4 sprints d'**1 semaine**, calés sur le calendrier MVP de [owner/03_Roadmap.md](../owner/03_Roadmap.md) :

| Sprint | Dates | Objectif | Jalon (Roadmap) | Fichier |
|--------|-------|----------|------------------|---------|
| **Sprint 1** | 05–11 juil. | Fondations dbt (facts) | G1 — Facts OK | [SPRINT_1_Fondations.md](SPRINT_1_Fondations.md) |
| **Sprint 2** | 12–18 juil. | Dimensions + Dashboards v1 | G2 — Dashboards v1 opérationnels | [SPRINT_2_Modeles_Dashboards.md](SPRINT_2_Modeles_Dashboards.md) |
| **Sprint 3** | 19–25 juil. | Dashboards finaux + validation métier | G3 — Sign-off Direction | [SPRINT_3_Validation_Metier.md](SPRINT_3_Validation_Metier.md) |
| **Sprint 4** | 26–31 juil. | QA + déploiement + formation | G4 🚀 — Go-Live | [SPRINT_4_GoLive.md](SPRINT_4_GoLive.md) |
| **Sprint 5** | 27–31 juil. | Refonte UI/UX exécutive (v1.5, post-clôture v1) | S-709 | [SPRINT_5_UIUX_Executif.md](SPRINT_5_UIUX_Executif.md) |

> Sprint 5 vient après la clôture de la v1 (24/07/2026, voir
> [chef_projet/BILAN_LIVRAISON_VS_VISION.md](../chef_projet/BILAN_LIVRAISON_VS_VISION.md) §8) —
> les jalons G1-G4 ci-dessus restent l'historique du MVP, pas un calendrier encore à venir.

Chaque fichier de sprint contient : objectif, stories du backlog rattachées, plan jour par jour, **Definition of Done du sprint** (sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable à ce sprint), critère de sortie (gate), et une section rétrospective à remplir en fin de semaine.

---

## Points de contrôle (pas de réunions — un seul porteur de tous les rôles)

Pas de standup, pas de revue d'équipe, pas de passation : un seul point de contrôle solo en fin de sprint suffit.

- **Point de fin de sprint** (~15 min, vendredi) : cocher la DoD du sprint + le gate dans le fichier du sprint, avant de passer au suivant
- **Rétrospective** : remplie dans la foulée, section dédiée en bas de chaque fichier de sprint
- **Blocages** : notés dès qu'ils apparaissent dans [chef_projet/RISQUES.md](../chef_projet/RISQUES.md), pas besoin d'attendre une réunion pour les remonter

---

## Règle de cohérence

- Le détail jour par jour et les gates vivent **ici**, pas dans [chef_projet/PLANNING.md](../chef_projet/PLANNING.md) (qui reste la vue d'ensemble haut niveau, sans duplication).
- Les stories restent définies une seule fois dans [owner/02_Backlog.md](../owner/02_Backlog.md) — les fichiers de sprint n'en reprennent que l'ID + le titre court.
- La DoD générique par type de livrable reste dans [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) — chaque sprint n'en cite que le sous-ensemble applicable, pas de copie intégrale.
