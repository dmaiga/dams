# Risques – DAMS BI MVP

**Propriétaire** : Chef de Projet  
**Cadence** : Review hebdo (Ven 16:00)  
**Seuil escalade** : P1 (bloquant) → immédiat

---

## Matrice Risques

| # | Risque | Impact | Probabilité | Score | Mitigation | Owner | Status |
|---|--------|--------|------------|-------|-----------|-------|--------|
| **R1** | Données DAMS incohérentes | 🔴 Haut | 🟡 Moyen | **MOYEN** | Audit DAMS S1J1, sample 10k lignes | Architecte | 🟢 OK |
| **R2** | PostgreSQL plein | 🔴 Haut | 🟢 Faible | **FAIBLE** | Cleanup avant S4, backup quotidien | Architecte | 🟢 OK |
| **R3** | Mahamane indisponible | 🔴 Haut | 🟡 Moyen | **MOYEN** | Doc complète, support escalade PO | Chef Proj | 🟡 WATCH |
| **R4** | Requêtes dashboards `bi` trop lentes à l'échelle prod (Metabase abandonné, ADR-009 — le risque porte maintenant sur les vues dbt consommées par l'app Django) | 🟡 Moyen | 🟡 Moyen | **MOYEN** | 24/07/2026 : cause la plus visible corrigée (vues agrégées passées de `materialized: view` à `table`, recalcul au `dbt run` plutôt qu'à chaque requête) — mesure sur volumétrie proche prod et index PostgreSQL dédiés toujours pas faits (S-710, volontairement différé, cf. `chef_projet/BILAN_LIVRAISON_VS_VISION.md` §5bis) | BI Dev | 🟡 WATCH |
| **R5** | Direction rejette KPI objectif 50kg | 🟡 Moyen | 🟢 Faible | **FAIBLE** | Valider S2, ajuster si besoin | PO | 🟢 OK |
| **R6** | ROT/superviseur confond dual login | 🟡 Moyen | 🟡 Moyen | **MOYEN** | Training clair S4, glossaire distribué | Architecte | 🟡 WATCH |
| **R7** | Dépenses: données manquent catégorisées | 🟡 Moyen | 🟡 Moyen | **MOYEN** | Audit Depense table S1, valider champs | BI Dev | 🟡 WATCH |
| **R8** | Agents objectif: données jour incomplètes | 🟡 Moyen | 🟢 Faible | **FAIBLE** | Sample agents S1, handle NULLs | BI Dev | 🟢 OK |
| **R9** | Écart schéma cible vs réel (core.Vente supposé plat) | 🔴 Haut | 🟢 Résolu | **FAIBLE** | Doc corrigée 16/07 depuis input/*.dump avant tout code | Architecte | 🟢 OK |
| **R10** | fct_depenses : ambiguïté rot_id vs effectue_par_id/type_agent | 🟡 Moyen | 🟢 Résolu | **FAIBLE** | Confirmé par audit REFERENCE_TECHNIQUE_BI.md : `effectue_par_id` sans contrainte de type, exposer `type_agent` en BI | Architecte | 🟢 OK |
| **R11** | Traçabilité cash intermédiaire non modélisée (Recouvrement/VersementBancaire) | 🟢 Faible | 🟢 Faible | **FAIBLE** | Hors scope MVP, sans impact sur rentabilité nette | PO | 🟢 OK |
| **R12** | Bug de calcul solde superviseur/clôture en PRODUCTION DAMS (champs dépréciés `Depense.versement__superviseur`/`VersementBancaire.superviseur` jamais alimentés depuis bascule ROT) | 🔴 Haut | 🔴 Confirmé | **HAUT** | Hors scope BI (n'affecte pas CA/marge/salaires/dépenses agrégés) — à signaler séparément pour correction dans DAMS lui-même | Mahamane (DAMS) | 🔴 À TRAITER (hors BI) |
| **R13** | ≥5 chemins de code créent Vente/Recouvrement/DistributionAgent avec garanties transactionnelles hétérogènes, `quantite_vendue` parfois désynchronisée | 🟡 Moyen | 🟡 Moyen | **MOYEN** | Pour fct_stocks/rotation, recalculer depuis Vente (`quantite_restante_calculee`), pas depuis le champ stocké | BI Dev | 🟡 WATCH |
| **R15** | Décision assumée : ne pas toucher au PostgreSQL de **production** (LWS, ADR-001) — développement 100% sur `input/*.dump`, conteneurisé (ADR-008) pour rester portable si un déploiement serveur est décidé plus tard | 🟡 Moyen | 🟢 Accepté | **FAIBLE** | Le Sprint 4 ("déploiement production") devra être redéfini le moment venu — pas de date engagée | PO / Chef Projet | 🟢 OK |
| **R16** | Docker Desktop instable sous Windows ; le contournement WSL2 bute à son tour sur un `docker compose build` du service `dbt` anormalement lent (`uv pip install dbt-core/dbt-postgres` > 1h, probable souci réseau WSL2) | 🟢 Faible | 🟡 Moyen | **FAIBLE** | 17/07 : Metabase installé nativement sur Windows (jar OSS + Java local, port 3001 — 3000 pris par Grafana), connecté avec succès au Postgres local (`dams_dev`, schéma `bi_`). Sprint 2 débloqué sans attendre le conteneur `dbt`. Docker/conteneurisation (ADR-008) reste la cible pour un futur déploiement serveur, repris plus tard une fois le souci réseau WSL2 diagnostiqué | Mahamane | 🟢 OK |
| **R14** | `RegleSalaire.dotation_fonction` superviseur jamais appliquée (bug `type_agent='entrepot'` vs `'superviseur'`) → coût paie superviseur structurellement sous-estimé dans `Salaire` | 🟡 Moyen | 🔴 Confirmé | **MOYEN** | KPI-005/009 restent fidèles aux données stockées (source de vérité = DAMS) ; documenter comme biais connu, pas à corriger en BI | PO | 🟡 WATCH |

---

## 🔴 Risques P1 (Bloquants)

**Aucun actuellement**

---

## 🟡 Risques P2 (À Monitorer)

### **R3 : Mahamane Indisponible**
- **Impact** : Tout arrête (Mahamane = 1 personne)
- **Proba** : Moyen (maladie, urgence)
- **Mitigation** :
  - [ ] Docs SUPER claires (checklist + README complets)
  - [ ] Code dbt = propre et commenté
  - [ ] Setup GitHub + Wiki documenter
  - [ ] Escalade : PO peut supporter S2+
- **Trigger** : Si absent > 1 jour en semaine clé (S1/S4)

---

### **R4 : Requêtes dashboards `bi` lentes à l'échelle prod (> 2s)**
- **Impact** : Dashboards inutilisables (Metabase abandonné — ADR-009 ; l'app Django `bi` lit
  directement les vues dbt matérialisées en table)
- **Proba** : Moyen (pas encore mesuré sur volumétrie proche prod)
- **Mitigation** :
  - [x] Vues agrégées passées de `materialized: view` à `table` (24/07/2026) — recalcul au
    `dbt run` plutôt qu'à chaque requête dashboard
  - [ ] Tester index PostgreSQL dédiés (agent_id, superviseur_id, date)
  - [ ] Mesurer sur une volumétrie proche prod (pas seulement `dams_dev`)
  - [ ] Fallback : données pré-calculées si nécessaire
- **Trigger** : Si > 10% requêtes > 2s

---

### **R6 : ROT/Superviseur Confond Dual Login**
- **Impact** : Utilisateur perd confiance, confusion
- **Proba** : Moyen (changement de paradigme)
- **Mitigation** :
  - [ ] Documentation CRISTAL CLAIRE dans GLOSSAIRE.md
  - [ ] Training S4 (15 min, visuel)
  - [ ] Support direct Mahamane (slack réactif)
- **Trigger** : Si utilisateur confus au training S4

---

### **R7 : Dépenses Non Catégorisées**
- **Impact** : Dashboard dépenses = incomplet
- **Proba** : Moyen (données existantes = peut être sales)
- **Mitigation** :
  - [ ] Audit table Depense S1J1 (vérifier champ categorie)
  - [ ] Vérifier 100% rows ont categorie
  - [ ] Fallback : créer "Divers" pour non-classées
  - [ ] Plan correction : ROT doit catégoriser S2
- **Trigger** : Si > 5% Depense sans categorie

---

### **R10 : fct_depenses — rot_id vs effectue_par_id**

- **Impact** : KPI dépenses ROT (KPI-007/008) mal filtré si `effectue_par_id` inclut des dépenses saisies par un superviseur non-ROT
- **Proba** : Moyen (structure réelle confirmée via `input/dams_2026-07-12.dump` : `core_depense.effectue_par_id → core_agent.id`, sans colonne `rot_id` dédiée — voir [architecte/05_Architecture.md](../architecte/05_Architecture.md#note-de-traçabilité))
- **Mitigation** :
  - [ ] À l'implémentation dbt : exposer `type_agent` dans `fct_depenses` plutôt que de renommer en dur `rot_id`
  - [ ] Test `accepted_values` (severity: warn) sur `type_agent ∈ ('rot','superviseur')` pour détecter l'écart au lieu de le cacher
  - [ ] Confirmer empiriquement la répartition réelle des `type_agent` sur `core_depense.effectue_par_id`
- **Trigger** : Si le test `accepted_values` échoue en dbt

---

## 🟢 Risques P3 (Faible – Infra)

- **R1** : DAMS incohérente → Audit S1J1 déjà planné ✅
- **R2** : PostgreSQL plein → Cleanup routine + backup ✅
- **R5** : Direction rejette KPI 50kg → Validé en S2, flexible ✅
- **R8** : Données jours incomplètes → Sample agents S1 ✅
- **R9** : Écart schéma cible/réel → Corrigé dans la doc avant le code ✅
- **R11** : Traçabilité cash intermédiaire non modélisée → Hors scope MVP, assumé ✅

---

## 📋 Action Items

### **À faire S1 (Avant Ven 11 Juil)**
- [ ] **Audit DAMS** : 10k lignes Vente, nullité, cohérence (R1)
- [ ] **Vérifier table Depense** : 100% rows catégorisées ? (R7)
- [ ] **Sample agents** : Données jours complètes ? (R8)
- [ ] **Index PostgreSQL** : agent_id, superviseur_id, date (R4)

### **À faire S2 (Avant Ven 18 Juil)**
- [ ] **Valider KPI 50kg** avec Direction (R5)
- [ ] **Training ROT/dual login** prep (doc + visuel) (R6)
- [ ] **Tester requêtes Metabase** : % < 2s ? (R4)
- [ ] **Escalade Mahamane** si indisponibilité (R3)

### **À faire S3 (Avant Ven 25 Juil)**
- [ ] **Vérifier support ROT** pendant training (R6)
- [ ] **Finaliser mitigation dépenses** si besoin (R7)

### **À faire S4 (Avant Ven 30 Juil)**
- [ ] **Training users** : ROT, superviseur, direction (R6)
- [ ] **QA finale** : requêtes < 2s ? (R4)
- [ ] **Backup + recovery test** (R2)

---

## 🔄 Escalade Process

**Si risque se concrétise** — pas de réunion de triage : un seul porteur de tous les rôles, la décision est immédiate.

1. Noter le risque dans ce fichier dès qu'il apparaît (sévérité P1/P2/P3)
2. Décider : Accept / Mitigate / Escalade (vers Direction si impact business) / Pivot
3. Update ligne risque + plan d'action

---

## ✅ Validation

**Risques revisités** : Ven 11 Juil, Ven 18 Juil, Ven 25 Juil, Ven 30 Juil

**Propriétaire** : Chef de Projet  
**Status** : 🟢 MONITORED (pas de P1 actuellement)

---

**Signature** : Chef Projet  
**Date** : 2 Juillet 2026  
**Prochaine review** : Ven 11 Juil 16:00

