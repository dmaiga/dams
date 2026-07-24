# Catalog de Dashboards – DAMS BI (Version Révisée)

---

> **Implémentation (20/07/2026)** : les 5 dashboards sont rendus par l'app Django `bi`
> (templates SSR + Chart.js CDN, Metabase abandonné — `architecte/04_ADR.md` ADR-009), pas
> par un outil BI externe. Les deux écarts notés dans une première itération sont comblés :
> KPI-006/008 (coût salaires %, dépenses % du CA) exposés par `vw_rentabilite_globale`, et
> KPI-701/702 (répartition des dépenses par catégorie, Dashboard Dépense) par la nouvelle vue
> `vw_depenses_categorie` — voir `07_Dictionnaire_KPI_Technique.md`.

> **Réorientation (24/07/2026)** : décision Direction de recentrer la BI sur **5 dashboards**,
> chacun porteur d'un axe de lecture métier complet (Santé Globale, Vente, Agent, Dépense,
> Fournisseur) plutôt qu'un découpage technique. La partie Superviseur (ex-Dashboard 3) est
> fusionnée dans l'axe Agent, et Dépense devient un dashboard autonome — voir
> `chef_projet/BILAN_LIVRAISON_VS_VISION.md` §3.1 et §7.

> **Clôture v1 (24/07/2026)** : ce catalogue décrit l'état réellement livré de la v1, arrêté à
> cette date (`chef_projet/BILAN_LIVRAISON_VS_VISION.md`). Les compléments identifiés (contrôle
> d'accès par rôle, cron dbt nightly, mise à jour des autres documents owner/bi) sont actés comme
> volontairement différés, pas comme des manques — voir §5bis du bilan. La mesure de performance
> (S-710) est close, voir §9 du bilan.

> **Refonte UI/UX (24/07/2026, v1.5)** : direction visuelle validée par la Direction — voir la
> maquette [maquettes/DAMS_BI_maquette_v1.html](maquettes/DAMS_BI_maquette_v1.html) et
> `sprints/SPRINT_5_UIUX_Executif.md`. Ce fichier décrit le contenu/la structure de chaque
> dashboard (toujours à jour) ; la maquette fixe le langage visuel (couleurs, typo, densité) qui
> sera appliqué par-dessus sans changer ce contenu.
>
> **Sprint 5 appliqué** : système visuel de la maquette porté sur les 5 dashboards réels
> (`bi/static/bi/dashboard.css`). Les classements/graphiques simples (produits, kilo vendu par
> équipe, kg/jour vs objectif, répartition des dépenses) sont passés en listes à barres/split-bar
> CSS natif ; seule la courbe multi-séries de Santé Globale reste en Chart.js (décision actée,
> cf. sprint). Contenu et libellés inchangés.

## Dashboard 1 : 📊 Santé Globale

**Audience** : La Direction  
**Quand regarder** : Chaque matin  
**Question clé** : **"Avons-nous gagné de l'argent ce mois ?"**

### Ce qu'on y voit

```
Grands chiffres en haut (marge brute mise en avant, priorité de cette phase — voir
chef_projet/BILAN_LIVRAISON_VS_VISION.md §3.4/§5bis) :
  • CA Total : 15,000,000 FCFA
  • Coût d'achat : 7,500,000 FCFA
  • Marge brute : 7,500,000 FCFA ✅ (carte principale)
  • Marge brute % : 50%

  Comparaison automatique : marge brute du mois/période affiché vs le mois qui précède
  immédiatement (pas "aujourd'hui - 1 mois" : suit toujours la période réellement sélectionnée).

Vue secondaire — marge nette (salaires + dépenses inclus) :
  • Dépenses, coût salaires, marge nette, marge nette %

Courbe de tendance :
  • CA, dépenses ROT, marge brute — journalier si un mois précis (ou une plage custom) est
    filtré, mensuel en vue cumulée.

Filtres :
  • Année / Mois (comme les autres dashboards)
  • Plage personnalisée Du/Au (date_debut/date_fin) — peut couvrir plusieurs mois, bascule
    alors automatiquement le graphique en grain journalier et les KPI en somme sur la plage.
```

---

## Dashboard 2 : 💰 Vente

**Audience** : Manager Produit, Direction  
**Quand regarder** : Chaque semaine / deux semaines  
**Question clé** : **"Faisons-nous du bénéfice ? D'où vient la marge ? Quels produits arrêter ?"**

C'est l'axe qui répond à la question de rentabilité : à quel prix on a vendu, comparé au prix
d'achat, produit par produit.

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

## Dashboard 3 : 👤 Agent

**Audience** : Superviseur, Manager Opérations, Direction  
**Quand regarder** : Chaque semaine  
**Questions clés** : **"Quel superviseur gère bien quoi ? Qui atteint son objectif de 50 kg/jour ?"**

Axe qui regroupe naturellement la performance de l'agent et celle du superviseur qui l'encadre —
un superviseur se lit à travers ses agents. Priorité produit (24/07/2026) : le kilo vendu par
l'équipe prime sur la rentabilité nette pour la lecture superviseur — voir
`chef_projet/BILAN_LIVRAISON_VS_VISION.md` §5bis.

### Filtres

```
Bascule Semaine / Mois (pas de "Toutes périodes" ici — jugé illisible sur ce dashboard) :
  • Mois : sélecteur Année/Mois classique, dernier mois disponible par défaut
  • Semaine : sélecteur dédié parmi les semaines ISO (lundi-dimanche) récentes disponibles

Filtre Superviseur (limite le tableau agents à une équipe)
Filtre Type d'agent (terrain / agent gros / agent polivalent)
```

### **PARTIE 1 : PERFORMANCE SUPERVISEUR / ÉQUIPE**

```
Tableau : qui ramène quoi (trié par kilo vendu, pas par rentabilité)

Colonnes : Équipe, Effectif, Kilo vendu, vs période précédente (kg), CA, Marge brute

Superviseur A :
  • Effectif : 5 agents
  • Kilo vendu : 1 200 kg — vs semaine/mois précédent : +80 kg ✅
  • CA : 3,000,000 FCFA — Marge brute : 1,500,000 FCFA

Superviseur D :
  • Effectif : 4 agents
  • Kilo vendu : 600 kg — vs période précédente : -150 kg ❌ (à surveiller)
  • CA : 1,200,000 FCFA — Marge brute : 600,000 FCFA
```

### **PARTIE 2 : PERFORMANCE AGENT vs OBJECTIF**

```
Tableau : Chaque agent et sa performance (colonnes : Agent, Superviseur, Type, Kg vendus,
Jours actifs, Jours ouvrés, Kg/jour, Statut objectif, Rentabilité — pas de colonne ratio
incentive/marge, retirée le 24/07/2026)

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

Rentabilité : au grain semaine, assimilée à la marge brute (pas d'incentive au grain
hebdomadaire, fct_salaires reste mensuel).

Graphique :
  • Qui est au-dessus de 50 kg/jour ?
  • Qui est en-dessous ?
  • Tendance : ça s'améliore ou ça décline ?
```

---

## Dashboard 4 : 🧾 Dépense

**Audience** : Direction, Trésorier  
**Quand regarder** : Chaque mois  
**Question clé** : **"Où va notre argent en dépenses ?"**

Dashboard autonome — vu et su de la Direction, pour analyser les postes de dépenses.

### Ce qu'on y voit

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

## Dashboard 5 : 📦 Fournisseur

**Audience** : Manager Produit, Finance  
**Quand regarder** : Chaque mois  
**Question clé** : **"Avec quel fournisseur trouve-t-on le meilleur deal ? Combien dort en stock ?"**

Trois cards (24/07/2026, en remplacement d'une table plate fournisseur x produit x mois jugée
illisible) : Stock par produit/fournisseur, Marge par fournisseur, Marge par produit — ces deux
dernières réagissent aux mêmes filtres Produit/Fournisseur/Période que la première.

**Réserve Direction (24/07/2026)** : cette page est en réflexion — l'agencement actuel ne
convainc pas encore totalement, conservé en l'état en attendant un arbitrage (voir
`chef_projet/BILAN_LIVRAISON_VS_VISION.md` §5bis).

