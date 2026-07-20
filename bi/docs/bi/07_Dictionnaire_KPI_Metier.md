# Dictionnaire des KPI – DAMS BI (Version Révisée)

---

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

## 📋 Synthèse : Les 28 KPI du MVP

| Groupe | Nombre | KPI Principaux |
|--------|--------|---------|
| **Santé Globale** | 6 | CA, Marge, Salaires, Dépenses, Rentabilité |
| **Produit** | 4 | CA, Marge, Rotation, Déficitaires |
| **Superviseur** | 6 + 2 | Performance, Dépenses |
| **Agent** | 4 + 2 | Performance, Objectif |
| **Stock** | 5 | Valeur, Rotation, Fournisseurs |
| **Alertes** | 5 | Vigilances |
| **TOTAL** | **28** | **MVP Complet** |

---

## ✅ Important

**Les KPI en gras ⭐ NOUVEAU** sont les ajouts pour cette révision :
- KPI-701/702 : Dépenses par catégorie
- KPI-401/402 : Agents vs objectif 50 kg/jour

Ces KPI changent la façon de voir la performance : on n'aura pas juste "qui vend", mais "qui atteint l'objectif fixe de l'entreprise".

