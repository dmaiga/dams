# 🎯 Engineering OS DAMS BI – Livrables Juillet 2026

**Date** : 2 Juillet 2026  
**Projet** : Plateforme Business Intelligence pour la distribution DAMS  
**Scope** : Période 01/01 – 30/06 2026 (MVP)  
**Owner** : Mahamane Daouda Maïga  

---

## 📦 Fichiers Livrés (8 documents = 104 KB)

### 1. **README_ENGINEERING_OS.md** (8.2 KB)
**LISEZ CECI EN PREMIER**

Guide de lecture des 7 documents. Explique :
- Qui doit lire quoi et quand
- Calendrier juillet (4 semaines)
- Checklist avant démarrage
- Stack technologique (PostgreSQL + dbt + Metabase = 0€)

---

### 2. **01_Vision_Produit.md** (6.9 KB)
**Product Owner → Contexte & Objectifs**

Résume :
- Le problème réel (qui rapporte vs qui coûte)
- Les 9 dimensions de questions métier
- MVP scope (5 dashboards, 25 KPI)
- KPI critiques (Rentabilité nette = centerpiece)
- Personas & cas d'usage

**À lire** : Dès le démarrage (5 min)

---

### 3. **04_ADR.md** (7.2 KB)
**Architecte → Décisions Techniques**

6 Architecture Decision Records :
- **ADR-001** : PostgreSQL comme DW (zéro coût, suffit pour MVP)
- **ADR-002** : dbt pour ETL (SQL-first, tests intégrés)
- **ADR-003** : Metabase pour BI (30 min setup)
- **ADR-004** : Période figée 01/01 – 30/06 (non flexible)
- **ADR-005** : Schéma `bi_` isolé (zéro impact DAMS prod)
- **ADR-006** : Refresh nuit batch (23h00 Mali)

**Statut** : ✅ Tous acceptés

---

### 4. **05_Architecture.md** (20 KB)
**Architecte → Implémentation Technique**

Contient :
- Flux financier end-to-end (vente → dépense → rentabilité)
- Data lineage (source → staging → fact → view → dashboard)
- Schéma en étoile (5 facts + 6 dimensions + 5 aggregates)
- Stack détaillé (tech + versions)
- Processus ETL nuit (timing, monitoring)
- Infrastructure déploiement
- Calendrier 4 semaines

---

### 5. **07_Dictionnaire_KPI.md** (15 KB)
**BI Developer → Référence Complète KPI**

Définition de 25 KPI MVP :

**Critiques (9)**
- KPI-001 à 009 : CA, marge, salaires, dépenses, rentabilité

**Produit (6)**
- KPI-101 à 106 : CA, marge, rotation, déficitaires

**Superviseur (6)**
- KPI-201 à 206 : Performance, coût équipe, rentabilité

**Agent (6)**
- KPI-301 à 306 : CA, marge, incentive, rentabilité

**Stock & Fournisseur (5)**
- KPI-401 à 405 : Valeur stock, rotation, marges fournisseur

Chaque KPI inclut : nom, définition, formule SQL, dimension, cible, source

---

### 6. **08_Dashboard_Catalog.md** (27 KB)
**BI Developer → Spécifications 5 Dashboards**

| Dashboard | Audience | Fréquence | KPI Principal |
|-----------|----------|-----------|---------------|
| **1. Santé Globale** | Direction | Quotidienne | Rentabilité Nette |
| **2. Rentabilité Produit** | Manager Produit | Bihebdomadaire | Produits Déficitaires |
| **3. Performance Superviseur** | Direction/RH | Mensuel | Rentabilité Superviseur |
| **4. Performance Agent** | Superviseur | Hebdomadaire | Rentabilité Agent |
| **5. Stock & Fournisseur** | Manager Produit | Mensuel | Valeur Stock |

Chaque dashboard inclut : objectif, layout ASCII, KPI, filtres, interactivité

---

### 7. **FLUX_PAIEMENT.md** (21 KB)
**Tous → Compréhension du Flux Cash**

Diagramme complet du flux financier :
1. **Vente** : Agent terrain → Recouvrement → Superviseur
2. **Remise** : Superviseur → ROT
3. **Dépenses** : ROT utilise l'argent (transport, carburant, etc.)
4. **Versement** : Cash restant → Banque
5. **Salaires** : Parallèle (agents terrain, gros, superviseurs)
6. **Rentabilité** : Synthèse finale (Marge − Salaires − Dépenses)

Inclus : mapping données DAMS → BI, validations clés, anomalies à surveiller

---

### 8. **09_Qualite_DoD.md** (6.6 KB)
**Chef de Projet → Critères d'Acceptation**

Definition of Done pour :
- ✅ Un dbt model (SQL + tests + docs)
- ✅ Un dashboard Metabase (5+ charts, < 2s execution)
- ✅ Un KPI (formule + dimension + cible)
- ✅ Un test de qualité (80%+ couverture)
- ✅ L'ETL nuit (< 30 min, logs, alertes)
- ✅ Un rapport Excel (format, traffic lights)
- ✅ Livraison MVP (checklist finale)

