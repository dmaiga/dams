# Dictionnaire des KPI – DAMS BI (Version Révisée)

---

> **Clôture v1 (24/07/2026)** : dashboards renommés en 5 axes métier — Santé Globale, Vente,
> Agent (fusion Superviseur + Agent), Dépense, Fournisseur (voir `bi/08_Dashboard_Catalog.md`).
> Nouveau sur le dashboard Agent : kilo vendu par équipe (priorité de lecture avant la
> rentabilité nette), comparaison vs la période précédente, bascule semaine/mois. Le ratio
> incentive/marge (KPI-non numéroté ici, cf. Technique KPI-305) n'est plus affiché. Sur le
> dashboard Fournisseur : deux vues séparées "Marge par fournisseur" et "Marge par produit"
> remplacent le tableau détaillé fournisseur x produit.

## 🎯 KPI CRITIQUES (Dashboard 1 : Santé Globale)

### KPI-001 : Chiffre d'Affaires Total (CA)
- **Nom** : Somme de tout ce qu'on a vendu ce mois
- **Formule** : Toutes les ventes × prix de vente
- **Dimension** : Global, par mois, par superviseur
- **Cible** : En croissance (chaque mois > mois précédent)
- **Propriétaire** : Direction
- **Source** : Table des ventes DAMS

---

### KPI-003 : Marge Brute
- **Nom** : Argent qu'on garde après payer les fournisseurs
- **Formule** : CA − Coût d'achat
- **Dimension** : Global, par mois
- **Cible** : > 3,000,000 FCFA/mois
- **Propriétaire** : Direction
- **Source** : Table des ventes (prix vente − prix achat)

---

### KPI-004 : Marge Brute %
- **Nom** : Pourcentage de la vente qu'on garde
- **Formule** : (Marge brute / CA) × 100%
- **Dimension** : Global
- **Cible** : 45–55% (on garde presque la moitié)
- **Propriétaire** : Direction

---

### KPI-005 : Coût Salaires & Incentives Total
- **Nom** : Somme de tous les salaires + bonus versés aux agents
- **Formule** : Salaire base + (kg vendus × 25 FCFA)
- **Dimension** : Global, par mois, par superviseur
- **Cible** : < 1,500,000 FCFA/mois
- **Propriétaire** : Finance
- **Source** : Table des salaires DAMS

---

### KPI-006 : Coût Salaires %
- **Nom** : Pourcentage des salaires par rapport au CA
- **Formule** : (Coût salaires / CA) × 100%
- **Dimension** : Global
- **Cible** : 25–35% (25% idéal, 35% max)
- **Propriétaire** : Finance

---

### KPI-007 : Coût Dépenses ROT
- **Nom** : Tout l'argent dépensé par le trésorier
- **Formule** : Transport + Carburant + Maintenance + Opérationnel + Divers
- **Dimension** : Global, par mois, par catégorie
- **Cible** : < 500,000 FCFA/mois
- **Propriétaire** : Finance
- **Source** : Table des dépenses DAMS

---

### KPI-008 : Dépenses %
- **Nom** : Pourcentage dépenses par rapport au CA
- **Formule** : (Coût dépenses / CA) × 100%
- **Dimension** : Global
- **Cible** : < 15% (plus c'est bas, mieux c'est)
- **Propriétaire** : Finance

---

### KPI-009 : Rentabilité Nette (LE KPI PRINCIPAL)
- **Nom** : Le vrai bénéfice après TOUT
- **Formule** : Marge brute − Salaires − Dépenses
- **Dimension** : Global, par mois
- **Cible** : > 500,000 FCFA/mois (positif = bonne santé)
- **Propriétaire** : Direction / Finance
- **Interprétation** :
  - ✅ > 0 = Nous gagnons de l'argent
  - ❌ < 0 = Nous perdons de l'argent
  - ⚠️ Positif mais faible = À investiguer

---

### KPI-010 : Rentabilité Nette %
- **Nom** : Le vrai bénéfice, en pourcentage du CA
- **Formule** : (Rentabilité nette / CA) × 100%
- **Dimension** : Global, par mois
- **Propriétaire** : Direction / Finance
- **Ajouté** : 23/07/2026 — section secondaire "marge nette", la marge brute (KPI-003/004) reste
  le chiffre mis en avant pour cette phase du projet

---

## 📊 KPI ANALYSE PRODUIT (Dashboard 2)

