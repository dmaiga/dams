# Definition of Done (DoD) – DAMS BI

Critères d'acceptation pour chaque livrabledu projet BI.

---

## Pour un **dbt Model** (Fact ou Dimension)

- ✅ Code SQL écrit et testé (au moins 50 lignes)
- ✅ Schéma défini avec types corrects (DECIMAL, INT, VARCHAR)
- ✅ Au moins 2 tests dbt : nullité + unicité (si PK)
- ✅ Commentaires documentés sur chaque colonne
- ✅ Pas de hardcoded values (utiliser variables, macros)
- ✅ Aucun secret/credential/host en dur — config via env (Twelve-Factor, [architecte/04_ADR.md#adr-007](../architecte/04_ADR.md#adr-007--conformité-twelve-factor-app))
- ✅ Nombre de lignes ≈ attendu (ex: fct_ventes ≈ 50k, dim_agent ≈ 50)
- ✅ Pas d'erreur de parsing : `dbt parse` réussit
- ✅ Git push avec message clair : "feat: add fct_ventes with 3 tests"

---

## Pour un **Dashboard Metabase**

- ✅ Au moins 5 visualisations (charts, tables, cards)
- ✅ Toutes les requêtes SQL optimisées : temps execution < 2s
- ✅ Aucun NULL anormal affiché (ou justifié)
- ✅ Couleurs cohérentes avec color system DAMS (#DA7756, #3B6EA5)
- ✅ Titres explicites : "Rentabilité Nette Superviseur (FCFA)"
- ✅ Au moins 1 filtre interactif (superviseur, période, etc.)
- ✅ Description du dashboard : 2-3 lignes du "pourquoi"
- ✅ Exportable en PDF sans artefacts de mise en page
- ✅ Partageable (permissions = lecture pour superviseurs)

---

## Pour un **KPI / Métrique**

- ✅ Définition écrite (1-2 phrases claires)
- ✅ Formule SQL testée (nombre de lignes cohérent avec attentes)
- ✅ Dimension clé identifiée (global, par produit, par agent)
- ✅ Cible / seuil documenté (ex: > 500k FCFA)
- ✅ Implémenté dans au moins 1 dashboard
- ✅ Résultats M-1 (comparaison mensuelle) OK
- ✅ Entré dans le Dictionnaire KPI

---

## Pour un **Test de Qualité Données**

- ✅ Couverture ≥ 80% des colonnes clés (fact tables)
- ✅ Tests intégrés dans dbt (`tests/`)
- ✅ Au moins 1 test par domaine :
  - Intégrité (nullité, unicité)
  - Logique métier (marge > 0, quantité > 0)
  - Cohérence (somme dimension = somme fact)
- ✅ Documentation du test : "Vérifie que marge = CA − Coût"
- ✅ Passage en CI/CD (ou run manuel `dbt test`)

---

## Pour la **Documentation dbt**

- ✅ README.md complété (project overview, setup, run instructions)
- ✅ Schéma `.yml` pour facts + dimensions (colonnes documentées)
- ✅ `dbt docs generate` exécuté sans erreur
- ✅ Lineage visible (source → staging → fact → view)
- ✅ Glossaire métier pour 5 termes clés (CA, marge, incentive, etc.)

---

## Pour l'**ETL Nuit (dbt run)**

- ✅ Exécution complète < 30 min
- ✅ Tous les models compilent sans erreur
- ✅ Tous les tests passent (`dbt test`)
- ✅ Logs archivés (`logs/` ou Slack notification)
- ✅ Alerte email si erreur (webhook dbt Cloud ou cron email)
- ✅ Schéma `bi_` vide avant run (DROP / TRUNCATE)
- ✅ Refresh matérialisé views après run

---

## Pour un **Rapport Excel**

- ✅ Structure claire : 1 feuille par dashboard / KPI
- ✅ En-têtes alignés avec Metabase (mêmes noms)
- ✅ Format FCFA pour devises (séparateur 1,234,567.89)
- ✅ Traffic lights : 🟢 OK, 🟡 Alerte, 🔴 Critique
- ✅ Formules dynamiques (référencent `bi_` views, pas hardcoded)
- ✅ Nom fichier : `DAMS_BI_[Mois]_[Année].xlsx`
- ✅ Autorisations : lecture seule pour superviseurs

---

## Pour une **Session de Validation Métier**

- ✅ Invitation : Direction + 2 superviseurs min
- ✅ Durée : 30 min (walkthrough rapide)
- ✅ Checklist :
  - "Les chiffres font-ils sens ?" ✓
  - "Y a-t-il des anomalies (produits déficitaires, etc.) ?" ✓
  - "Avez-vous des questions ?" ✓
- ✅ Notes prises + tickets créés (si changements)
- ✅ Signature approuvant les dashboards

---

## Pour la **Livraison MVP (Fin juillet)**

- ✅ **Artefacts** :
  - 5 dashboards Metabase fonctionnels
  - dbt project complet avec tests
  - Dictionnaire KPI (07_Dictionnaire_KPI.md)
  - Documentation architecture (05_Architecture.md)
  
- ✅ **Infrastructure** :
  - Schéma `bi_` en production PostgreSQL
  - ETL nuit (cron ou dbt Cloud) actif
  - Backups quotidiens (`bi_` schema dump)
  
- ✅ **Accès** :
  - Metabase URL fournie
  - Credentials distribuées (Direction, superviseurs)
  - Mode guide utilisateur optionnel activé
  
- ✅ **Formation** :
  - Walkthrough 30 min pour Direction
  - Documentation utilisateur: "Comment lire les dashboards ?"
  - Support email : Mahamane

---

## Pour la **Maintenance Post-MVP**

- ✅ **Monitoring nuit** :
  - Logs vérifiés (dbt run success/fail)
  - Alertes reçues si erreur
  
- ✅ **Requêtes ad-hoc** :
  - Répondu dans 1 jour ouvrable
  - Résultat fourni en SQL ou export
  
- ✅ **Bug fixes** :
  - Classé urgence si dashboard cassé
  - Résolu dans 24h
  
- ✅ **Améliorations** :
  - Collectées en backlog V2
  - Traitées en août/septembre

---

## Matrice de Qualité

| Critère | MVP | V1.5 | V2 |
|---------|-----|------|-----|
| Dashboards | 5 | 8 | 12 |
| KPI | 25 | 40 | 60 |
| Tests dbt | 20 | 40 | 60 |
| Refresh | Nuit | Nuit | Hourly |
| Alertes | Email | Slack | Email + SMS |
| Prévisions | Non | Non | Oui |

---

## Définitions

**Fait = Fait**
- Table de faits (fct_*) avec au moins 10k lignes
- Clés étrangères vers dimensions
- Au moins 5 colonnes de mesures

**Dimension = Dimension**
- Table de dimensions (dim_*) avec < 1k lignes
- Une clé primaire simple
- Au moins 3 colonnes descriptives

**Test = Assertif**
- Passe ou échoue (binaire)
- Exécution < 10s
- Documentation du pourquoi

**KPI = Mesure Métier**
- Agrégation d'une ou plusieurs colonnes fact
- Fréquence définie (quotidien, mensuel)
- Cible / seuil connu

---

## Checklist Finale (Avant Go-Live)

### Mahamane (Architect)
- [ ] dbt project complet compilé
- [ ] Tous les tests dbt passent
- [ ] Schéma `bi_` peuplé (> 100k rows in fct_ventes)
- [ ] Lineage généré (`dbt docs`)
- [ ] Git historique propre (commits parlants)
- [ ] README dbt à jour

### Direction (Validation Métier)
- [ ] Walkthrough dashboards OK
- [ ] Chiffres cohérents (CA, marge, rentabilité)
- [ ] Anomalies identifiées (déficitaires, etc.)
- [ ] Feedback actionnelle capturée

### Infrastructure
- [ ] PostgreSQL backups OK
- [ ] Cron job (dbt run) testée
- [ ] Metabase accessible sans erreur 500
- [ ] Permissions distribuées (read-only)

### Documentation
- [ ] Vision (01_Vision_Produit.md) ✓
- [ ] Architecture (05_Architecture.md) ✓
- [ ] KPI Dictionnaire (07_Dictionnaire_KPI.md) ✓
- [ ] Dashboard Catalog (08_Dashboard_Catalog.md) ✓

**Si toutes les cases ✅ → READY FOR PRODUCTION**

---

## Notes

- **DoD = Contrat** entre Mahamane (dev) et Direction (métier)
- **Flexible** : adaptable selon feedback métier
- **Pas parfait = OK** : MVP ≠ Production SLA
- **V2** : améliorer monitoring, alertes, prévisions
