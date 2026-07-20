# Glossaire DAMS BI

Définitions métier essentielles (pour éviter les confusions)

---

## 🏪 Acteurs & Rôles

### **Agent Terrain (Mamy)**
- **Définition** : Vendeur terrain qui vend directement aux clients (petit volume)
- **Objectif fixe** : 50 kg/jour minimum
- **Rémunération** : Salaire de base + Incentive (25 FCFA/kg)
- **Superviseur** : Qui l'encadre (superviseur terrain)

### **Agent Gros**
- **Définition** : Vendeur qui vend en gros (volume élevé)
- **Rémunération** : Pas de salaire fixe, commission selon volume (paliers)
- **Objectif** : Pas de KPI 50kg/jour (il vend en poids + cartons)

### **Superviseur (Entrepôt)**
- **Définition** : Manager terrain qui encadre les agents, collecte l'argent
- **Valeur technique réelle** : `Agent.type_agent = 'entrepot'` (pas `'superviseur'` — le champ base de données s'appelle `entrepot`, confirmé par [architecte/REFERENCE_TECHNIQUE_BI.md](../architecte/REFERENCE_TECHNIQUE_BI.md#1-inventaire-des-modèles)). Ce glossaire garde "superviseur" comme terme métier, mais tout code/requête doit filtrer sur `entrepot`.
- **Rôles** :
  - Recouvrir ses agents (collecter l'argent qu'ils ont vendu) — **automatique** à chaque vente comptant, pas une action séparée (voir Recouvrement ci-dessous)
  - Distribuer stock aux agents
  - Saisir le prix de vente à chaque transaction (le prix n'est **pas** pré-décidé par le ROT et communiqué — c'est une saisie manuelle obligatoire du superviseur au moment de la vente)
  - Motiver agents à dépasser 50 kg/jour
  - Remettre son argent au ROT (action **manuelle et différée**, pas automatique)
- **Rémunération** : Salaire de base + Dotation de fonction + Bonus (kg supervisés) — ⚠️ en pratique, la dotation de fonction n'est jamais appliquée en production (bug `type_agent` confirmé, voir REFERENCE_TECHNIQUE_BI §6.1.4) : le coût réel affiché peut être sous-estimé.

### **ROT (Responsable Opérations Trésorier)**
- **Définition** : Rôle porté par un agent de type `Agent.type_agent = 'rot'` — une catégorie d'agent à part entière dans la base (2 agents `rot` recensés, distincts des 4 agents `entrepot`)
- **Système "dual login"** : l'hypothèse d'une même personne physique cumulant un compte `entrepot` et un compte `rot` est plausible organisationnellement mais **non confirmée par le code/la base** (aucun champ ne relie les deux comptes) — à vérifier auprès de l'équipe si cette distinction a un impact sur l'attribution des KPI par personne
- **Rôles** :
  - Recevoir remises de tous les superviseurs (`RecouvrementSuperviseur`, manuel, différé)
  - Effectuer dépenses opérationnelles (transport, carburant, etc.) via `effectue_par`
  - Verser à la banque via `VersementBancaire.effectue_par` (le champ `VersementBancaire.superviseur` existe mais n'est plus utilisé)
- **Rémunération** : Idem superviseur

### **Direction**
- **Définition** : Décideurs stratégiques, lecteurs des dashboards
- **Questions** : Faisons-nous des bénéfices ? Quels produits arrêter ?

### **Trésorier (=ROT)**
- **Alias** : Même chose que ROT (rôle de superviseur)

---

## 💰 Concepts Financiers

### **CA (Chiffre d'Affaires)**
- **Définition** : Somme de toutes les ventes (quantité × prix_vente)
- **Exemple** : 100 kg × 5,000 FCFA/kg = 500,000 FCFA de CA
- **Formule** : `SUM(quantité × prix_vente_unitaire)`

### **Prix d'Achat**
- **Définition** : Ce qu'on paie au fournisseur par unité
- **Exemple** : Riz = 2,500 FCFA/kg (prix fournisseur)
- **Tracé dans** : Lot d'entrepôt (table LotEntrepot)

### **Prix de Vente**
- **Définition** : Ce qu'on demande au client pour vendre
- **Rôle réel** : saisie manuelle **obligatoire** par le superviseur à chaque vente (`VenteForm.prix_vente_unitaire`, sans valeur par défaut) — il n'est pas pré-décidé/communiqué en amont par le ROT ni hérité d'une distribution
- **Exemple** : Riz = 5,000 FCFA/kg (prix terrain)

### **Marge Brute**
- **Définition** : CA − Coût d'achat = l'argent qu'on garde avant payer aucun coût
- **Exemple** : 500,000 (CA) − 250,000 (coût achat) = 250,000 marge brute
- **Formule** : `SUM((prix_vente − prix_achat) × quantité)`

### **Marge %**
- **Définition** : Marge brute en pourcentage du CA
- **Cible** : 45–55% (on garde entre 45% et 55% du CA)
- **Formule** : (Marge brute / CA) × 100%

### **Salaires & Incentives**
- **Salaire de base** : Fixe mensuel (même si on vend peu)
- **Incentive** : Bonus = kg vendus × 25 FCFA (agents terrain uniquement)
- **Exemple** : Base 100k + (500 kg × 25) = 100k + 12.5k = 112.5k

### **Dépenses (ROT)**
- **Définition** : Argent dépensé pour opérations (transport, carburant, maintenance, etc.)
- **Qui décide** : ROT/Trésorier
- **Catégories** :
  - Transport marchandise
  - Carburant
  - Maintenance véhicules
  - Frais opérationnels
  - Divers
- **Cible** : < 15% du CA

### **Rentabilité Nette** ⭐ LA CLEF
- **Définition** : Le vrai bénéfice après TOUT
- **Formule** : `Marge brute − Salaires − Dépenses`
- **Exemple** : 5M (marge) − 1.2M (salaires) − 0.4M (dépenses) = 3.4M ✅ Profit
- **Vigilance** :
  - ✅ > 0 = Nous gagnons
  - ❌ < 0 = Nous perdons
  - 🎯 Cible : > 500k/mois
- ⚠️ **Biais connu** : le coût salarial des superviseurs (`Salaire.salaire_total`) exclut structurellement la dotation de fonction en production (bug applicatif confirmé, voir [architecte/REFERENCE_TECHNIQUE_BI.md §6.1.4](../architecte/REFERENCE_TECHNIQUE_BI.md)) — la rentabilité nette calculée en BI reste fidèle à ce qui est réellement payé/enregistré dans DAMS (source de vérité), mais ce chiffre peut légèrement surestimer la rentabilité réelle tant que ce bug n'est pas corrigé côté DAMS.

---

## 📊 Données & Métriques

### **Quantité Vendue (kg)**
- **Définition** : Poids total vendu (kilogrammes)
- **Important** : Mesurée en kg, pas en "unités" — mais **jamais directement le champ `quantite`** : pour un produit conditionné (carton/sac, `poids_unitaire_kg` renseigné), `quantite_en_kg = quantite × poids_unitaire_kg` ; pour un produit vendu au kg (vrac), `quantite_en_kg = quantite`. Toute agrégation de volume en BI doit répliquer cette conversion (propriété `Vente.quantite_en_kg`), pas sommer `quantite` brut.
- **Lien** : Agents objectif = 50 kg/jour

### **Objectif Agent**
- **Définition** : Chaque agent terrain doit vendre minimum 50 kg/jour
- **Calcul** : Total kg vendus / Nombre de jours travaillés
- **Alerte** :
  - ✅ > 50 kg/jour = OK
  - ⚠️ 40–50 kg/jour = Alerte (superviseur doit motiver)
  - ❌ < 40 kg/jour = Sous-performance

### **Recouvrement**
- **Définition** : Argent qu'agent remet au superviseur
- **Flow réel** : **automatique et instantané** — une ligne `Recouvrement` est créée dans la même transaction que chaque `Vente` comptant (100% des ventes actuellement), pas une remise physique différée de J+2 comme le laisse penser le terme "recouvrement"
- **Tracé dans** : Table Recouvrement (montant_recouvre, date, superviseur)
- **À ne pas confondre avec** : la remise **superviseur → ROT** (`RecouvrementSuperviseur`), qui elle reste une action manuelle et différée

### **Rotation Stock**
- **Définition** : Vitesse à laquelle on tourne le stock
- **Formule** : CA produit / Stock moyen
- **Interprétation** :
  - Ratio > 2 = Rapide ✅ (bon, capital pas gelé)
  - Ratio 0.5–2 = Normal
  - Ratio < 0.5 = Lent ⚠️ (capital gelé)

### **Stock Mort**
- **Définition** : Produit qui ne se vend plus, reste longtemps
- **Vigilance** : > 60 jours en stock = à investiguer
- **Action** : Liquider ou diminuer prix

---

## 🏪 Opérations

### **Vente**
- **Définition** : Transaction agent → client
- **Tracée dans** : Table Vente (agent_id, quantité, prix_vente_unitaire, date)
- **Types** :
  - **Vente détail** : Petit volume, agents terrain
  - **Vente gros** : Grand volume, agents gros

### **Distribution (Superviseur → Agent)**
- **Définition** : Superviseur donne stock à agent pour qu'il vende
- **Tracée dans** : Table DistributionAgent
- **Immutable** : Quantité initiale ne change pas (audit)

### **Dépense (ROT)**
- **Définition** : ROT paie pour opérations (transport, carburant, etc.)
- **Tracée dans** : Table Depense
- **Catégories** : Transport, Carburant, Maintenance, Opérationnel, Divers

### **Versement Bancaire (ROT → Banque)**
- **Définition** : ROT verse à la banque l'argent restant après dépenses
- **Tracée dans** : Table VersementBancaire
- **Montants** :
  - `montant_vente` : Argent des ventes remises
  - `montant_hors_vente` : Autre source

---

## 📍 Localités & Superviseurs

### **Superviseur A, B, C, D, etc.**
- **Définition** : Chaque superviseur gère sa zone / ses agents
- **Comparaison** : BI va comparer performance superviseur A vs B
- **Métrique clé** : Rentabilité = (Marge brute équipe) − (Salaires équipe)

### **Équipe Superviseur**
- **Définition** : Ensemble agents sous un superviseur
- **Coût** : Salaires agents + salaire superviseur lui-même

---

## 🎯 KPI Essentiels

| Acronyme | Signification |
|----------|---------------|
| **CA** | Chiffre d'Affaires |
| **KPI** | Key Performance Indicator (indicateur clé) |
| **ROT** | Responsable Opérations Trésorier |
| **DW** | Data Warehouse (entrepôt de données) |
| **ETL** | Extract-Transform-Load (processus données) |
| **BI** | Business Intelligence (analytics) |
| **S1, S2, S3, S4** | Semaine 1, 2, 3, 4 |
| **MVP** | Minimum Viable Product (version mini) |

---

## 🚨 Signaux d'Alerte (À Monitorer)

### **🔴 ROUGE (Action immédiate)**
- Produit vendu à perte (marge < 0)
- Superviseur déficitaire (coût équipe > marge)
- Dépenses > 20% du CA
- Agent objectif < 40 kg/jour

### **🟡 JAUNE (Investiguer)**
- Marge % < 40%
- Salaires > 35% du CA
- Dépenses > 15% du CA
- Agent objectif 40–50 kg/jour (limite)
- Stock en > 60 jours

### **🟢 VERT (OK)**
- Marge % 45–55%
- Salaires < 35% du CA
- Dépenses < 15% du CA
- Agent objectif > 50 kg/jour
- Stock rotation > 2

---

## 💡 Exemples Concrets

### **Scenario 1 : Superviseur rentable**
```
CA généré        : 3,000,000 FCFA
Coût achat       : 1,500,000 (50%)
──────────────────────────────
Marge brute      : 1,500,000

Salaires équipe  : 500,000
──────────────────────────────
Rentabilité      : 1,000,000 ✅ BON
```

### **Scenario 2 : Superviseur déficitaire**
```
CA généré        : 1,200,000 FCFA
Coût achat       : 600,000
──────────────────────────────
Marge brute      : 600,000

Salaires équipe  : 700,000 (TROP!)
──────────────────────────────
Rentabilité      : -100,000 ❌ PROBLÈME
```

### **Scenario 3 : Agent sous objectif**
```
Agent B vendu    : 180 kg en 5 jours
Objectif         : 50 kg/jour × 5 = 250 kg
Réalité          : 180 / 5 = 36 kg/jour
Status           : ❌ SOUS OBJECTIF (72% de l'objectif)
```

---

## ✨ À Retenir

- **Objectif agents = 50 kg/jour** (métrique clé supervision)
- **ROT = catégorie d'agent à part (`type_agent='rot'`)**, distincte de `entrepot` (superviseur) en base — le lien "même personne, dual login" n'est pas vérifiable dans les données
- **Superviseur = `type_agent='entrepot'`** dans la base, pas `'superviseur'`
- **Rentabilité nette** = CA − Coûts achat − Salaires − Dépenses
- **Marge %** doit rester 45–55% (sweet spot)
- **Dépenses** doivent rester < 15% du CA
- **Stock** ne doit pas dépasser 3M FCFA (capital gelé)

