# Dictionnaire des KPI – DAMS BI

---

## 🎯 KPI CRITIQUES (Dashboard 1 : Santé Globale)

> **Implémentation (17/07/2026)** : KPI-001 à KPI-009 disponibles agrégés par mois dans `bi_.vw_rentabilite_globale` (`dbt/models/marts/aggregates/vw_rentabilite_globale.sql`). Testé en local (dbt build, hors Docker) — voir [sprints/SPRINT_2_Modeles_Dashboards.md](../sprints/SPRINT_2_Modeles_Dashboards.md).
>
> **Complément (20/07/2026)** : `vw_rentabilite_globale` expose désormais aussi `salaires_pct` (KPI-006) et `depenses_pct` (KPI-008), calculés en SQL (`100.0 * cout_salaires / ca`, `100.0 * cout_depenses / ca`, `null` si `ca = 0`) — l'app Django `bi` n'a plus besoin de s'en passer, ces deux KPI sont désormais affichés sur le Dashboard 1.

### KPI-001 : Chiffre d'Affaires Total (CA)

| Attribut | Valeur |
|----------|--------|
| **Nom** | Chiffre d'Affaires Total |
| **Définition** | Somme de toutes les ventes réalisées (prix de vente × quantité) |
| **Formule** | `SUM(fct_ventes.quantite * fct_ventes.prix_vente_unitaire)` |
| **Dimension** | Global, par mois, par superviseur, par agent, par produit |
| **Fréquence** | Mensuel, hebdomadaire |
| **Unit** | FCFA |
| **Cible** | Croissance MoM > 0% |
| **Propriétaire** | Direction |
| **Source** | `fct_ventes` |

---

### KPI-002 : Coût d'Achat Total

| Attribut | Valeur |
|----------|--------|
| **Nom** | Coût d'Achat Total |
| **Définition** | Somme des coûts d'achat fournisseur pour tous les produits vendus |
| **Formule** | `SUM(fct_ventes.quantite * fct_ventes.prix_achat_unitaire)` |
| **Dimension** | Global, par mois, par fournisseur, par produit |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | < 50% du CA |
| **Propriétaire** | Direction |
| **Source** | `fct_ventes` |

---

### KPI-003 : Marge Brute

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Brute Nette |
| **Définition** | Différence entre CA et coût d'achat |
| **Formule** | `SUM(fct_ventes.quantite * (fct_ventes.prix_vente_unitaire - fct_ventes.prix_achat_unitaire))` |
| **Dimension** | Global, par mois, par superviseur, par produit |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | > 3,000,000 FCFA/mois |
| **Propriétaire** | Direction |
| **Source** | `fct_ventes` (colonne `marge_unitaire`) |

---

### KPI-004 : Marge Brute %

| Attribut | Valeur |
|----------|--------|
| **Nom** | Pourcentage Marge Brute |
| **Définition** | Marge brute divisée par CA (en %) |
| **Formule** | `(KPI-003 / KPI-001) * 100` |
| **Dimension** | Global, par mois, par superviseur, par produit |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | 45–55% |
| **Propriétaire** | Direction |
| **Source** | `fct_ventes` |

---

### KPI-005 : Coût Salaires & Incentives Total

| Attribut | Valeur |
|----------|--------|
| **Nom** | Coût Total Paie (Salaires + Incentives) |
| **Définition** | Somme de tous les salaires + incentives versés (agents + superviseurs) |
| **Formule** | `SUM(fct_salaires.salaire_base + fct_salaires.incentive)` |
| **Dimension** | Global, par mois, par superviseur, par type d'agent |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | < 1,500,000 FCFA/mois |
| **Propriétaire** | Finance |
| **Source** | `fct_salaires` |

> **Correction (dbt-1, 20/07/2026)** : `fct_salaires` excluait auparavant toute logique de
> prorata au démarrage — un agent entré en cours de période générait un coût salarial sur
> des mois antérieurs à son entrée en fonction. Corrigé en filtrant `fct_salaires` sur
> `date_debut >= agent.date_debut_fonction` (ligne exclue si antérieure). Cascade automatique
> sur KPI-006, KPI-009 (Dashboard 1) et KPI-203/204 (Dashboard 3, coût équipe et rentabilité
> superviseur). Test dbt associé : `assert_salaire_apres_date_debut_fonction`.

