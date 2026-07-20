# Planning – DAMS BI MVP

**Durée** : 4 semaines (Juillet 2026), organisées en **4 sprints d'1 semaine**
**Objectif** : Livrer 5 dashboards Metabase + infrastructure BI
**Owner** : Chef de Projet

Le détail jour par jour, les stories rattachées et la Definition of Done de chaque sprint sont dans [../sprints/](../sprints/README.md). Ce document reste la vue d'ensemble haut niveau — ne pas dupliquer le détail ici.

---

## Vue d'ensemble

```
Sprint 1 (05–11 Juil)  │ Fondations (dbt + Facts)              → sprints/SPRINT_1_Fondations.md
Sprint 2 (12–18 Juil)  │ Modèles (Dimensions + Dashboards v1)  → sprints/SPRINT_2_Modeles_Dashboards.md
Sprint 3 (19–25 Juil)  │ Dashboards (Version finale)           → sprints/SPRINT_3_Validation_Metier.md
Sprint 4 (26–31 Juil)  │ Validation + Go-Live                  → sprints/SPRINT_4_GoLive.md
```

---

## 🚨 Points de Contrôle (Gate Critiques)

| Sprint | Gate | Critère | Owner |
|--------|------|---------|-------|
| **S1** | Facts OK | 5 facts chargées + 15 tests passent | Chef Projet |
| **S2** | Dashboards v1 | 5 dashboards opérationnels < 2s | Chef Projet |
| **S3** | Validation | Sign-off direction | PO |
| **S4** | Go-Live | QA checklist + production déployée | Chef Projet |

---

## 🎯 KPI Projet

| Métrique | Cible |
|----------|-------|
| Temps exécution requête | < 2 sec |
| % tests dbt passés | 100% |
| Availability dashboards | 99% (24/5) |
| Time-to-answer question métier | < 1 min |
| User satisfaction | > 4/5 (survey) |

---

## 📞 Escalades & Risques

**Si blocage identifié** :
1. Noter le blocage dans [RISQUES.md](RISQUES.md) dès qu'il apparaît
2. Décider d'un plan d'action et le documenter

Pas de réunion de triage ni de standup — un seul porteur de projet, pas de synchronisation d'équipe nécessaire (voir [../sprints/README.md](../sprints/README.md)).

**Rythme de suivi** :
- **Point de fin de sprint** : Ven 16:00 — DoD + gate + rétrospective (~15 min, détaillé dans [../sprints/README.md](../sprints/README.md))

---

## ✨ Après Go-Live

Voir [../owner/03_Roadmap.md](../owner/03_Roadmap.md) pour le détail v1.5 (août) et v2.0 (septembre+).

---

**Validé par** : Chef Projet
**Dernière maj** : 16 juillet 2026
**Status** : ✅ READY — découpage en sprints effectué, voir [../sprints/](../sprints/README.md)