### KPI-101 : CA par Produit
- **Nom** : Combien on a vendu chaque produit
- **Formule** : SUM(quantité × prix_vente) par produit
- **Dimension** : Produit
- **Cible** : Croissance chaque mois
- **Source** : Table des ventes

---

### KPI-102 : Marge Brute par Produit
- **Nom** : Combien on gagne sur chaque produit
- **Formule** : SUM((prix_vente − prix_achat) × quantité)
- **Dimension** : Produit
- **Cible** : TOUS les produits > 0 (aucun déficitaire)
- **Vigilance** : 🚨 Si < 0 = ARRÊTER ce produit

---

### KPI-103 : Marge % par Produit
- **Nom** : Pourcentage marge par produit
- **Formule** : (Marge / CA) × 100%
- **Dimension** : Produit
- **Cible** : 40–60%

---

### KPI-105 : Rotation Stock Produit
- **Nom** : Combien de fois on tourne le stock (fast ou slow ?)
- **Formule** : CA produit / Stock moyen
- **Dimension** : Produit
- **Cible** : > 2 (rapide = bon), < 0.5 (lent = mauvais)
- **Vigilance** : Produits lents = capital gelé

---

### KPI-106 : Produits Déficitaires
- **Nom** : Nombre de produits qu'on vend à perte
- **Formule** : COUNT(produits où marge < 0)
- **Dimension** : Global
- **Cible** : 0 (ZÉRO)
- **Vigilance** : 🚨 Si > 0 = Action immédiate requise

---

## 👥 KPI PERFORMANCE SUPERVISEUR (Dashboard 3)

### KPI-201 : CA par Superviseur
- **Nom** : Chiffre d'affaires ramené par superviseur
- **Formule** : SUM(ventes agents) par superviseur
- **Dimension** : Superviseur
- **Source** : Table des ventes

---

### KPI-202 : Marge Brute Superviseur
- **Nom** : Marge qu'on gagne dans son équipe
- **Formule** : SUM((prix_vente − prix_achat) × quantité) par superviseur
- **Dimension** : Superviseur
- **Cible** : Plus élevé = mieux

---

### KPI-203 : Coût Paie Équipe Superviseur
- **Nom** : Combien coûte son équipe en salaires
- **Formule** : SUM(salaire_total agents) par superviseur
- **Dimension** : Superviseur
- **Cible** : Moins = mieux, mais pas au détriment de la performance

---

### KPI-204 : Rentabilité Superviseur
- **Nom** : Bénéfice net du superviseur (marge − coûts équipe)
- **Formule** : Marge brute − Coût paie équipe
- **Dimension** : Superviseur
- **Cible** : > 500,000 FCFA/mois
- **Vigilance** : 
  - ✅ Positif = Bon superviseur
  - ❌ Négatif = Non rentable (restructurer ?)

---

### KPI-205 : Nombre Agents Actifs
- **Nom** : Combien d'agents supervise-t-il ?
- **Formule** : COUNT(agents) par superviseur
- **Dimension** : Superviseur

---

### KPI-206 : CA Moyen par Agent
- **Nom** : En moyenne, chaque agent ramène combien ?
- **Formule** : CA superviseur / Nombre agents
- **Dimension** : Superviseur
- **Cible** : > 500,000 FCFA/agent/mois

---

### **KPI-207 : Kilo Vendu par Équipe** ⭐ NOUVEAU (24/07/2026)
- **Nom** : Combien de kilos l'équipe d'un superviseur a-t-elle vendu ?
- **Formule** : SUM(kg vendus par tous les agents du superviseur)
- **Dimension** : Superviseur, par mois ou par semaine
- **Priorité** : c'est le chiffre mis en avant sur le tableau équipe, avant la rentabilité nette
- **Affichage** : avec comparaison vs la période précédente (mois-1 ou semaine-1)

---

### **KPI-701 : Répartition Dépenses par Catégorie** ⭐ NOUVEAU
- **Nom** : Dans quoi le trésorier dépense l'argent ?
- **Formule** : Dépenses par catégorie (Transport, Carburant, Maintenance, Opérationnel, Divers)
- **Dimension** : Global, par catégorie
- **Affichage** : Graphique pie (qui voit le plus gros poste)
- **Exemple** :
  - Transport : 42% (PLUS CHER)
  - Carburant : 32%
  - Maintenance : 15%
  - Opérationnel : 10%
  - Divers : 2%