---

### KPI-006 : Coût Salaires %

| Attribut | Valeur |
|----------|--------|
| **Nom** | Pourcentage Salaires / CA |
| **Définition** | Coût paie en % du CA |
| **Formule** | `(KPI-005 / KPI-001) * 100` |
| **Dimension** | Global, par superviseur |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | 25–35% |
| **Propriétaire** | Finance |
| **Source** | `fct_salaires` + `fct_ventes` |

---

### KPI-007 : Coût Dépenses ROT

| Attribut | Valeur |
|----------|--------|
| **Nom** | Dépenses Operationnelles (ROT) |
| **Définition** | Somme de toutes les dépenses effectuées par le ROT |
| **Formule** | `SUM(fct_depenses.montant WHERE categorie IN (...))` |
| **Dimension** | Global, par mois, par catégorie |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | < 500,000 FCFA/mois |
| **Propriétaire** | Finance |
| **Source** | `fct_depenses` |

---

### KPI-008 : Dépenses %

| Attribut | Valeur |
|----------|--------|
| **Nom** | Pourcentage Dépenses / CA |
| **Définition** | Dépenses en % du CA |
| **Formule** | `(KPI-007 / KPI-001) * 100` |
| **Dimension** | Global |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | < 10% |
| **Propriétaire** | Finance |
| **Source** | `fct_depenses` + `fct_ventes` |

---

### KPI-009 : Rentabilité Nette

| Attribut | Valeur |
|----------|--------|
| **Nom** | Résultat Net Mensuel |
| **Définition** | Marge brute − Salaires − Dépenses |
| **Formule** | `KPI-003 - KPI-005 - KPI-007` |
| **Dimension** | Global, par mois |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | > 500,000 FCFA/mois |
| **Propriétaire** | Direction / Finance |
| **Source** | Synthèse fcts |
| **Interprétation** | ✅ > 0 = Profitable ; ❌ < 0 = Déficitaire |

---

## 📊 KPI ANALYSE PRODUIT (Dashboard 2)

