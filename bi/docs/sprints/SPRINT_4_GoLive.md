# Sprint 4 — QA, déploiement et formation (26–31 juillet 2026)

> ⚠️ **Point de vigilance après Sprint 1.** Le projet dbt a été développé et testé sur une base PostgreSQL **locale** (`dams_dev`, restaurée depuis un dump) — l'accès au serveur PostgreSQL de **production** (LWS, ADR-001) n'a jamais été validé dans ce projet. À vérifier **en tout début de Sprint 4**, pas le jour du déploiement : accès réseau, identifiants, permissions de création du schéma `bi_` sur l'instance réelle. Voir R15 dans [chef_projet/RISQUES.md](../chef_projet/RISQUES.md).

**Objectif** : tests finaux, déploiement production, formation Direction, go-live officiel.
**Jalon Roadmap** : G4 🚀 — *Go-Live*
**Owner sprint** : Chef Projet (exécution + gate)

---

## Backlog du sprint

Voir détail complet dans [owner/02_Backlog.md](../owner/02_Backlog.md).

| # | Story | Priorité |
|---|-------|----------|
| S-005 | Refresh batch nuit (23h00 Mali) | 🟡 SHOULD |
| S-601 | dbt docs (lineage) | 🟡 SHOULD |
| S-602 | Export Excel mensuel | 🟡 SHOULD |
| S-603 | Formation Direction (30 min) + guide de lecture | 🔴 MUST |

---

## Plan jour par jour

| Jour | Livrable | Owner | Validation |
|------|----------|-------|------------|
| Lun 26 | Checklist QA signée (tests dbt, requêtes < 2s, pas de NULL anormal, backups OK) | Chef Projet | Direction |
| Mar 27 | Documentation finale (README par dossier, guide "comment lire les dashboards", FAQ) | Architecte + BI Dev | Chef Projet |
| Mer 28 | Déploiement production : schéma `bi_`, cron dbt (23h00), alertes email, Metabase, credentials | Architecte + BI Dev | Chef Projet |
| Jeu 29 – Ven 30 | Formation Direction (30 min) + superviseurs (optionnel, 20 min), support en direct | PO + Mahamane | Direction + superviseurs |
| Ven 30 (16h00) | Rétrospective finale du MVP | Chef Projet | Toute l'équipe |

---

## Definition of Done du sprint

Sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable — *pour la Livraison MVP* :

- [ ] Artefacts : 5 dashboards Metabase fonctionnels, dbt project complet avec tests, Dictionnaire KPI, Architecture documentée
- [ ] Infrastructure : schéma `bi_` en production, ETL nuit actif, backups quotidiens
- [ ] Accès : URL Metabase fournie, credentials distribuées, permissions read-only
- [ ] Formation : walkthrough 30 min Direction, documentation utilisateur, support email identifié

## Gate de sortie (G4 — GO-LIVE)

- [ ] Checklist QA 100% verte
- [ ] Infrastructure déployée en production
- [ ] Direction formée et autonome sur les dashboards
- [ ] Support post-lancement en place (Mahamane)

**Décision** : GO-LIVE officiel — vendredi 30 juillet 2026.

---

## Rétrospective finale MVP

- Qu'est-ce qui a bien marché ?
- Qu'est-ce qui s'est mal passé ?
- Quoi améliorer en v1.5 (août) ? → voir [owner/03_Roadmap.md](../owner/03_Roadmap.md)
- Quoi pour v2.0 (septembre+) ? → voir [owner/03_Roadmap.md](../owner/03_Roadmap.md)
