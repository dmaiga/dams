# Structure Engineering OS – DAMS BI

Organisation par rôles et responsabilités

---

## 📁 Architecture Dossiers

```
dams-bi/
│
├── 📂 owner/                          ← Product Owner (Vision métier)
│   ├── 01_Vision_Produit.md             "Pourquoi on fait ça ?"
│   ├── 02_Backlog.md                    "Quoi faire ensuite ?"
│   ├── 03_Roadmap.md                    "Quand et dans quel ordre ?"
│   └── README.md                      → "Guide PO"
│
├── 📂 architecte/                     ← Data Architect (Comment on le construit)
│   ├── 04_ADR.md                        "Decisions techniques"
│   ├── 05_Architecture.md               "Stack + Flux + Lineage"
│   ├── 06_Modele_Multidimensionnel.drawio    "Schéma en étoile"
│   ├── FLUX_PAIEMENT.md                 "Diagrammes cash"
│   ├── REFERENCE_TECHNIQUE_BI.md        "Modèles réels, écarts, source de vérité dbt"
│   └── README.md                      → "Guide Architecte"
│
├── 📂 bi/                             ← BI Developer (Dashboards + KPI)
│   ├── 07_Dictionnaire_KPI_Technique.md "KPI + formules SQL (technique)"
│   ├── 07_Dictionnaire_KPI_Metier.md    "KPI en langage métier (Direction)"
│   ├── 08_Dashboard_Catalog.md          "5 dashboards spécifiés"
│   ├── queries/                         Requêtes SQL ad-hoc
│   │   └── queries_utiles.sql
│   ├── tests/                           Tests données
│   │   └── validations.sql
│   └── README.md                      → "Guide BI Dev"
│
├── 📂 chef_projet/                    ← Chef de Projet (Quality + Planning)
│   ├── 09_Qualite_DoD.md                "Definition of Done"
│   ├── risques.md                       "Risk Register (léger)"
│   ├── planning.md                      "Calendrier 4 semaines"
│   └── README.md                      → "Guide Chef Projet"
│
├── 📂 shared/                        ← Pour Tout Le Monde
│   ├── INDEX.md                         "Résumé complet"
│   ├── README_ENGINEERING_OS.md         "Guide de lecture"
│   ├── SYNTHESE_REVISIONS.md            "Changements apportés"
│   └── GLOSSAIRE.md                     "Définitions métier"
│
├── 📂 sprints/                        ← Chef de Projet (Exécution du MVP)
│   ├── README.md                        "Cadence, cérémonies, index"
│   ├── SPRINT_1_Fondations.md           "S1 : facts + tests"
│   ├── SPRINT_2_Modeles_Dashboards.md   "S2 : dimensions + dashboards v1"
│   ├── SPRINT_3_Validation_Metier.md    "S3 : KPI complets + sign-off"
│   └── SPRINT_4_GoLive.md               "S4 : QA + déploiement + formation"
│
├── 📂 dbt/                            ← Code (ne pas confondre avec docs)
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_*.sql
│   │   └── marts/
│   │       ├── fct_*.sql
│   │       └── dim_*.sql
│   ├── tests/
│   │   └── *.yml
│   ├── dbt_project.yml
│   └── README.md                      → "Guide dbt setup"
│
└── 📂 sql/                            ← Requêtes pontuelles
    └── README.md
```

---

## 👤 Par Rôle : Ce Qu'On Lit

### **📋 PRODUCT OWNER**

**📂 Dossier** : `owner/`

**Fichiers clés** :
- ✅ `owner/01_Vision_Produit.md` — **LIS D'ABORD** (pourquoi on construit)
- ✅ `owner/02_Backlog.md` — Quoi faire ensuite (priorités)
- ✅ `owner/03_Roadmap.md` — Quand (jalons)
- ✅ `shared/INDEX.md` — Résumé 3 min

**Tâches** :
- [ ] Valider vision (10 questions métier)
- [ ] Approuver 5 dashboards
- [ ] Valider KPI principal (Rentabilité nette)
- [ ] Valider objectifs agents (50 kg/jour)

---

### **🏗️ ARCHITECTE DATA**

**📂 Dossier** : `architecte/`

**Fichiers clés** :
- ✅ `architecte/04_ADR.md` — Pourquoi PostgreSQL + dbt + Metabase
- ✅ `architecte/05_Architecture.md` — Comment on le construit (flux, lineage, infra)
- ✅ `architecte/06_Modele_Multidimensionnel.drawio` — Schéma en étoile (facts + dims)
- ✅ `architecte/FLUX_PAIEMENT.md` — Diagrammes cash end-to-end

