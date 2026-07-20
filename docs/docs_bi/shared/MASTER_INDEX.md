# 📚 Master Index – DAMS BI Engineering OS

**Complet & Structuré par Rôles**

---

## 🎯 Commencer Ici (5 minutes)

1. **STRUCTURE_DOSSIERS.md** ← Tu es ici
2. **README_ENGINEERING_OS.md** ← Guide de lecture
3. **INDEX.md** ← Résumé 3 min

Ensuite : ouvre le dossier correspondant à ton rôle ↓

---

## 📁 Structure Réelle à Créer

```
dams-bi/

├── 📂 owner/                          [Product Owner]
│   ├── 01_Vision_Produit.md           ✨ Clé métier
│   ├── 02_Backlog.md                  (À créer)
│   ├── 03_Roadmap.md                  (À créer)
│   └── README.md                      (À créer)
│
├── 📂 architecte/                     [Data Architect]
│   ├── 04_ADR.md                      ✨ Décisions tech
│   ├── 05_Architecture.md             ✨ Flux + Stack
│   ├── 06_Modele_Multidimensionnel.drawio   (À créer)
│   ├── FLUX_PAIEMENT.md               ✨ Diagrammes
│   └── README.md                      (À créer)
│
├── 📂 bi/                             [BI Developer]
│   ├── 07_Dictionnaire_KPI.md         ✨ 28 KPI
│   ├── 08_Dashboard_Catalog.md        ✨ 5 dashboards
│   ├── queries/                       (À créer)
│   ├── tests/                         (À créer)
│   └── README.md                      (À créer)
│
├── 📂 chef_projet/                    [Chef de Projet]
│   ├── 09_Qualite_DoD.md              ✨ Definition of Done (générique)
│   ├── PLANNING.md                    ✨ Vue d'ensemble 4 semaines
│   ├── RISQUES.md                     ✨ Risk Register
│   └── README.md                      (À créer)
│
├── 📂 sprints/                        [Chef de Projet – exécution]
│   ├── README.md                      ✨ Cadence + index des 4 sprints
│   └── SPRINT_1..4_*.md               ✨ Backlog, plan, DoD, gate par sprint
│
├── 📂 partagé/                        [Tout le Monde]
│   ├── INDEX.md                       ✨ Résumé projet
│   ├── README_ENGINEERING_OS.md       ✨ Comment lire
│   ├── SYNTHESE_REVISIONS.md          ✨ Changements v2.0
│   ├── GLOSSAIRE.md                   ✨ Définitions métier
│   ├── STRUCTURE_DOSSIERS.md          ← Ce fichier
│   └── MASTER_INDEX.md                ← Vous lisez ça
│
├── 📂 dbt/                            [Code – à créer]
│   ├── models/staging/
│   ├── models/marts/
│   ├── tests/
│   ├── dbt_project.yml
│   └── README.md
│
└── 📂 sql/                            [Ad-hoc queries]
    └── README.md
```

**✨ = Fichier déjà créé (à télécharger)**  
**(À créer) = Tu dois faire**

---

## 👤 Par Rôle – Ordre de Lecture Recommandé

### **🎯 PRODUCT OWNER (Mahamane = Vision Métier)**

**Commencer ici** :
1. ⏱️ 3 min : **partagé/INDEX.md**
2. ⏱️ 10 min : **partagé/README_ENGINEERING_OS.md**
3. ⏱️ 15 min : **owner/01_Vision_Produit.md** ← CLEF
4. ⏱️ 10 min : **partagé/GLOSSAIRE.md** ← Termes métier

**Après** :
- owner/02_Backlog.md (à créer)
- owner/03_Roadmap.md (à créer)
- PLANNING.md → valider scope + timeline

**Tâches clés** :
- ✅ Valider vision métier
- ✅ Approuver 5 dashboards
- ✅ Valider 28 KPI
- ✅ Valider objectif agents 50kg/jour

---

### **🏗️ ARCHITECTE DATA (Mahamane = Infrastructure)**

**Commencer ici** :
1. ⏱️ 3 min : **partagé/INDEX.md**
2. ⏱️ 10 min : **partagé/README_ENGINEERING_OS.md**
3. ⏱️ 5 min : **architecte/04_ADR.md** ← Décisions approuvées ✅
4. ⏱️ 15 min : **architecte/05_Architecture.md** ← Flux + Stack
5. ⏱️ 20 min : **architecte/FLUX_PAIEMENT.md** ← Diagrammes