- **Question** : "Devons-nous réduire quelque part ?"

---

### **KPI-702 : Dépenses en % du CA** ⭐ NOUVEAU
- **Nom** : Quelle proportion du CA est consommée par dépenses ?
- **Formule** : (Total dépenses / CA) × 100%
- **Dimension** : Global, par mois
- **Cible** : < 15% (alerte si > 15%)
- **Vigilance** : Si > 20%, c'est un signal d'alerte majeur

---

## 👤 KPI PERFORMANCE AGENT (Dashboard 4)

### KPI-301 : CA Agent
- **Nom** : Chiffre d'affaires généré par cet agent
- **Formule** : SUM(quantité × prix_vente) par agent
- **Dimension** : Agent
- **Source** : Table des ventes

---

### KPI-302 : Marge Brute Agent
- **Nom** : Marge qu'il génère
- **Formule** : SUM((prix_vente − prix_achat) × quantité) par agent
- **Dimension** : Agent

---

### KPI-303 : Incentive Agent
- **Nom** : Bonus qu'on lui verse
- **Formule** : Kg vendus × 25 FCFA (pour agents terrain)
- **Dimension** : Agent

---

### KPI-304 : Rentabilité Agent
- **Nom** : Vaut-il ce qu'on lui paie ?
- **Formule** : Marge − Incentive
- **Dimension** : Agent
- **Vigilance** :
  - ✅ > 0 = Rentable
  - ❌ < 0 = Nous coûte plus qu'il rapporte

---

### **KPI-401 : % Agents Qui Atteignent 50 kg/jour** ⭐ NOUVEAU
- **Nom** : Combien d'agents font bien leur boulot ?
- **Formule** : COUNT(agents avec kg_total/jours >= 50) / COUNT(agents) × 100%
- **Dimension** : Global, par superviseur
- **Cible** : 100% (tous les agents doivent faire 50 kg/jour minimum)
- **Vigilance** :
  - 🟢 > 80% = OK
  - 🟡 60–80% = Alerte (besoin de motiver)
  - 🔴 < 60% = Problème sérieux
- **Exemple** :
  - Agent A : 250 kg / 5 jours = 50 kg/jour ✅
  - Agent B : 180 kg / 5 jours = 36 kg/jour ❌ (sous objectif)

---

### **KPI-402 : Agents Sous Objectif (50 kg/jour)** ⭐ NOUVEAU
- **Nom** : Nombre d'agents qui ne font pas 50 kg/jour
- **Formule** : COUNT(agents où kg_moyen_jour < 50)
- **Dimension** : Global, par superviseur
- **Cible** : 0 (ZÉRO)
- **Vigilance** : 
  - 🚨 Si > 0 = Action superviseur requise
  - Chaque agent sous objectif = perte sèche

---

### **KPI-403 : Kg Vendus par Produit et par Agent** ⭐ NOUVEAU (sprint-11, 18/08/2026)
- **Nom** : Quels produits font le volume d'un agent ?
- **Formule** : SUM(quantite_en_kg − kilo_perdu_incentive) GROUP BY agent, produit, mois
- **Dimension** : Agent x Produit x Mois — "produit" = nom du produit (pas de vraie catégorie,
  décision différée par le PO), fiche détail agent uniquement
- **Vigilance** : aucune (KPI de composition, pas de seuil vert/jaune/rouge)
- **Source** : `dbt_bi/models/marts/aggregates/vw_ventes_agent_produit.sql`

---

### **KPI-404 : Kg en Stock chez l'Agent** ⭐ NOUVEAU (sprint-11, 18/08/2026)
- **Nom** : Combien de stock l'agent a-t-il encore en main ?
- **Formule** : Quantité distribuée − ventes déjà faites − pertes déclarées, par ligne de
  distribution encore active (réplique `DetailDistribution.quantite_restante_calculee`)
- **Dimension** : Agent x Produit, fiche détail agent uniquement
- **Vigilance** : aucune pour l'instant (pas de statut "stock dormant chez l'agent" en v1 —
  piste ouverte, pas construite ce sprint)
- **Fraîcheur** : batch dbt, pas temps réel (décision produit — dashboard consulté
  hebdomadairement, cf. `docs/sprints/sprint-11.md` § Décisions actées)
- **Source** : `dbt_bi/models/marts/fct_stock_agent.sql`

---

