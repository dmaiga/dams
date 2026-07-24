# DAMS BI – Vision Produit

## Contexte

**DAMS** gère le flux complet de nos opérations de distribution :

```
Nous achetons auprès des fournisseurs
         ↓
Les produits arrivent à l'entrepôt
         ↓
Un superviseur distribue à ses agents
         ↓
Les agents vendent sur le terrain
         ↓
Ils récupèrent l'argent
         ↓
Ils remettent au superviseur
         ↓
Le superviseur (qui joue aussi le rôle de trésorier) récupère de tous
         ↓
Il fait ses dépenses opérationnelles
         ↓
Il verse le reste à la banque
```

**Quelques règles importantes pour comprendre notre métier :**

- **Chaque agent doit vendre au minimum 50 kg par jour** (tous produits confondus). C'est son objectif fixe. S'il vend moins, il ne crée pas assez de valeur.

- **Le superviseur n'est pas qu'un collecteur.** Il doit aussi booster ses agents à dépassser les 50 kg. C'est son rôle de manager.

- **La trésorerie est une responsabilité.** Quand nous confions à un superviseur de faire les dépenses et versements, il se connecte avec un compte "trésorier". C'est la même personne, mais avec deux rôles distincts dans le système (deux comptes différents). Cela permet de tracer qui a fait quoi clairement.

- **Chaque action est tracée** : qui a vendu quoi, qui a récupéré combien d'argent, qui l'a versé à la banque, qui l'a dépensé et pour quoi.

---

**Le vrai problème** : nous avons beaucoup de données sur ce qu'on vend, mais **pas de vue claire sur ce que ça nous rapporte réellement après tous les coûts (salaires + dépenses)**.

---

> **Priorité de phase (24/07/2026, clôture v1)** : cette Vision Produit pose la rentabilité nette
> comme le chiffre le plus important à suivre à terme — cela reste l'objectif. Mais pour la v1
> livrée, la Direction a choisi de mettre en avant la **marge brute** (carte principale du
> dashboard Santé Globale, `KPI-003`), la rentabilité nette (`KPI-009`) restant affichée en
> section secondaire. C'est une décision assumée pour cette phase du projet (déterminer d'abord
> si l'activité dégage de la marge, avant de juger la rentabilité complète), pas un changement
> durable de ce que ce document définit comme objectif final. Détail dans
> `chef_projet/BILAN_LIVRAISON_VS_VISION.md` §3.4/§5bis.

---

## Le Vrai Problème

Tu dois décider chaque mois :
- **Quels produits continuer à vendre** vs lesquels arrêter ?
- **Quels superviseurs/agents développer** vs lesquels restructurer ?
- **Où perdons-nous de l'argent** malgré les ventes ?

Exemple concret :
| Dimension | Agent A | Agent B |
|-----------|---------|---------|
| **CA** | 2,500,000 | 2,500,000 |
| **Coût achat** | 1,250,000 | 1,250,000 |
| **Marge brute** | 1,250,000 | 1,250,000 |
| **Incentive (25 FCFA/kg)** | 12,500 | 12,500 |
| **Bilan** | ✅ Rentable | ✅ Rentable |
| **MAIS...** |  |  |
| Superviseur coûte | 500,000 | 500,000 |
| 4 autres agents sous lui | 4 × 50,000 | 4 × 50,000 |
| **Coût équipe réel** | **700,000** | **700,000** |
| **Rentabilité nette** | **550,000** | **550,000** |

⚠️ **Si le superviseur a 10 agents qui vendent chacun 100,000 CA mais à bas prix :**
- Marge brute = 500,000
- Coûts salaires équipe = 700,000
- **Rentabilité = -200,000** ❌ PERTE

---

## Les 10 Questions Que Vous Vous Posez

**Et auxquelles ce système doit répondre :**

### 1️⃣ **La santé financière globale**
- Avons-nous gagné de l'argent sur ce semestre ?
- Somme toute : ventes − coûts d'achat − salaires − dépenses = combien de bénéfice ?
- La tendance s'améliore mois après mois ou elle baisse ?

### 2️⃣ **Quels produits sont vraiment rentables ?**
- Lequel de nos produits rapporte de l'argent réellement ?
- Lequel on vend en-dessous du prix d'achat (on perd dessus) ?
- Lequel devrait-on arrêter de vendre car non rentable ?
- Lequel dort en stock et nous coûte du capital ?

### 3️⃣ **Quel superviseur gère bien ses agents ?**
- Qui ramène le plus d'argent ?
- Qui gère ses coûts (salaires) de façon efficace ?
- Qui a une équipe rentable ?
- Y a-t-il des superviseurs qui nous coûtent plus qu'ils ne rapportent ?

### 4️⃣ **Qui vend vraiment ? Qui ne fait pas son travail ?**
- Quels agents atteignent l'objectif de 50 kg/jour ?
- Quels agents ne font que 30 kg ou 20 kg (sous-performance) ?
- Qui génère du CA mais avec une marge faible (vend au rabais) ?
- Qui met trop de salaire/incentive pour peu de ventes ?

### 5️⃣ **Quels fournisseurs nous proposent les meilleures conditions ?**
- Chez quel fournisseur on a les meilleures marges ?
- Chez quel fournisseur on paye trop cher (tue nos marges) ?

### 6️⃣ **Combien d'argent on a "gelé" en stock ?**
- Quelle valeur totale dort en entrepôt maintenant ?
- Quels produits restent trop longtemps (mois) sans être vendus ?
- Quels produits se vendent vite (bonne rotation) ?

### 7️⃣ **Où va notre argent en dépenses ?**
- Quelles sont nos plus grandes catégories de dépenses ?
- Transport ? Carburant ? Maintenance ? Autre ?
- Quel pourcentage de nos ventes est consommé par les dépenses ?
- Somme-nous trop généreux quelque part ?