**Après** :
- architecte/06_Modele_Multidimensionnel.drawio (à créer)
- Lire bi/07_Dictionnaire_KPI.md → comprendre data needs

**Tâches clés** :
- ✅ Setup PostgreSQL schéma `bi_`
- ✅ Initialiser dbt project
- ✅ Créer modèles staging
- ✅ Créer 5 fact tables

---

### **📊 BI DEVELOPER (Mahamane = Dashboards + KPI)**

**Commencer ici** :
1. ⏱️ 3 min : **partagé/INDEX.md**
2. ⏱️ 10 min : **partagé/README_ENGINEERING_OS.md**
3. ⏱️ 20 min : **bi/07_Dictionnaire_KPI.md** ← 28 KPI + formules
4. ⏱️ 15 min : **bi/08_Dashboard_Catalog.md** ← 5 dashboards specs
5. ⏱️ 5 min : **chef_projet/09_Qualite_DoD.md** ← Critères acceptance

**Après** :
- bi/queries/queries_utiles.sql (à créer)
- bi/tests/validations.sql (à créer)
- Créer dashboards Metabase

**Tâches clés** :
- ✅ Implémenter 28 KPI
- ✅ Créer 5 dashboards < 2s
- ✅ Écrire 20+ tests dbt
- ✅ Générer dbt docs

---

### **⚙️ CHEF DE PROJET (Mahamane = Quality + Planning)**

**Commencer ici** :
1. ⏱️ 3 min : **partagé/INDEX.md**
2. ⏱️ 10 min : **partagé/README_ENGINEERING_OS.md**
3. ⏱️ 15 min : **chef_projet/PLANNING.md** ← 4 semaines détail
4. ⏱️ 5 min : **chef_projet/RISQUES.md** ← Risk Register
5. ⏱️ 10 min : **chef_projet/09_Qualite_DoD.md** ← DoD criteria

**Après** :
- Lire tous les autres docs (contexte complet)
- GLOSSAIRE.md (termes métier)

**Tâches clés** :
- ✅ Gérer calendrier 4 semaines
- ✅ Tracker DoD (chaque model testé ?)
- ✅ Escalader risques
- ✅ Valider livrables chaque semaine

---

### **👥 DIRECTION / UTILISATEURS (Lecture Rapide)**

**Commencer ici** :
1. ⏱️ 3 min : **partagé/INDEX.md**
2. ⏱️ 5 min : **owner/01_Vision_Produit.md** ← Contexte
3. ⏱️ 10 min : **bi/08_Dashboard_Catalog.md** ← Ce qu'on va voir
4. ⏱️ 10 min : **partagé/GLOSSAIRE.md** ← Termes clés

**Avant go-live** :
- Training 30 min avec PO (walkthrough dashboards)

---

## 📋 Checklist : Fichiers à Télécharger (v2.0)

**✅ À télécharger maintenant (révisés)** :

```
PARTAGÉ (pour tout le monde) :
□ INDEX.md                            ✨ Résumé complet
□ README_ENGINEERING_OS.md            ✨ Guide lecture
□ SYNTHESE_REVISIONS.md               ✨ Changements v2.0
□ GLOSSAIRE.md                        ✨ Définitions métier
□ STRUCTURE_DOSSIERS.md               ✨ Ce fichier
□ MASTER_INDEX.md                     ✨ Ce que tu lis

OWNER :
□ 01_Vision_Produit.md                ✨ RÉVISÉ (français clair)
□ 02_Backlog.md                       (À créer)
□ 03_Roadmap.md                       (À créer)

ARCHITECTE :
□ 04_ADR.md                           ✨ Décisions tech
□ 05_Architecture.md                  ✨ Flux + Stack + Timeline
□ 06_Modele_Multidimensionnel.drawio  (À créer – drawio)
□ FLUX_PAIEMENT.md                    ✨ Diagrammes cash

BI :
□ 07_Dictionnaire_KPI.md              ✨ RÉVISÉ (28 KPI)
□ 08_Dashboard_Catalog.md             ✨ RÉVISÉ (5 dashboards)
□ queries/queries_utiles.sql          (À créer)
□ tests/validations.sql               (À créer)

CHEF PROJET :
□ 09_Qualite_DoD.md                   ✨ DoD criteria
□ PLANNING.md                         ✨ 4 semaines détail
□ RISQUES.md                          ✨ Risk Register
```

