# DAMS BI – Engineering OS (Juillet 2026)

Bienvenue dans l'Operating System pour la plateforme Business Intelligence dédiée à la distribution DAMS.

---

## 📋 Qu'est-ce que c'est ?

C'est l'**ensemble minimaliste de documents** qui guide le projet BI du démarrage (juillet) au go-live (fin juillet 2026).

**Principe** : Chaque document sert à **prendre une décision** ou **construire quelque chose**. Rien de plus.

---

## 🗂️ Structure

```
dams-bi/

├── 01_Vision_Produit.md            ← Pourquoi on construit ça ?
├── 04_ADR.md                       ← Quelles décisions d'archi ?
├── 05_Architecture.md              ← Comment on le construit ?
├── 06_Modele_Multidimensionnel.*   ← Schéma en étoile (TODO: .drawio)
├── 07_Dictionnaire_KPI.md          ← Tous les KPI définis
├── 08_Dashboard_Catalog.md         ← 5 dashboards + wireframes
├── 09_Qualite_DoD.md               ← Critères acceptation
├── FLUX_PAIEMENT.md                ← Flux cash & salaires (visuel)
├── README_ENGINEERING_OS.md        ← Vous lisez ça
│
├── dbt/                            ← Projet dbt (à créer)
│   ├── models/
│   │   ├── staging/                ← Raw extracts (stg_*)
│   │   ├── marts/                  ← Facts & dimensions (fct_*, dim_*)
│   │   └── views/                  ← Aggregates (vw_*)
│   ├── tests/                      ← Tests dbt
│   ├── docs/                       ← Documentations YML
│   └── dbt_project.yml             ← Config
│
└── sql/                            ← Requêtes ad-hoc si besoin
```

---

## 🎯 Pour Qui ? Quand ? Comment ?

### **Rôle = Product Owner** (Mahamane)
**Quand** : Démarrage, priorisations, validation métier  
**Lisez** : 01_Vision_Produit.md (5 min), puis 08_Dashboard_Catalog.md (10 min)  
**Actions** :
- Valider les 5 questions métier clés
- Approuver les 5 dashboards
- Valider rentabilité nette comme KPI principal ⭐

---

### **Rôle = Architecte Data** (Mahamane)
**Quand** : Conception, implémentation, tests  
**Lisez** : 04_ADR.md (5 min), 05_Architecture.md (10 min), 06_Modèle (20 min)  
**Actions** :
- Confirmer PostgreSQL + dbt + Metabase
- Créer schéma `bi_` + premiersmodels dbt
- Valider lineage (source → fact → dashboard)

---

### **Rôle = BI Developer** (Mahamane)
**Quand** : Implémentation dashboards, tests  
**Lisez** : 07_Dictionnaire_KPI.md (15 min), 09_Qualite_DoD.md (5 min)  
**Actions** :
- Implémenter les 25 KPI MVP
- Construire les 5 dashboards Metabase
- Valider tests dbt (>20 tests)

---

### **Rôle = Direction / Métier**
**Quand** : Validation final (fin juillet)  
**Lisez** : 01_Vision_Produit.md (5 min), 08_Dashboard_Catalog.md (15 min), FLUX_PAIEMENT.md (5 min)  
**Actions** :
- Valider les chiffres (CA, marge, rentabilité)
- Approuver les 5 dashboards
- Autoriser go-live

---

## 📅 Calendrier (Juillet)

| Semaine | Livrables | Owner | Validation |
|---------|-----------|-------|------------|
| **S1** | dbt project + 5 facts | Architect | ADR confirmé ✓ |
| **S2** | Dimensions + premiers dashboards | BI Dev | Wireframes vs réalité |
| **S3** | 5 dashboards complets + tests | BI Dev | Direction walkthrough |
| **S4** | Validation + go-live | Direction + Arch | Sign-off final |

---

## 🚀 Quick Start

**Jour 1 (Mahamane)**
```bash
# 1. Créer le repo
git init dams-bi
cd dams-bi

# 2. Initialiser dbt
dbt init dbt --adapter postgres

# 3. Copier ce README et les docs
cp /path/to/01_Vision_Produit.md .
cp /path/to/04_ADR.md .
# ... etc

# 4. Premier model test
# dbt/models/staging/stg_ventes.sql
# SELECT * FROM public.core_vente LIMIT 100
```

**Jour 2-3 (Modèles dbt)**
```bash
# Créer les facts
dbt run --select fct_ventes
dbt run --select fct_salaires
dbt run --select fct_depenses
dbt test --select fct_*

# Vérifier le schéma
dbt docs generate
dbt docs serve  # http://localhost:8000
```

**Jour 4-6 (Dashboards)**
- Connecter Metabase à PostgreSQL schéma `bi_`
- Créer 5 dashboards (1 par jour)
- Validation métier

---

## 📊 Les 5 Questions Clés (Raison d'être)

