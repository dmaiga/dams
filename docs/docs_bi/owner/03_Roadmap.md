# DAMS BI – Roadmap

**Propriétaire** : Product Owner (Mahamane Daouda Maïga)
**Audience** : Toute l'équipe + Direction
**Fréquence mise à jour** : Chaque semaine
**Dernière modification** : 2 juillet 2026
**Version** : 1.0

---

## Vue d'ensemble

```
Juillet 2026        │ MVP v1.0  → 5 dashboards + 25 KPI en production
Août 2026           │ v1.5      → Automatisations & confort
Septembre 2026 +    │ v2.0      → Intelligence (ML, RAG, prévisions)
```

Le détail jour par jour du MVP est tenu par le Chef de Projet dans [../chef_projet/PLANNING.md](../chef_projet/PLANNING.md). Cette roadmap donne la vision produit et les jalons.

---

## 🎯 MVP v1.0 — Juillet 2026 (période analysée : 01/01 → 30/06)

Objectif : la Direction répond à **80 % des questions métier en < 5 min**, sans Excel.

### Semaine 1 (05–11 juil.) — Fondations
- **Jalon G1** : projet dbt opérationnel, schéma `bi_`, **5 fact tables + 15 tests** qui passent.
- Stories : S-001 → S-004.
- Gate : *Facts OK* (Chef Projet).

### Semaine 2 (12–18 juil.) — Modèles + Dashboards v1
- **Jalon G2** : **5 dimensions** créées, Metabase connecté, **5 dashboards v1** (< 2 s).
- Stories : S-003, S-101, S-201, S-301, S-401, S-501.
- Gate : *Dashboards v1 opérationnels* (Chef Projet).

### Semaine 3 (19–25 juil.) — Dashboards finaux + validation métier
- **Jalon G3** : tous les KPI visibles, filtres interactifs, **sign-off Direction**.
- Stories : S-102, S-103, S-202, S-302, S-402, S-502 + affinage.
- Gate : *Validation Direction* (PO).

### Semaine 4 (26–31 juil.) — Go-Live
- **Jalon G4 🚀** : QA finale, déploiement production, cron nuit, **formation Direction**.
- Stories : S-005, S-601, S-602, S-603.
- Gate : *Go-Live* (Chef Projet). **GO-LIVE officiel : vendredi 30 juil.**

### Critères de succès du MVP
- ✅ 5 dashboards opérationnels
- ✅ 3 produits déficitaires identifiés (à arrêter)
- ✅ 2 superviseurs à restructurer identifiés
- ✅ Dépenses ROT clarifiées
- ✅ 100 % des tests dbt passent, requêtes < 2 s

---

## 🔧 v1.5 — Août 2026 (améliorations)

Confort et automatisation, une fois le socle stable.

- **Refresh horaire** (au lieu de nuit uniquement).
- **Alertes automatiques par email** : vente sous prix d'achat, produit/agent déficitaire, dépenses > 15 % du CA.
- **Export PDF mensuel** des dashboards (rapports réguliers).
- Traitement des **nouvelles questions métier** remontées après le go-live (backlog PO).

Stories concernées : réactivation des ⚪ *WON'T now* « alertes » et « export ».

---

## 🚀 v2.0 — Septembre 2026 et au-delà (intelligence)

- **Assistant BI conversationnel** (RAG + LLM) : poser des questions en langage naturel.
- **Prévisions de ventes** (time-series / ML).
- **Recommandations** : quels produits commander, quels agents développer.
- **Analyse fine superviseur** (drill-down avancé).
- **Périodes flexibles** : analyse multi-périodes (au-delà de 01/01–30/06 figé).
- **Analyse des dettes clients** (crédit).

---

## Dépendances & risques

Les décisions techniques structurantes sont dans [../architecte/04_ADR.md](../architecte/04_ADR.md) ; les risques suivis dans [../chef_projet/RISQUES.md](../chef_projet/RISQUES.md).

Points de vigilance produit :
- La période **01/01–30/06 est figée** pour le MVP (ADR-004) — le flexible arrive en v2.
- Le `.drawio` du modèle multidimensionnel et le code `dbt/` sont **à créer** (projet en démarrage).