### **KPI-405 : Incentive (calcul en direct)** ⭐ NOUVEAU (sprint-11, 18/08/2026)
- **Nom** : Combien l'agent gagne-t-il actuellement en incentive ?
- **Formule** : kg_vendus (net des pertes) × RegleSalaire.incentive_par_kg (lu en direct, jamais
  codé en dur) — calculé côté Django (`bi/views.py::dashboard_agent_detail`), pas en dbt : pas de
  drift possible avec le taux réel, disponible aux deux granularités (mois/semaine).
- **Dimension** : Agent x (mois ou semaine), fiche détail agent uniquement
- **Précision importante** (correction du 18/08/2026, après vérification de
  `paie/services/salaire_liste_service.py`) : ce calcul reproduit **exactement** ce que la vue
  Direction "liste des salaires" du module `paie` affiche déjà au quotidien —
  `SalaireListeService.get_salaires()` appelle `CalculatorSalaire.calcul_salaire_mamy(...)` en
  direct, sans jamais lire le modèle `Salaire` stocké. Il n'y a donc **pas** de "génération
  manuelle obligatoire" pour connaître un salaire — le modèle `Salaire`/
  `SalaireGenerationService` existe toujours, mais sert un usage séparé et optionnel
  (verrouiller/archiver un montant, par ex. avant versement). KPI-303 (`fct_salaires`, mensuel)
  ne reflète que les lignes verrouillées de cette façon — souvent absentes ou en retard sur les
  ventes réelles — et est affiché en complément de KPI-405, pas comme la valeur de référence.