**Tâches** :
- [ ] Approuver stack (PostgreSQL + dbt + Metabase)
- [ ] Créer dbt project
- [ ] Valider schéma `bi_` (facts + dimensions)
- [ ] Mettre en place lineage (dbt docs)

---

### **📊 BI DEVELOPER**

**📂 Dossier** : `bi/`

**Fichiers clés** :
- ✅ `bi/07_Dictionnaire_KPI_Technique.md` — **LIS D'ABORD** (formules SQL, sources dbt)
- ✅ `bi/07_Dictionnaire_KPI_Metier.md` — version langage courant (Direction)
- ✅ `bi/08_Dashboard_Catalog.md` — 5 dashboards (wireframes + specs)
- ✅ `bi/queries/queries_utiles.sql` — Requêtes de base
- ✅ `bi/tests/validations.sql` — Tests données

**Tâches** :
- [ ] Implémenter les 25 KPI MVP (dbt + Metabase)
- [ ] Créer 5 dashboards Metabase
- [ ] Écrire 20+ tests dbt (validations données)
- [ ] Générer dbt docs (lineage)

---

### **⚙️ CHEF DE PROJET**

**📂 Dossier** : `chef_projet/`

**Fichiers clés** :
- ✅ `chef_projet/09_Qualite_DoD.md` — Definition of Done (critères acceptation génériques)
- ✅ `chef_projet/PLANNING.md` — vue d'ensemble du calendrier 4 semaines
- ✅ `sprints/README.md` — cadence + index des 4 sprints
- ✅ `sprints/SPRINT_1_Fondations.md` → `SPRINT_4_GoLive.md` — backlog, plan, DoD, gate par sprint
- ✅ `chef_projet/RISQUES.md` — Risk Register léger (1 page max)

**Tâches** :
- [ ] Gérer le calendrier par sprint (S1 = facts, S2 = dashboards, S3 = validation, S4 = go-live)
- [ ] Vérifier la DoD de sprint avant chaque gate
- [ ] Tracker les risques (blockers ?)
- [ ] Valider livrables + décision GO/NO-GO à chaque fin de sprint

---

### **👥 TOUT LE MONDE**

**📂 Dossier** : `shared/`

**Fichiers clés** :
- ✅ `shared/INDEX.md` — Résumé 3 min du projet entier
- ✅ `shared/README_ENGINEERING_OS.md` — "Comment lire les docs"
- ✅ `shared/SYNTHESE_REVISIONS.md` — Changements version 2.0
- ✅ `shared/GLOSSAIRE.md` — Définitions métier (ROT, agent, superviseur, etc.)

---

## 📖 Comment Naviguer

### **Si tu as 5 minutes**
→ Lis `shared/INDEX.md`

### **Si tu as 15 minutes**
→ Lis `shared/README_ENGINEERING_OS.md`

### **Si tu es Product Owner**
→ Ouvre `owner/` et lis dans cet ordre :
1. `01_Vision_Produit.md`
2. `02_Backlog.md`
3. `03_Roadmap.md`

### **Si tu es Architecte**
→ Ouvre `architecte/` et lis dans cet ordre :
1. `04_ADR.md`
2. `05_Architecture.md`
3. `06_Modele_Multidimensionnel.drawio`

### **Si tu es BI Developer**
→ Ouvre `bi/` et lis dans cet ordre :
1. `07_Dictionnaire_KPI_Technique.md` (+ `07_Dictionnaire_KPI_Metier.md` pour la version Direction)
2. `08_Dashboard_Catalog.md`
3. `queries/queries_utiles.sql`

### **Si tu es Chef de Projet**
→ Ouvre `chef_projet/` et lis dans cet ordre :
1. `09_Qualite_DoD.md`
2. `planning.md`
3. `risques.md`

---

## 🚀 Setup Réel (Pour Mahamane)

```bash
# Clone le repo (quand git activé)
git clone https://github.com/[...]/dams-bi.git
cd dams-bi

# Structure créée
tree -L 2
dams-bi/
├── owner/
│   ├── 01_Vision_Produit.md
│   ├── 02_Backlog.md
│   ├── 03_Roadmap.md
│   └── README.md
├── architecte/
│   ├── 04_ADR.md
│   ├── 05_Architecture.md
│   ├── 06_Modele_Multidimensionnel.drawio
│   ├── FLUX_PAIEMENT.md
│   └── README.md
├── bi/
│   ├── 07_Dictionnaire_KPI_Technique.md
│   ├── 07_Dictionnaire_KPI_Metier.md
│   ├── 08_Dashboard_Catalog.md
│   ├── queries/
│   ├── tests/
│   └── README.md
├── chef_projet/
│   ├── 09_Qualite_DoD.md
│   ├── planning.md
│   ├── risques.md
│   └── README.md
├── shared/
│   ├── INDEX.md
│   ├── README_ENGINEERING_OS.md
│   ├── SYNTHESE_REVISIONS.md
│   └── GLOSSAIRE.md
├── dbt/
│   ├── models/
│   ├── tests/
│   └── dbt_project.yml
└── sql/
    └── queries_utiles.sql

# Initialiser dbt
cd dbt
dbt init --project-dir .

# Vérifier structure
ls -la owner/ architecte/ bi/ chef_projet/ shared/ dbt/ sql/
```

