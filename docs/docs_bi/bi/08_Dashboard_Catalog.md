# Catalog de Dashboards – DAMS BI (Version Révisée)

---

> **Implémentation (20/07/2026)** : les 5 dashboards sont rendus par l'app Django `bi`
> (templates SSR + Chart.js CDN, Metabase abandonné — `architecte/04_ADR.md` ADR-009), pas
> par un outil BI externe. Deux écarts connus par rapport à ce catalogue, dus à des colonnes
> non exposées par les vues `bi_.vw_*` existantes (hors périmètre dbt autorisé pour ce sprint,
> limité à dbt-1/dbt-2 — voir `bi/07_Dictionnaire_KPI_Technique.md`) :
> - **Dashboard 1** : KPI-006 (coût salaires %) et KPI-008 (dépenses %) ne sont pas affichés — `vw_rentabilite_globale` n'expose que les montants FCFA, pas les pourcentages, et les recalculer en Python violerait la règle « aucun ratio recalculé côté Django ».
> - **Dashboard 3, partie 2** : le graphique « répartition des dépenses par catégorie » et le KPI-702 (dépenses % du CA) ne sont pas affichés — aucune vue `bi_` n'agrège `fct_depenses` par catégorie.

## Dashboard 1 : 📊 Santé Globale 

**Audience** : La Direction  
**Quand regarder** : Chaque matin  
**Question clé** : **"Avons-nous gagné de l'argent ce mois ?"**

### Ce qu'on y voit

```
Grands chiffres en haut :
  • CA Total : 15,000,000 FCFA
  • Nos bénéfices nets : 2,500,000 FCFA ✅ 
  • Sommes croissance : +10% vs mois dernier

Courbes pour voir la tendance :
  • CA mois par mois (augmente ou diminue ?)
  • Marge mois par mois (stable ou dégradation ?)
  • Bénéfice final mois par mois (améliore-t-on ?)
  
Répartition :
  • Quel superviseur ramène le plus de CA ?
```

---

## Dashboard 2 : 💰 Rentabilité Produit

**Audience** : Manager Produit, Direction  
**Quand regarder** : Chaque semaine / deux semaines  
**Question clé** : **"Quels produits arrêter ? Lesquels développer ?"**

### Ce qu'on y voit

```
Classement des produits (du meilleur au pire) :
  Produit A : 1,500,000 FCFA marge ✅ 
  Produit B : 1,200,000 FCFA marge ✅
  Produit C : 600,000 FCFA marge ⚠️
  Produit X : -50,000 FCFA (ON PERD DESSUS) ❌

Tableau détaillé par produit :
  • Combien on l'a vendu (CA)
  • Combien ça nous a coûté (coût achat)
  • Combien on a gagné (marge)
  • Combien ça tourne vite (rotation)

Alerte :
  • ROUGE : Produits vendus à perte
  • JAUNE : Produits qui tournent lentement (du capital gelé)
```

---

## Dashboard 3 : 👥 Performance Superviseur & Dépenses

**Audience** : Direction, Manager RH, Trésorier  
**Quand regarder** : Chaque mois  
**Questions clés** : **"Quel superviseur gère bien ? Où va notre argent en dépenses ?"**

### Ce qu'on y voit

#### **PARTIE 1 : PERFORMANCE SUPERVISEUR**

```
Tableau : qui ramène quoi

Superviseur A : 
  • Chiffre d'affaires généré : 3,000,000 FCFA
  • Sa marge après coût achat : 1,500,000 FCFA
  • Ce qu'il coûte en salaires équipe : 500,000 FCFA
  • Bénéfice net : 1,000,000 FCFA ✅ 

Superviseur B : 
  • Chiffre d'affaires : 2,800,000 FCFA
  • Marge : 1,400,000 FCFA
  • Coût équipe : 600,000 FCFA
  • Bénéfice : 800,000 FCFA ✅

Superviseur D :
  • Chiffre d'affaires : 1,200,000 FCFA
  • Marge : 600,000 FCFA
  • Coût équipe : 700,000 FCFA
  • Bénéfice : NÉGATIF (-100,000) ❌ PROBLÈME
```

#### **PARTIE 2 : DÉPENSES (Le trésorier)**

```
Graphique : où va notre argent en dépenses

  Transport marchandise : 850,000 FCFA (42%) ⚠️ PLUS GROS POSTE
  Carburant : 650,000 FCFA (32%)
  Maintenance véhicules : 300,000 FCFA (15%)
  Frais opérationnels : 200,000 FCFA (10%)
  Divers : 50,000 FCFA (2%)
  
  TOTAL : 2,050,000 FCFA par mois

Alerte :
  • Dépenses = 20.5% du CA (cible : < 15%)
  • JAUNE : Transport coûte trop cher ? 
  • À investiguer : besoin de mieux encadrer les dépenses ?
```