```
Dashboard 1 : "Faisons-nous des bénéfices ?" 
            → KPI-009 : Rentabilité Nette

Dashboard 2 : "Quels produits arrêter / développer ?"
            → KPI-106 : Produits Déficitaires

Dashboard 3 : "Quel superviseur performer ?"
            → KPI-204 : Rentabilité Superviseur

Dashboard 4 : "Qui vend ?"
            → KPI-304 : Rentabilité Agent

Dashboard 5 : "Où dort le capital ?"
            → KPI-401 : Valeur Stock
```

---

## ⚙️ Stack Tech (Rappel)

| Couche | Tech | Coût |
|--------|------|------|
| **Source** | DAMS PostgreSQL (public.*) | 0€ |
| **Transformation** | dbt Core | 0€ |
| **Warehouse** | PostgreSQL schéma `bi_` | 0€ |
| **BI** | Metabase Docker | 0€ |
| **Infra** | LWS cPanel + VM locale | Existant |

---

## 🔍 Comment Lire les Docs ?

### Si tu as **5 min**
→ Lis **01_Vision_Produit.md** (contexte + objectifs)

### Si tu as **15 min**
→ Ajoute **08_Dashboard_Catalog.md** (wireframes + KPI)

### Si tu as **30 min**
→ Ajoute **04_ADR.md** + **05_Architecture.md** (décisions + infra)

### Si tu dois **implémenter**
→ Ajoute **07_Dictionnaire_KPI.md** (formules) + **09_Qualite_DoD.md** (tests)

### Si tu dois **comprendre le flux cash**
→ Lis **FLUX_PAIEMENT.md** (diagrammes visuels)

---

## 📌 Points Critiques

### ✅ Ce qui est figé (non-négociable)
- Période : 01/01 – 30/06 2026 (pas flexible)
- Scope facts : Ventes, salaires, dépenses, stocks
- KPI principal : Rentabilité nette (Marge − Salaires − Dépenses)
- Architecture : PostgreSQL + dbt + Metabase (approuvé)

### ⚠️ Ce qui est flexible
- Nombre exact dashboards (MVP = 5, peut augmenter V2)
- Nombre KPI (MVP = 25, peut augmenter)
- Design Metabase (couleurs, layouts)
- Refresh frequency (nuit → hourly en V2)

### 🚨 Ce qu'il NE FAUT PAS faire
- ❌ Modifier les modèles DAMS production
- ❌ Hardcoder les valeurs (utiliser variables dbt)
- ❌ Sauter les tests dbt (20 min pour 30 min gained later)
- ❌ Oublier la documentation YML (tu oublieras sinon)

---

## 🎓 Ressources Utiles

**dbt**
- Docs : https://docs.getdbt.com
- Tutorial : https://docs.getdbt.com/guides/dbt-tutorial
- Slack community : https://community.getdbt.com

**Metabase**
- Docs : https://www.metabase.com/docs/
- Setup guide : https://www.metabase.com/docs/latest/installation-and-operation

**PostgreSQL**
- Window functions : https://www.postgresql.org/docs/13/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS
- Aggregations : https://www.postgresql.org/docs/13/functions-aggregate.html

---

## 💬 Support & Questions

- **Mahamane** : Architecture + dbt + direction
- **Claude** : Reviews documentation, brainstorm alternative solutions

**Process** :
1. Problème bloquant ? → Slack / email immédiat
2. Question design ? → Doc d'abord, puis discus
3. Feature request ? → Backlog V2 (août+)

---

## ✍️ Mises à Jour Doc

**Règle** : Mettre à jour le doc **AVANT** de commencer le travail.
- Changement de scope ? → Update 01_Vision_Produit.md
- Changement stack ? → Update 04_ADR.md
- Nouveau KPI ? → Update 07_Dictionnaire_KPI.md

**Format commit** :
```
docs: update 07_Dictionnaire_KPI with KPI-701 (stock alerts)
```

---

## 🏁 Succès = ?

**En fin juillet :**
- ✅ 5 dashboards Metabase, toutes les requêtes < 2s
- ✅ 25 KPI définis et testés (dbt tests)
- ✅ Direction fait un walkthrough et approuve
- ✅ ETL nuit (dbt run) automatisé et stable
- ✅ Documentation complète

**Après go-live :**
- ✅ 0 crash dashboard en production
- ✅ Questions métier répondues en < 1 min
- ✅ 3+ produits/superviseurs identifiés comme non-rentables

---

## 📞 Checklist Avant de Commencer

- [ ] J'ai lu 01_Vision_Produit.md
- [ ] J'ai compris les 5 questions métier
- [ ] J'ai confirmé le scope (PostgreSQL + dbt + Metabase)
- [ ] J'ai un accès PostgreSQL DAMS production
- [ ] J'ai dbt installé (`dbt --version`)
- [ ] J'ai Docker / Metabase disponible
- [ ] J'ai un editor SQL (VS Code + dbt extension)
- [ ] J'ai Git configuré

---

**Maintenant** : Ouvre **01_Vision_Produit.md** et commençons ! 🚀