---

## 🚀 Workflow : Du Téléchargement au Démarrage

### **Jour 1 (Aujourd'hui)**
```
1. Télécharge les ✨ fichiers (13 fichiers totaux)
2. Crée structure dossiers (8 dossiers + dbt/)
3. Distribue les fichiers dans les bons dossiers
4. Chaque rôle lit SON dossier (ordre recommandé)
```

### **Jour 2-3 (S1J1-J2)**
```
5. Valider vision avec Direction (30 min)
6. Approuver stack tech (PostgreSQL + dbt + Metabase)
7. Setup PostgreSQL + dbt project
8. Audit DAMS data (10k lignes, cohérence)
```

### **Jour 4+ (S1J3+)**
```
9. Créer 5 fact tables dbt
10. Écrire 15+ tests dbt
11. ✅ FIN S1 : Facts OK + tests passent
```

### **S2-S4**
```
12. Créer dimensions + dashboards Metabase
13. Validation direction
14. Go-live Ven 30 Juillet
```

---

## 🎯 Rappel : Les 3 Changements Clés de v2.0

| Avant | Après |
|-------|-------|
| Jargon tech confus | ✅ Français littéral pour direction |
| ROT flou (entité ?) | ✅ ROT = rôle superviseur (dual login) |
| Pas d'objectif agents | ✅ Objectif 50 kg/jour = métrique clé |
| Dépenses boîte noire | ✅ Répartition transparente (Transport, Carburant) |
| 25 KPI | ✅ 28 KPI (+ objectif + dépenses) |

---

## 💡 Pro Tips

1. **Chaque rôle = dossier** → Pas de confusion qui lit quoi
2. **Partagé/** = source de vérité (pas de duplication)
3. **Fichiers = propriétaire clair** (header : "Owner: [Role]")
4. **Git = trace changes** (commit avec message clair)
5. **Weekly review** = Ven 16:00 (rétrospective + risques)

---

## 📞 Contacts & Support

| Question | Voir | Contact |
|----------|------|---------|
| Pourquoi on construit ça ? | owner/01_Vision_Produit.md | PO (Mahamane) |
| Comment c'est architecturé ? | architecte/05_Architecture.md | Architecte (Mahamane) |
| Quels KPI on va voir ? | bi/07_Dictionnaire_KPI.md | BI Dev (Mahamane) |
| Quand sera-ce livré ? | chef_projet/PLANNING.md | Chef Proj (Mahamane) |
| Qu'est-ce qu'un ROT ? | partagé/GLOSSAIRE.md | Tout le monde |
| Structure comment ? | STRUCTURE_DOSSIERS.md | Ce fichier |

---

## ✅ Validation Avant Démarrage

**Confirmer avec Direction** :

- [ ] Vision métier OK (10 questions) ?
- [ ] ROT = rôle superviseur (dual login) compris ?
- [ ] Objectif agents 50 kg/jour OK ?
- [ ] Dépenses par catégorie OK ?
- [ ] 5 dashboards + 28 KPI = bon scope ?
- [ ] Calendrier 4 semaines OK ?
- [ ] Stack (PostgreSQL + dbt + Metabase) OK ?

Une fois ✅ tout → **GO FULL DEVELOPMENT**

---

## 🎉 Ce Que Tu Vas Avoir à la Fin

**Fin Juillet 2026** :
```
✅ 5 Dashboards Metabase
✅ 28 KPI Actifs & Opérationnels
✅ Infrastructure BI PostgreSQL + dbt
✅ Direction capable de répondre :
   • Faisons-nous des bénéfices ?
   • Quels produits arrêter ?
   • Quel superviseur performer ?
   • Qui atteint 50 kg/jour ?
   • Où va l'argent ?
```

---

**C'est prêt. Commence ici. Bon courage ! 🚀**

---

**Version** : 2.0 (Révisé juillet 2026)  
**Fichiers** : 20 documents (13 clés + 7 à créer)  
**Durée** : 4 semaines  
**Go-Live** : 30 Juillet 2026