---

## Dashboard 4 : 👤 Performance Agent vs Objectif

**Audience** : Superviseur, Manager Opérations  
**Quand regarder** : Chaque semaine  
**Question clé** : **"Qui atteint son objectif de 50 kg/jour ? Qui est à la traîne ?"**

### Ce qu'on y voit

```
Tableau : Chaque agent et son performance

Agent A : 
  • Kg vendus ce mois : 250 kg (50 kg × 5 jours travail)
  • Objectif : 50 kg/jour ✅ ATTEINT

Agent B :
  • Kg vendus : 225 kg (45 kg/jour)
  • Objectif : 50 kg/jour ✅ PRESQUE BON (90%)

Agent C :
  • Kg vendus : 175 kg (35 kg/jour)
  • Objectif : 50 kg/jour ⚠️ SOUS OBJECTIF (70%)

Agent E :
  • Kg vendus : 40 kg (8 kg/jour)
  • Objectif : 50 kg/jour ❌ TRÈS FAIBLE (16%)

Colonne : Statut Objectif
  ✅ = Atteint (>= 50 kg/jour)
  ⚠️ = Proche mais pas encore (40-50 kg/jour)
  ❌ = Sous objectif (< 40 kg/jour)
  
Graphique :
  • Qui est au-dessus de 50 kg/jour ?
  • Qui est en-dessous ?
  • Tendance : ça s'améliore ou ça décline ?
```

---

## Dashboard 5 : 📦 Stock & Fournisseur

**Audience** : Manager Produit, Finance  
**Quand regarder** : Chaque mois  
**Question clé** : **"Combien d'argent dormons-nous en stock ? Quels fournisseurs coûtent cher ?"**

### Ce qu'on y voit

```
Valeur gelée en stock :
  • Total stock maintenant : 5,000,000 FCFA
  • C'est combien de jours de CA ? 
  • Objective : < 3,000,000 FCFA

Produits qui tournent lentement :
  • Produit A : 25 jours en stock ✅ RAPIDE
  • Produit B : 35 jours en stock ✅ BON
  • Produit Z : 120 jours en stock ❌ STOCK MORT (à liquider)

Fournisseurs : qui a les bonnes conditions ?
  • Fournisseur A : marges 50% (meilleur)
  • Fournisseur B : marges 50% (bon)
  • Fournisseur C : marges 40% (faible)
  • Fournisseur D : marges 20% ❌ À INVESTIGUER (trop cher)
```

---

## Résumé : Les 5 Réponses Que Vous Aurez

| Question | Dashboard | Réponse Simple |
|----------|-----------|---------|
| **Faisons bénéfice ?** | Dashboard 1 | Voir le chiffre "Bénéfice net" en grand |
| **Quels produits arrêter ?** | Dashboard 2 | Voir les produits en ROUGE (perte) |
| **Quel superviseur gère bien ?** | Dashboard 3 | Voir le classement rentabilité |
| **Où va l'argent en dépenses ?** | Dashboard 3 (Part 2) | Voir le graphique répartition dépenses |
| **Qui atteint 50 kg/jour ?** | Dashboard 4 | Voir colonnes ✅ vs ❌ |
| **Combien dort en stock ?** | Dashboard 5 | Voir le chiffre total stock |
| **Quels fournisseurs coûtent cher ?** | Dashboard 5 | Voir marges par fournisseur |

---

## Important : Ce que Vous Allez Découvrir

**Possible 1 :** Un agent ramène beaucoup de CA mais sa marge est faible
→ Il vend au rabais ou négocie mal

**Possible 2 :** Un superviseur a beaucoup d'agents mais coût équipe > marge
→ Non rentable, à restructurer

**Possible 3 :** Un produit se vend mais on le perd dessus
→ À arrêter immédiatement

**Possible 4 :** Dépenses dépassent 15% du CA
→ Signal d'alerte, à enquêter

**Possible 5 :** Beaucoup d'agents sous 50 kg/jour
→ Besoin de mieux encadrer / motiver

---

## Format Simple

Chaque dashboard c'est :
- Des **gros chiffres** (faciles à lire)
- Des **graphiques** (voir la tendance d'un coup d'oeil)
- Des **couleurs** (🟢 bon, 🟡 alerte, 🔴 problème)
- Un **tableau détaillé** (pour approfondir)

Pas d'Excel compliqué. Pas de jargon tech. Juste les chiffres qui comptent.