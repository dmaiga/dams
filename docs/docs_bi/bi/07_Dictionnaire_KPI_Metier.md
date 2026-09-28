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
- **Dimension** : Superviseur x (mois ou semaine). **Étendu le 19/08/2026** : jusque-là visible
  uniquement sur la fiche détail équipe (Partie 4), affiché aussi en vue d'ensemble sur le
  tableau "Performance superviseur" (Partie 1, `dashboard_agents.html`) — une barre par équipe,
  pour repérer en un coup d'œil quelles équipes poussent vers le seuil individuel de 50 kg/jour
  sans avoir à ouvrir chaque fiche équipe une par une.
- **Vigilance** : même logique 3 paliers que le niveau agent (✅ ≥50 kg/jour/agent en moyenne,
  ⚠️ ≥40, ❌ en dessous)
- **Source** : calculé côté Django (`bi/views.py::dashboard_superviseur_detail` et, depuis le
  19/08/2026, `dashboard_agents`), à partir de `VwPerformanceSuperviseur(_semaine)
  .nb_agents_actifs`/`kg_vendus`

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
- KPI-406 (19/08/2026) : étendu de la fiche détail équipe au tableau Partie 1 du dashboard Agent
  (une barre par équipe vs le seuil de 50 kg/jour/agent, plus besoin d'ouvrir chaque équipe)
- 19/08/2026 : Dashboard Santé Globale élargi de 4 cartes — Top 10 agents kg vendus (métrique
  sous-jacente à KPI-401/402) et marge brute (KPI-302) côte à côte, marge brute 6 derniers mois
  (tendance fixe), Top 10 produits CA (KPI-101 Dashboard 2) — pas de nouveaux codes KPI,
  réaffichage classé de métriques existantes sur le mois de référence de la période sélectionnée
- 28/09/2026 (post-v1, demande mdmaiga) : « Marge par produit » (dashboard Stock/Fournisseur,
  KPI-506/507) gagne deux colonnes — **Incentive cédée** (`Produit.taux_incentive × quantité
  vendue`, recalculée depuis `Vente` en Python, pas via `vw_marge_fournisseur` qui ne porte pas la
  quantité) et **Marge nette** (`marge − incentive cédée`) — la marge réellement disponible après
  reversement aux agents de vente. Même périmètre assumé que sur la fiche fournisseur direction
  (`direction/analyses/fournisseurs/detail.html`) : seul le taux dédié au produit est compté, pas
  le repli au kg (`RegleSalaire.incentive_par_kg`), qui dépend du type d'agent vendeur et non du
  produit — un produit sans taux dédié affiche 0 sur cette colonne. Implémenté dans
  `bi/views.py::dashboard_stock`.
- 28/09/2026 (suite, retour mdmaiga) : les 2 colonnes ajoutées ci-dessus faisaient déborder le
  tableau « Marge par produit » (scroll horizontal). Colonne « Calibration » retirée des deux
  tableaux (fournisseur et produit) — le statut (`nb_ajustements`) n'est plus une colonne texte
  mais un point de couleur (`.bi-dot`, `bi/static/bi/dashboard.css`) devant le nom, vert si
  calibré/gris sinon (`title=` au survol pour le détail). Même logique de couleur que l'ancien
  badge, sans la place occupée par le texte.
- 28/09/2026 (suite, demande mdmaiga) : même ajout **Incentive cédée / Marge nette** sur le
  dashboard Produits (`/bi/produits/`, KPI-101 à 106) — grain produit × mois cette fois (pas
  produit seul), pour matcher `VwRentabiliteProduit` ; recalculé depuis `Vente` groupée par
  `(produit_id, année, mois)` via `ExtractYear`/`ExtractMonth`, même périmètre assumé (taux dédié
  uniquement). Colonne « Marge » renommée « Marge brute » pour lever l'ambiguïté avec la nouvelle
  colonne « Marge nette ».
  **Barre « Classement des produits par marge » recolorée** : chaque barre (auparavant une seule
  couleur pleine, proportionnelle à la marge brute) est désormais scindée en 2 segments empilés —
  marge nette conservée (couleur par défaut) et incentive cédée aux agents « mamies » (`var(
  --warning)`, orange) — avec une légende au-dessus du graphe. Objectif : rendre visible en un
  coup d'œil la part de la marge de chaque produit qui part en incentive plutôt que d'être
  conservée. **Piège technique évité** : les pourcentages de largeur (`bar_pct`, `bar_pct_nette`,
  `bar_pct_incentive`) sont calculés en Python et formatés en chaîne à point décimal (`f"{x:.2f}"`)
  avant d'être injectés dans un `style="width:...%"` — les afficher via `{{ }}` sans ce formatage
  les fait passer par le rendu localisé français de Django (virgule décimale), qui casse
  silencieusement la valeur CSS (`width:99,70%` invalide, la barre reste vide sans erreur visible).
  `chart_data`/`_chart_json` de `dashboard_produits` (jamais consommé côté template, code mort)
  supprimé au passage.
- 28/09/2026 (suite, retour mdmaiga) : `/bi/produits/` n'avait **aucun filtre période dans
  l'interface** — `annee`/`mois` ne se pilotaient qu'en tapant l'URL à la main, contrairement à
  `/bi/stock/` et `/bi/sante/`. Bloc `filtre_periode` ajouté (année + mois, "Toutes périodes"),
  même gabarit que les autres dashboards. Une fois ce filtre en place, répéter le mois sur chaque
  ligne du tableau "Détail par produit" est redondant (toutes les lignes partagent le même mois dès
  qu'un filtre est actif) — colonne "Mois" retirée du tableau, la valeur reste affichée en petit
  texte gris sous le nom du produit (purement informatif, utile surtout en "Toutes périodes" où
  plusieurs mois peuvent coexister pour un même produit).
- 28/09/2026 (suite, retour mdmaiga) : graphe "Classement des produits par marge" — un
  `title=` (hover natif) sur chaque segment de la barre précise marge nette conservée / incentive
  cédée. Le montant cédé avait d'abord été affiché en clair sous la valeur de marge (deuxième
  ligne "− X cédés") en plus du hover, puis retiré le jour même sur retour mdmaiga : le total de
  marge brute suffit en lecture directe, le hover est suffisant pour le détail. Tableau « Détail
  par produit » réordonné et resserré à la
  demande de mdmaiga : **Produit, Qté vendue, Coût d'achat, CA, Marge brute, Cédée, Nette, Marge
  nette %** — colonnes « Marge % » (brute) et « Rotation stock » retirées (pas dans la liste
  demandée). « Marge nette % » est un nouveau calcul (`marge_nette / ca × 100`), distinct de
  l'ancien « Marge % » qui rapportait la marge brute au CA.
- 28/09/2026 (suite, retour mdmaiga — « le tableau n'est pas facile à lire ») : filets verticaux
  (`.bi-col-sep`, `bi/static/bi/dashboard.css`) séparant 3 blocs logiques — identité/volume,
  construction du CA (coût → CA → marge brute), puis déduction et résultat net (cédée → nette →
  %) — sans ajouter de couleur, juste un repère de lecture. Colonne « Nette » en gras (c'est le
  chiffre qui compte le plus pour la direction, plus que la marge brute qui surestime ce qui est
  réellement conservé). Badge coloré sur « Marge nette % » recalculé sur la marge **nette**
  (`statut_marge_produit(marge_nette, marge_nette_pct)`, mêmes seuils que le badge produit
  existant, qui lui reste sur la marge brute) — un produit à marge brute saine peut afficher un
  badge net différent si l'incentive en mange une grosse part, c'est le signal recherché.
- 28/09/2026 (correction de fond, retour mdmaiga) : la colonne « Incentive cédée »
  (dashboard Stock ET dashboard Produits) affichait `0` pour la plupart des produits — le
  périmètre du 28/09 (voir plus haut) ne comptait que le taux dédié au produit
  (`Produit.taux_incentive`), en excluant le repli au kilo (`RegleSalaire.incentive_par_kg`) sous
  prétexte que ce n'était "pas une donnée par produit". Faux dans les faits : la paie
  (`paie/services/salaire_calculator.py::calcul_salaire_mamy`) applique bien les deux règles à
  chaque vente, et la plupart des produits n'ont pas de taux dédié — d'où la colonne quasi-vide.
  **Corrigé** : formule complète (taux dédié si renseigné, sinon `kg × incentive_par_kg`),
  restreinte aux ventes des agents `terrain` (seuls concernés — `agent_gros` a un taux fixe au
  carton indépendant du produit, les superviseurs n'ont pas d'incentive produit). Logique
  extraite dans `core/services/incentive_service.py` (`get_incentive_par_kg_terrain()` +
  `calculer_incentive_terrain()`), partagée avec `direction/services/fournisseur_service.py`, pour
  que les 3 écrans ne divergent plus sur la formule — la duplication précédente est exactement ce
  qui a produit ce bug. **Limite assumée** : ne déduit pas les pertes
  (`Perte.kilo_perdu_incentive`), contrairement à la paie — l'incentive affichée ici est une borne
  haute légèrement optimiste, jugé acceptable pour un écran d'analyse. Vérifié sur données réelles
  (août 2026) : "ail" passe de `0` à `250` FCFA, "KG pomme de terre" de `0` à `2 250` FCFA.
- 28/09/2026 (suite, retour mdmaiga) : hover (`title=`, curseur `help`) sur la cellule « Cédée »
  du tableau « Détail par produit » (`/bi/produits/`) — affiche la formule exacte
  (`core/services/incentive_service.py::expliquer_incentive_terrain`, appelée avec les mêmes
  arguments que le calcul du montant, pour qu'elle ne puisse jamais diverger du chiffre affiché).
  Exemples réels : « 71 unité(s) vendue(s) par les mamies × 25 FCFA/unité (taux dédié au produit)
  = 1 775 FCFA » (Oignon KG) ou « 90 kg vendus par les mamies × 25 FCFA/kg (repli au kilo, pas de
  taux dédié) = 2 250 FCFA » (KG pomme de terre).
- 28/09/2026 (suite, retour mdmaiga) : le hover ci-dessus a rempli son rôle de vérification —
  mdmaiga a constaté que « KG pomme de terre » affichait 90 kg dans la formule alors que la
  colonne « Qté vendue (kg) » affiche 92, et a demandé de vérifier. **Pas un bug** : sur les 92
  unités vendues en août 2026, 90 l'ont été par des agents `terrain` et 2 par un agent
  `agent_polivalent` — seules les ventes des agents terrain génèrent cette incentive (périmètre
  confirmé plus haut), l'écart de 2 est donc attendu. Le hover est retiré (son but était de
  vérifier le calcul, pas de rester en usage courant) — `expliquer_incentive_terrain`
  (`core/services/incentive_service.py`) est retirée avec lui, aucun autre appelant.
- 28/09/2026 (correction, retour mdmaiga) : les `title=` du graphe "Classement des produits par
  marge" (segments de barre marge nette / incentive cédée) avaient été retirés à tort en même
  temps que ceux du tableau — mdmaiga ne visait que le hover du **tableau** (celui-là un test de
  vérification côté calcul) ; celui du **graphe** est un élément de lecture utile et reste en
  place. Seul le hover de la cellule « Cédée » du tableau « Détail par produit » est retiré.

Ces KPI changent la façon de voir la performance : on n'aura pas juste "qui vend", mais "qui
atteint l'objectif fixe de l'entreprise" — et, depuis le 24/07, "quelle équipe vend le plus de
kilos", pas seulement qui dégage la meilleure rentabilité nette.