- **Vigilance** : aucune (pas de seuil vert/jaune/rouge).
- **Sensibilité** : masquable avec CA/marge (même bouton "Masquer les données sensibles" que le
  reste de l'app).

---

### **KPI-406 : Objectif Équipe (kg/jour)** ⭐ NOUVEAU (sprint-11, 18/08/2026)
- **Nom** : L'équipe dans son ensemble tire-t-elle assez ?
- **Formule** : objectif = nb_agents_actifs × 50 kg/jour, comparé au kg/jour réel de l'équipe
  (kg_vendus équipe / jours ouvrés de la période) — dérivé de l'objectif agent (KPI-401/402), pas
  un nouveau seuil inventé
- **Dimension** : Superviseur x (mois ou semaine), fiche détail équipe uniquement
- **Vigilance** : même logique 3 paliers que le niveau agent (✅ ≥50 kg/jour/agent en moyenne,
  ⚠️ ≥40, ❌ en dessous)
- **Source** : calculé côté Django (`bi/views.py::dashboard_superviseur_detail`), à partir de
  `VwPerformanceSuperviseur(_semaine).nb_agents_actifs`/`kg_vendus`

---

### **KPI-407 : CA Moyen par Agent vs Cible** (branché le 18/08/2026)
- **Nom** : Chaque agent de l'équipe rapporte-t-il assez en moyenne ?
- **Formule** : CA équipe / nb_agents_actifs, comparé à la cible `CA_MOYEN_AGENT_CIBLE`
  (500 000 FCFA)
- **Dimension** : Superviseur x (mois ou semaine), fiche détail équipe uniquement
- **Constat** : `ca_moyen_par_agent` (mensuel) et `CA_MOYEN_AGENT_CIBLE` existaient déjà
  (`VwPerformanceSuperviseur`, `bi/constants.py`) mais n'étaient affichés/comparés nulle part
  avant ce sprint. Recalculé côté Django (`ca / nb_agents_actifs`) plutôt que lu du champ stocké,
  pour fonctionner aux deux granularités (le champ mart n'existe qu'au grain mensuel).
- **Vigilance** : `bi/constants.py::statut_ca_moyen_agent` — ✅ ≥ cible, ⚠️ en dessous, ❌ négatif
  (cas théorique)
- **Sensibilité** : masquable comme CA/marge/rentabilité.

---

## 📦 KPI STOCK & FOURNISSEUR (Dashboard 5)

### KPI-501 : Valeur Stock Total
- **Nom** : Combien d'argent dormons-nous en stock ?
- **Formule** : SUM(quantité × prix_achat_moyen)
- **Dimension** : Global, par produit
- **Cible** : < 3,000,000 FCFA (moins c'est mieux)
- **Vigilance** : > 5,000,000 FCFA = capital immobilisé excessif

---

### KPI-502 : Jours en Stock Moyen
- **Nom** : Combien de temps un produit reste avant vente ?
- **Formule** : Moyenne(jours depuis réception)
- **Dimension** : Produit
- **Cible** : 30–45 jours
- **Vigilance** :
  - 🟢 < 30 = Rapide (bon)
  - 🟡 30–60 = Normal
  - 🔴 > 60 = Lent (stock mort)

---

### KPI-503 : CA par Fournisseur
- **Nom** : Combien on achète chez chaque fournisseur ?
- **Formule** : SUM(coût_achat) par fournisseur
- **Dimension** : Fournisseur

---

### KPI-504 : Marge par Fournisseur
- **Nom** : Combien on gagne sur les produits d'un fournisseur ?
- **Formule** : SUM(marge) par fournisseur
- **Dimension** : Fournisseur
- **Vigilance** : Si < 0 = Fournisseur trop cher (arrêter)

---

### KPI-505 : Marge % Fournisseur
- **Nom** : Pourcentage marge par fournisseur
- **Formule** : (Marge / CA fournisseur) × 100%
- **Dimension** : Fournisseur
- **Cible** : 40–55% (tous les fournisseurs)
- **Vigilance** : < 30% = Fournisseur non compétitif

---

### **KPI-506 : Marge par Produit (tous fournisseurs confondus)** ⭐ NOUVEAU (24/07/2026)
- **Nom** : Ce produit est-il rentable, peu importe qui l'a fourni ?
- **Formule** : SUM(marge) par produit, tous fournisseurs additionnés
- **Dimension** : Produit
- **Remplace** : l'ancien tableau détaillé fournisseur x produit, jugé illisible

---

### **KPI-507 : Marge % par Produit (tous fournisseurs confondus)** ⭐ NOUVEAU (24/07/2026)
- **Nom** : Pourcentage marge par produit
- **Formule** : (KPI-506 / CA produit tous fournisseurs) × 100%
- **Dimension** : Produit

---

## 🚨 KPI VIGILANCE (Alertes)

### KPI-901 : Produits Déficitaires
- **Définition** : Nombre de produits où on perd de l'argent
- **Action** : ARRÊTER ces produits immédiatement

---

### KPI-902 : Agents Non Rentables
- **Définition** : Nombre d'agents où incentive > marge
- **Action** : Investiguer + discussion avec superviseur

---

### KPI-903 : Superviseurs Déficitaires
- **Définition** : Nombre de superviseurs où coût équipe > marge
- **Action** : Restructurer ou fermer

---

### KPI-904 : Dépenses Anormales
- **Définition** : Dépenses > 15% du CA
- **Action** : Audit ROT (trésorier)

---

### KPI-905 : Agents Sous Objectif
- **Définition** : Count agents avec < 50 kg/jour moyen
- **Action** : Superviseur doit motiver/former ces agents

---

## 📋 Synthèse : Les 31 KPI de la v1 (clôturée le 24/07/2026)

| Groupe | Nombre | KPI Principaux |
|--------|--------|---------|
| **Santé Globale** | 7 | CA, Marge, Salaires, Dépenses, Rentabilité (brute + nette) |
| **Produit** | 4 | CA, Marge, Rotation, Déficitaires |
| **Superviseur** | 7 + 2 | Performance, Kilo vendu par équipe, Dépenses |
| **Agent** | 4 + 2 | Performance, Objectif |
| **Stock / Fournisseur** | 7 | Valeur, Rotation, Marge fournisseur, Marge produit |
| **Alertes** | 5 | Vigilances |
| **TOTAL** | **31** | **v1 close** |

---

## ✅ Important

**Les KPI en gras ⭐ NOUVEAU** sont les ajouts successifs :
- KPI-701/702 : Dépenses par catégorie
- KPI-401/402 : Agents vs objectif 50 kg/jour
- KPI-010 (23/07/2026) : Rentabilité nette %, secondaire à la marge brute pour cette phase
- KPI-207 (24/07/2026) : Kilo vendu par équipe — priorité de lecture sur le dashboard Agent
- KPI-506/507 (24/07/2026) : Marge par produit tous fournisseurs confondus

Ces KPI changent la façon de voir la performance : on n'aura pas juste "qui vend", mais "qui
atteint l'objectif fixe de l'entreprise" — et, depuis le 24/07, "quelle équipe vend le plus de
kilos", pas seulement qui dégage la meilleure rentabilité nette.