---

## 🎯 Résumé Exécutif

### Le Problème
DAMS génère des ventes mais ne sait pas :
- Faisons-nous des bénéfices réellement ?
- Quels produits arrêter (déficitaires) ?
- Quel superviseur coûte trop cher ?
- Où dorment nos millions en stock ?

### La Solution
5 dashboards analytiques (Metabase) sur PostgreSQL, rafraîchis chaque nuit via dbt.

**Exemple** : 
```
CA Mois         : 10,000,000 FCFA
Coût Achat      : -5,000,000
─────────────────────────────
Marge Brute     : 5,000,000

Salaires/Paie   : -1,200,000
Dépenses ROT    : -400,000
─────────────────────────────
Rentabilité Nette : 3,400,000 ✅
```

### Le Stack (0€)
- PostgreSQL (schéma `bi_`)
- dbt Core (orchestrateur ETL)
- Metabase (dashboards)
- cron nuit (refresh automatique)

### Le Timeline
| Semaine | Livrables |
|---------|-----------|
| S1 | dbt project + 5 facts |
| S2 | 5 dimensions + premières vues |
| S3 | 5 dashboards Metabase |
| S4 | Validation + go-live |

Détail par sprint (backlog, plan jour par jour, DoD, gate) : [../sprints/README.md](../sprints/README.md)

---

## 🗺️ Comment Démarrer

### Jour 1 : Lecture & Validation (Mahamane)
```
1. Lis README_ENGINEERING_OS.md (5 min)
2. Lis 01_Vision_Produit.md (5 min)
3. Confirmez avec Direction : 5 questions OK ? (15 min)
```

### Jour 2 : Architecture (Mahamane)
```
1. Lis 04_ADR.md (5 min)
2. Lis 05_Architecture.md (15 min)
3. Confirmez stack (PostgreSQL + dbt + Metabase)
4. Créez dbt project
```

### Jour 3-4 : Modélisation (Mahamane)
```
1. Lis 07_Dictionnaire_KPI.md (20 min)
2. Créez dbt models (facts + dimensions)
3. Écrivez tests dbt (min 2/model)
```

### Jour 5-6 : Dashboards (Mahamane)
```
1. Lis 08_Dashboard_Catalog.md (20 min)
2. Créez 5 dashboards Metabase
3. Testez + validez avec Direction
```

### Jour 7 : Validation Finale (Direction + Mahamane)
```
1. Walkthrough direction (30 min)
2. Bug fixes (si besoin)
3. Go-live ✅
```

---

## 📊 Les 5 Réponses Principales

| Question | Dashboard | Métrique |
|----------|-----------|---------|
| Faisons-nous des bénéfices ? | 1. Santé Globale | KPI-009 : Rentabilité Nette |
| Quels produits arrêter ? | 2. Rentabilité Produit | KPI-106 : Produits Déficitaires |
| Quel superviseur performer ? | 3. Performance Superviseur | KPI-204 : Rentabilité Superviseur |
| Qui vend vraiment ? | 4. Performance Agent | KPI-304 : Rentabilité Agent |
| Où dort le capital ? | 5. Stock & Fournisseur | KPI-401 : Valeur Stock |

---

## ⚙️ Prochaines Étapes

### Immédiates (Aujourd'hui)
- [ ] Télécharger les 8 documents
- [ ] Lire README_ENGINEERING_OS.md
- [ ] Valider vision avec Direction

### S1 (Semaine 1)
- [ ] Créer dbt project
- [ ] Créer schéma `bi_` PostgreSQL
- [ ] Écrire 5 facts models

### S2-S3 (Semaines 2-3)
- [ ] Créer 5 dashboards Metabase
- [ ] Écrire tests dbt (20+ tests)
- [ ] Générer dbt docs

### S4 (Semaine 4)
- [ ] Validation métier
- [ ] Go-live

---

## 🤝 Support

**Questions ?**
1. Relis le README (70% de chances tu trouveras la réponse)
2. Cherche dans le doc correspondant (ex: KPI → 07_Dictionnaire_KPI.md)
3. Contact Mahamane (slack/email)

---

## ✅ Checklist Livraison

- [x] Vision produit définie (01_Vision)
- [x] Décisions architecturales prises (04_ADR)
- [x] Architecture technique décrite (05_Architecture)
- [x] KPI dictionnaire complet (07_Dictionnaire)
- [x] 5 Dashboards spécifiées (08_Catalog)
- [x] Definition of Done (09_DoD)
- [x] Flux cash documenté (FLUX_PAIEMENT)
- [x] Guide utilisateur (README_ENGINEERING_OS)

**Status** : ✅ READY FOR DEVELOPMENT

---

**Next** : Ouvre `README_ENGINEERING_OS.md` et commence !

Bon courage 🚀