> **Implémentation (17/07/2026)** : KPI-101 à KPI-106 disponibles agrégés par produit dans `bi_.vw_rentabilite_produit`. KPI-105 (rotation) utilise le stock **actuel** en proxy de stock moyen (`fct_stocks` = snapshot, pas d'historique quotidien — limite actée Sprint 1/3).

### KPI-101 : CA par Produit

| Attribut | Valeur |
|----------|--------|
| **Nom** | Chiffre d'Affaires par Produit |
| **Formule** | `SUM(fct_ventes.quantite * fct_ventes.prix_vente_unitaire) GROUP BY produit_id` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | Croissance produits clés > 10% MoM |
| **Source** | `fct_ventes` |

---

### KPI-102 : Marge Brute par Produit

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Produit |
| **Formule** | `SUM(fct_ventes.marge_unitaire) GROUP BY produit_id` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | Tous produits > 0 |
| **Vigilance** | ⚠️ Produits < 0 = déficitaires |
| **Source** | `fct_ventes` |

---

### KPI-103 : Marge % par Produit

| Attribut | Valeur |
|----------|--------|
| **Nom** | Pourcentage Marge Produit |
| **Formule** | `(SUM(marge) / SUM(ca)) * 100` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | 40–60% |
| **Source** | `fct_ventes` |

---

### KPI-104 : Quantité Vendue par Produit

| Attribut | Valeur |
|----------|--------|
| **Nom** | Volume Ventes Produit (kg ou cartons) |
| **Formule** | `SUM(fct_ventes.quantite) GROUP BY produit_id` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | kg ou cartons |
| **Source** | `fct_ventes` |

---

### KPI-105 : Rotation Stock Produit

| Attribut | Valeur |
|----------|--------|
| **Nom** | Stock Turnover |
| **Définition** | CA produit / Stock moyen |
| **Formule** | `SUM(ca_produit) / AVG(stock_value_produit)` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | Ratio |
| **Cible** | > 2 (rapide) |
| **Vigilance** | < 0.5 = stock mort |
| **Source** | `fct_ventes` + `fct_stocks` |

---

### KPI-106 : Produits Déficitaires

| Attribut | Valeur |
|----------|--------|
| **Nom** | Nombre Produits avec Marge Négative |
| **Formule** | `COUNT(DISTINCT produit_id WHERE marge < 0)` |
| **Dimension** | Global |
| **Fréquence** | Mensuel |
| **Unit** | Count |
| **Cible** | 0 |
| **Vigilance** | ⚠️ Si > 0, action immédiate requise |
| **Source** | `fct_ventes` |

---

## 👥 KPI PERFORMANCE SUPERVISEUR (Dashboard 3)

> **Implémentation (17/07/2026)** : KPI-201 à KPI-206 disponibles agrégés par superviseur (`dim_agent` filtrée `type_agent='entrepot'`) dans `bi_.vw_performance_superviseur`. CA/marge via `fct_ventes.superviseur_id` (hiérarchie au moment de la vente) ; coût équipe via `fct_salaires.superviseur_id` (hiérarchie actuelle) — divergence volontaire, voir commentaire du modèle.
>
> **Complément (20/07/2026)** : KPI-701 (répartition des dépenses par catégorie) et KPI-702 (dépenses % du CA, déjà couvert par `depenses_pct` sur `vw_rentabilite_globale`) disponibles via la nouvelle vue `bi_.vw_depenses_categorie`, grain catégorie×mois — `montant_pct` = part de la catégorie dans le total des dépenses du mois (calculé en SQL). `categorie` peut être `NULL` (21 lignes `core_depense` sans catégorie en base, écart DAMS déjà documenté dans `architecte/REFERENCE_TECHNIQUE_BI.md` §6.3.22) — affiché tel quel côté BI (« Non catégorisé »), pas masqué.

### KPI-201 : CA par Superviseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Chiffre d'Affaires Superviseur |
| **Formule** | `SUM(fct_ventes.quantite * fct_ventes.prix_vente_unitaire) GROUP BY superviseur_id` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_ventes` |

---

### KPI-202 : Marge Brute Superviseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Brute Superviseur (avant paie équipe) |
| **Formule** | `SUM(marge_unitaire) GROUP BY superviseur_id` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_ventes` |

---

### KPI-203 : Coût Paie Équipe Superviseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Coût Agents Supervisés |
| **Définition** | Salaires + incentives de tous les agents sous ce superviseur |
| **Formule** | `SUM(fct_salaires.salaire_total) WHERE superviseur_id = X` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_salaires` |

---

### KPI-204 : Rentabilité Superviseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Nette Superviseur (après paie) |
| **Formule** | `KPI-202 - KPI-203` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | > 500,000 FCFA |
| **Vigilance** | ⚠️ Négatif = superviseur non rentable |
| **Source** | Synthèse fcts |

---

### KPI-205 : Nombre Agents Actifs

| Attribut | Valeur |
|----------|--------|
| **Nom** | Effectif Agents Superviseur |
| **Formule** | `COUNT(DISTINCT agent_id WHERE superviseur_id = X)` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | Count |
| **Source** | `dim_agent` |

---

### KPI-206 : CA Moyen par Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | CA par Agent (moyenne) |
| **Formule** | `KPI-201 / KPI-205` |
| **Dimension** | Superviseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | > 500,000 FCFA/agent/mois |
| **Source** | Synthèse |

---

## 👤 KPI PERFORMANCE AGENT (Dashboard 4)

> **Implémentation (17/07/2026)** : KPI-301 à KPI-306 disponibles agrégés par agent dans `bi_.vw_performance_agent`, restreint aux types réellement soumis à l'objectif terrain (`terrain`, `agent_gros`, `agent_polivalent`). Colonne `kg_par_jour` = kg vendus / jours **distincts avec vente** (pas jours calendaires), `statut_objectif_50kg` ∈ {`atteint`, `proche`, `sous_objectif`} selon les seuils de [bi/08_Dashboard_Catalog.md](08_Dashboard_Catalog.md).

### KPI-301 : CA Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | Chiffre d'Affaires Agent |
| **Formule** | `SUM(fct_ventes.quantite * fct_ventes.prix_vente_unitaire) WHERE agent_id = X` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel, hebdomadaire |
| **Unit** | FCFA |
| **Source** | `fct_ventes` |

---

### KPI-302 : Marge Brute Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Produite par Agent |
| **Formule** | `SUM(marge_unitaire) WHERE agent_id = X` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_ventes` |

---

### KPI-303 : Incentive Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | Incentive Versée |
| **Définition** | Pour agents terrain : kg_vendus × 25 FCFA |
| **Formule** | `SUM(fct_salaires.incentive) WHERE agent_id = X` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_salaires` |

---

### KPI-304 : Rentabilité Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | Profitabilité Agent (Marge − Incentive) |
| **Formule** | `KPI-302 - KPI-303` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | > 100,000 FCFA/mois |
| **Vigilance** | ⚠️ Négatif = agent déficitaire |
| **Source** | Synthèse |

---

### KPI-305 : Ratio Incentive / Marge

| Attribut | Valeur |
|----------|--------|
| **Nom** | Poids Incentive sur Marge |
| **Formule** | `(KPI-303 / KPI-302) * 100` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | < 5% (incentive ne doit pas dépasser 5% de la marge) |
| **Vigilance** | > 10% = agent non rentable |
| **Source** | Synthèse |

---

### KPI-306 : Quantité Vendue Agent

| Attribut | Valeur |
|----------|--------|
| **Nom** | Volume Agent (kg) |
| **Formule** | `SUM(fct_ventes.quantite_en_kg) WHERE agent_id = X` |
| **Dimension** | Agent |
| **Fréquence** | Mensuel |
| **Unit** | kg |
| **Source** | `fct_ventes` |
| **⚠ Attention** | Ne PAS sommer `quantite` brut : un produit conditionné (carton/sac) est vendu en unités, pas en kg — `quantite_en_kg` applique la conversion (`quantite × poids_unitaire_kg`) déjà calculée dans `fct_ventes`. Nécessaire pour comparer correctement au seuil 50 kg/jour. Voir [architecte/REFERENCE_TECHNIQUE_BI.md §2.5](../architecte/REFERENCE_TECHNIQUE_BI.md). |

---

## 📦 KPI STOCK & FOURNISSEUR (Dashboard 5)

> **Implémentation (17/07/2026)** : KPI-401/402 disponibles par couple produit×fournisseur dans `bi_.vw_analyse_stock` (grain = snapshot lot agrégé).
>
> **Implémentation (dbt-2, 20/07/2026)** : KPI-403 à KPI-405 disponibles agrégés par fournisseur×mois dans `bi_.vw_marge_fournisseur` (`fct_ventes` + `dim_fournisseur`, grain différent de `vw_analyse_stock` — vente vs lot en stock). Metabase étant abandonné (voir `architecte/04_ADR.md`), la vue est directement consommée par l'app Django `bi`. Calibration prix d'achat : la vue expose `marge_systeme` (prix d'achat brut de `fct_ventes`) ET `marge_calibree` (corrigée par `bi.AjustementPrixAchat`, saisie admin Direction, moyenne pondérée par quantité à la clé fournisseur×mois — `fct_ventes` n'exposant pas `lot_id`, la correction ne peut pas être rattachée au lot précis malgré la saisie d'un `reference_lot` à titre de traçabilité).

### KPI-401 : Valeur Stock Total

| Attribut | Valeur |
|----------|--------|
| **Nom** | Stock Valeur Actuelle |
| **Formule** | `SUM(fct_stocks.quantite_restante * fct_stocks.prix_achat_moyen)` |
| **Dimension** | Global, par produit, par fournisseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | < 5,000,000 FCFA (capital immobilisé) |
| **Source** | `fct_stocks` |

---

### KPI-402 : Jours en Stock Moyen

| Attribut | Valeur |
|----------|--------|
| **Nom** | Days Inventory Outstanding (DIO) |
| **Formule** | `AVG(jours_en_stock)` |
| **Dimension** | Produit |
| **Fréquence** | Mensuel |
| **Unit** | Jours |
| **Cible** | 30–45 jours |
| **Vigilance** | > 60 jours = stock mort |
| **Source** | `fct_stocks` |

---

### KPI-403 : CA par Fournisseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Chiffre d'Affaires Fournisseur |
| **Formule** | `SUM(ca) GROUP BY fournisseur_id` |
| **Dimension** | Fournisseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Source** | `fct_ventes` |

---

### KPI-404 : Marge par Fournisseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Marge Fournisseur |
| **Formule** | `SUM(marge) GROUP BY fournisseur_id` |
| **Dimension** | Fournisseur |
| **Fréquence** | Mensuel |
| **Unit** | FCFA |
| **Cible** | Tous fournisseurs > 0 |
| **Source** | `fct_ventes` |

---

### KPI-405 : Marge % Fournisseur

| Attribut | Valeur |
|----------|--------|
| **Nom** | Pourcentage Marge Fournisseur |
| **Formule** | `(KPI-404 / KPI-403) * 100` |
| **Dimension** | Fournisseur |
| **Fréquence** | Mensuel |
| **Unit** | % |
| **Cible** | 45–55% |
| **Source** | `fct_ventes` |

---

## 🚨 KPI VIGILANCE (Monitoring)

### KPI-601 : Produits Déficitaires (Marge < 0)

| Attribut | Valeur |
|----------|--------|
| **Nom** | Alerte : Produits Vendus à Perte |
| **Formule** | `COUNT(DISTINCT produit) WHERE marge < 0` |
| **Action** | Si > 0, investigation immédiate |
| **Owner** | Direction |

---

### KPI-602 : Agents Déficitaires

| Attribut | Valeur |
|----------|--------|
| **Nom** | Alerte : Agents Non Rentables |
| **Formule** | `COUNT(agent) WHERE (marge - incentive) < 0` |
| **Action** | Si > 0, review contrats agents |
| **Owner** | RH / Direction |

---

### KPI-603 : Superviseurs Déficitaires

| Attribut | Valeur |
|----------|--------|
| **Nom** | Alerte : Superviseurs Non Rentables |
| **Formule** | `COUNT(superviseur) WHERE (marge_brute - coût_équipe) < 0` |
| **Action** | Si > 0, restructuration requise |
| **Owner** | Direction |

---

## 📋 Synthèse des Dimensions

| Dimension | KPI Applicables |
|-----------|-----------------|
| **Temporal** | Tous (par mois, semaine) |
| **Produit** | 101–106, 404–405 |
| **Agent** | 301–306 |
| **Superviseur** | 201–206 |
| **Fournisseur** | 403–405 |
| **Type Agent** | 005–006 (par type) |

---

## ⚙️ Calcul des Agrégations

### Exemple : Rentabilité Nette Superviseur B (Juillet)

```
Superviseur B a 5 agents (Terrain)

1. CA (fct_ventes) :
   ∑ ventes agents = 5,000,000 FCFA

2. Coût Achat :
   ∑ (quantité × prix_achat) = 2,500,000 FCFA

3. Marge Brute :
   5,000,000 - 2,500,000 = 2,500,000 FCFA

4. Salaires Équipe (fct_salaires) :
   - Agent A : 100,000 (base) + 25,000 (incentive) = 125,000
   - Agent B : 100,000 + 20,000 = 120,000
   - Agent C : 100,000 + 30,000 = 130,000
   - Agent D : 100,000 + 15,000 = 115,000
   - Agent E : 100,000 + 10,000 = 110,000
   - Superviseur B : 200,000 (base) + 50,000 (dotation) + 100,000 (bonus kg) = 350,000
   ∑ Salaires = 960,000 FCFA

5. Dépenses (si liées à cette équipe) :
   = 0 (dépenses ROT globales, non allouées)

6. Rentabilité Nette :
   2,500,000 - 960,000 = 1,540,000 FCFA ✅
```

---

## 🎯 Format des Exports

**Tous les KPI sont exportés en Excel avec :**
- Valeurs (FCFA, %, Count)
- Comparaison M-1 (variation %)
- Tendance 6 mois
- Traffic lights (🟢 OK, 🟡 Alerte, 🔴 Critique)