### 8️⃣ **Quelles anomalies cachées se produisent ?**
- Y a-t-il des produits vendus à perte (prix vente < prix achat) ?
- Y a-t-il des superviseurs ou agents qui nous coûtent plus qu'ils ne rapportent ?
- Y a-t-il des gaspillages d'argent ou des inefficacités ?

### 9️⃣ **Comment avons-nous performé en janvier vs juin ?**
- Le CA augmente ou diminue mois après mois ?
- La marge s'améliore ou se détériore ?
- Sommes-nous en train de nous améliorer ?

### 🔟 **Qui dépense vraiment et pour quoi ?**
- Le trésorier (superviseur-ROT) fait combien de dépenses par mois ?
- Pour quelles catégories (transport, carburant, maintenance) ?
- Pouvons-nous réduire quelque part ?

---

## Vigilances Importantes

**Avant de valider les tableaux de bord, voilà ce qu'il faut savoir :**

- **Si un agent vend 40 kg/jour au lieu de 50 kg** → il ne crée pas assez de valeur. On paie son salaire mais son rendement est faible. À monitorer chaque jour.

- **Si un superviseur a beaucoup d'agents sous-performant** → son équipe n'est pas assez motivée ou encadrée. C'est sa responsabilité de les booster.

- **Si nos dépenses dépassent 15% du CA mensuel** → c'est un signal d'alerte. Quelque chose consomme trop.

- **Si un produit se vend moins de 50 kg en un mois** → c'est un produit mort en stock. À examiner.

- **Si un superviseur en tant que trésorier fait énormément de dépenses** → à investiguer (justification ? inefficacité ?).

---

## MVP – Scope

**Période d'analyse** : 01/01/2026 – 30/06/2026 (période figée)

**Couverture data** :
- ✅ Ventes (agent, superviseur, produit, fournisseur, quantité, prix)
- ✅ Coûts achat (par lot, par fournisseur)
- ✅ Salaires & incentives (agents terrain, gros, superviseurs)
- ✅ Dépenses ROT (catégories)
- ✅ Stocks (quantité, valeur)
- ⚠️ Rabais superviseurs (trackés implicitement via écart prix_fixe vs prix_vente)
- ⚠️ Paiements fournisseurs (lecture, pas d'analyse dette)

**Artefacts livrés** :
- 1 datawarehouse PostgreSQL (schéma en étoile)
- 5 dashboards analytiques (Superset / Metabase)
- Dictionnaire KPI (formules + définitions)
- Export Excel mensuel automatisé

---

## KPIs Critiques (MVP)

| KPI | Formule | Fréq. | Owner |
|-----|---------|-------|-------|
| **Marge brute nette** | ∑(CA) − ∑(coût_achat) | Mensuel | Direction |
| **Rentabilité nette** | Marge − Salaires − Dépenses | Mensuel | Direction |
| **Marge brute %** | (CA − coût_achat) / CA × 100 | Par produit | BI |
| **Coût salaire %** | ∑(Salaires + incentives) / CA × 100 | Par superviseur | BI |
| **Incentive vs Marge** | Incentive / Marge brute × 100 | Par agent | BI |
| **CA par agent** | ∑(Ventes par agent) | Par agent | BI |
| **Rotation stock** | CA / Stock moyen | Par produit | BI |
| **Agents déficitaires** | Count(agents où incentive > marge) | Mensuel | Direction |
| **Produits déficitaires** | Count(produits où marge < 0) | Mensuel | BI |
| **Dépenses ROT %** | ∑(Dépenses) / ∑(Cash superviseur) × 100 | Mensuel | Finance |

---

## Hors MVP (V2 / V3)

- 🚫 **Assistant BI conversationnel** (RAG + LLM)
- 🚫 **Alertes automatiques** (vente en-dessous prix achat, etc.)
- 🚫 **Prévisions de ventes** (time series / ML)
- 🚫 **Recommandations produit** (quoi commander next ?)
- 🚫 **Analyse dettes clients** (crédit)
- 🚫 **Périodes calendaires flexibles** (V2 : analyse multi-périodes)

---

## Personas & Cas d'Usage

### 👨‍💼 **Directeur**
- **Besoin** : "Faisons-nous des bénéfices ce mois ?"
- **Dashboard** : Vue globale (santé, tendance)
- **Fréquence** : Hebdomadaire

### 📊 **Manager Produit**
- **Besoin** : "Quels produits arrêter ? Lesquels développer ?"
- **Dashboard** : Rentabilité produit (marge, rotation, coûts)
- **Fréquence** : Bihebdomadaire

### 👥 **Manager RH/Opérations**
- **Besoin** : "Quel superviseur est performant ?"
- **Dashboard** : Performance superviseur (CA, marge, coûts équipe)
- **Fréquence** : Mensuel (paie)

### 🏪 **Superviseur** (optionnel)
- **Besoin** : "Comment mes agents performent ?"
- **Dashboard** : Analyse agents (CA, incentive, profitabilité)
- **Fréquence** : Hebdomadaire

---

## Succès = ?

- ✅ 5 dashboards opérationnels
- ✅ Capacité à identifier les produits à faible valeur ajoutée (marge faible ou déficitaires)
- ✅ Capacité à identifier les agents peu prolifiques (CA faible comparé à leur salaire + incentive)
- ✅ Capacité à identifier les superviseurs à restructurer (équipe qui coûte plus qu'elle ne rapporte)
- ✅ Réduction coûts non-productifs (dépenses ROT clarifiées)
- ✅ Data team  capable de répondre à 80% des questions métier en < 5 min