---

## 📌 Règles de Cohabitation

### **✅ DO**
- Chaque rôle lit SON dossier en priorité
- Docs sharedes = `shared/` (pas de copie)
- Code dbt = `dbt/` (séparé des docs)
- Chaque doc = propriétaire clair (voir header du fichier)

### **❌ DON'T**
- Ne pas mélanger code + docs
- Ne pas dupliquer docs dans plusieurs dossiers
- Ne pas push docs sans expliquer changement

> Tous les rôles ci-dessus sont portés par la même personne (Mahamane) : la séparation par dossier structure les *types de décision*, pas une coordination entre personnes. Pas de notification/validation croisée entre "rôles" — juste mettre à jour le bon dossier au bon moment.

---

## 🔄 Workflow de Mise à Jour

```
Changement de vision/priorités ?
→ Update `owner/03_Roadmap.md` (+ `02_Backlog.md` si stories impactées)

Changement de stack/décision technique ?
→ Update `architecte/04_ADR.md`

Ajout/modif KPI ?
→ Update `bi/07_Dictionnaire_KPI_Technique.md` + `bi/07_Dictionnaire_KPI_Metier.md`
→ Update `bi/08_Dashboard_Catalog.md` si impact dashboard

Risque identifié ?
→ Update `chef_projet/RISQUES.md`
```

---

## 📊 Responsabilités Claires

| Rôle | Lit | Édite | Approuve |
|------|-----|-------|----------|
| **PO** | `owner/*` | Vision + Backlog + Roadmap | Scope + KPI |
| **Architecte** | `architecte/*` | ADR + Architecture + Model | Stack + Lineage |
| **BI Dev** | `bi/*` | KPI + Dashboard + Tests | Implémentation |
| **Chef Projet** | `chef_projet/*`, `sprints/*` | DoD + Planning + Sprints + Risques | Quality gate (par sprint) |
| **Tout monde** | `shared/*` | SYNTHESE + Glossaire | Aucun (lecture) |

---

## 🎯 Exemple : Ajouter un KPI

**Scénario** : PO dit "Je veux un KPI sur les agents sous objectif"

**Étapes** :
1. **PO** : Update `owner/02_Backlog.md` (ajouter story)
2. **Architecte** : Review (impact données ? besoin nouvelle table ?)
3. **BI Dev** : 
   - Ajoute KPI dans `bi/07_Dictionnaire_KPI_Technique.md` et `bi/07_Dictionnaire_KPI_Metier.md`
   - Ajoute dans `bi/08_Dashboard_Catalog.md` (quel dashboard ?)
   - Implémente en dbt
   - Ajoute test
4. **Chef Projet** : Vérifie DoD (tests ? documentation ?)
5. **PO** : Valide visuellement (Metabase)

**Trace** : Commit git = "feat: add KPI-401 agents objectif" + référence story

---

## ✨ Avantage de Cette Structure

| Avant | Après |
|-------|-------|
| 9 fichiers en vrac | 9 fichiers organisés par rôle |
| Pas clair qui lit quoi | Chacun sait quoi lire |
| Débat sur vision/technique mélangés | Séparation claire |
| Pas de propriétaire document | Chaque doc = propriétaire |
| Risque d'éditer wrong doc | Dossier = périmètre clair |

---

## 📝 Template Header (Chaque Document)

```markdown
# [Titre]

**Propriétaire** : [Rôle] (PO / Architecte / BI Dev / Chef Projet)  
**Audience** : [Qui lit ça]  
**Fréquence mise à jour** : [Chaque sprint / Chaque semaine / Ad-hoc]  
**Dernière modification** : [Date]  
**Version** : [1.0 / 1.5 / 2.0]

---

[Contenu]
```

---

## 🚀 Prochains Pas

1. **Crée la structure** de dossiers (8 dossiers)
2. **Distribue les fichiers** dans les bons dossiers
3. **Chaque rôle** lit SON dossier
4. **Chef Projet** crée `planning.md` + `risques.md`
5. **Go S1** (Semaine 1)

Besoin d'aide pour le setup Git ? Je peux créer un `.gitignore` + structure repo aussi.