### Ce qu'on y voit

```
Card 1 — Stock par produit / fournisseur :
  • Total stock maintenant : 5,000,000 FCFA (objectif < 3,000,000 FCFA)
  • Par ligne produit x fournisseur : quantité restante, valeur stock, jours en stock moyen
  • Produit Z : 120 jours en stock ❌ STOCK MORT (à liquider)

Card 2 — Marge par fournisseur (tous produits confondus) :
  • Fournisseur A : CA, marge, marge % — 50% (meilleur) ✅
  • Fournisseur D : marge % 20% ❌ À INVESTIGUER (trop cher)
  • Calibration : nombre d'ajustements de prix d'achat appliqués (bi.AjustementPrixAchat)

Card 3 — Marge par produit (tous fournisseurs confondus) :
  • Même lecture que la card fournisseur, mais agrégée par produit — répond à "ce produit
    est-il rentable, indépendamment de qui l'a fourni ?"
```

---

## Résumé : Les 5 Réponses Que Vous Aurez

| Question | Dashboard | Réponse Simple |
|----------|-----------|---------|
| **Faisons bénéfice ?** | Santé Globale | Voir le chiffre "Bénéfice net" en grand |
| **Quels produits arrêter ? D'où vient la marge ?** | Vente | Voir les produits en ROUGE (perte) |
| **Quel superviseur gère bien ? Qui atteint 50 kg/jour ?** | Agent | Voir le classement rentabilité + colonnes ✅ vs ❌ |
| **Où va l'argent en dépenses ?** | Dépense | Voir le graphique répartition dépenses |
| **Combien dort en stock ? Quels fournisseurs/produits coûtent cher ?** | Fournisseur | Voir le chiffre total stock + card marge par fournisseur + card marge par produit |

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
