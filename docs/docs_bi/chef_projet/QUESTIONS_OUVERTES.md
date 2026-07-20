# Questions ouvertes – DAMS BI

**Propriétaire** : Chef de Projet / PO
**Cadence** : alimenté en continu pendant les revues utilisateur, tranché au fil de l'eau
**Statut** : 🆕 nouvelle · 🔎 à investiguer · 🟡 en cours · ✅ tranchée

> Contrairement à `AMELIORATIONS_DAMS.md` (limites du système DAMS lui-même) et
> `RISQUES.md` (risques projet suivis en continu), ce fichier capture les **retours à
> chaud sur les dashboards BI livrés** — remarques du 20/07/2026 lors de la première
> revue utilisateur, avant tout travail sur l'UI/UX.

---

## Q1 : Agrégations paramétrables (group by produit / agent / catégorie dépense)

**Remontée par** : Direction, 20/07/2026
**Statut** : 🆕

Le détail ligne à ligne exposé par les dashboards (produit, agent, dépense par catégorie)
est pour l'essentiel déjà disponible dans l'application DAMS elle-même (listes, filtres
existants). Ce qui manque et que la BI doit apporter en plus, c'est une **vision agrégée
paramétrable** — pouvoir regrouper (group by) selon plusieurs axes à la volée plutôt que de
ne fournir que des détails déjà consultables ailleurs.

**À clarifier avant implémentation** :
- Sur quel(s) dashboard(s) exactement (2 - Produits, 3 - Superviseurs/Dépenses, 4 - Agents) ?
- Quels axes de regroupement précis sont attendus (ex. produits par mois plutôt que par
  ligne unique all-time, dépenses par catégorie × superviseur, agents par
  type_agent × superviseur) ?
- Ces agrégations doivent-elles rester des vues dbt figées (cohérent avec la règle « aucune
  agrégation métier en Python ») ou un vrai group-by dynamique côté UI (auquel cas il faut
  discuter comment rester conforme à cette règle) ?

---

## Q2 : Dashboard 4 (Performance Agent) — filtre période inopérant + objectif à évaluer dans le temps

**Remontée par** : Direction, 20/07/2026
**Statut** : 🔎 diagnostic fait, correction à planifier

Deux remarques distinctes :

1. **Le sélecteur annee/mois semble ne rien faire sur ce dashboard.**
   Diagnostic (confirmé dans le code, `bi/views.py` et
   `dbt_bi/models/marts/aggregates/vw_performance_agent.sql`) : `vw_performance_agent` est un
   agrégat **all-time**, sans colonne `mois`/`annee` — contrairement à
   `vw_rentabilite_globale` et `vw_marge_fournisseur`. Le filtre est donc bien branché côté
   UI (il est propagé dans les liens/formulaire) mais n'a **aucun effet sur les données** de
   ce dashboard précis, faute de grain temporel dans la vue source. Ce n'est pas un bug de
   filtre, c'est un manque de dimension temporelle dans le modèle dbt.

2. **L'objectif 50 kg/jour doit se lire sur une base hebdomadaire, pas comme un verdict figé.**
   Un agent doit vendre 50 kg/jour sur ~6 jours ouvrés, soit ~300 kg/semaine. L'intention
   n'est pas de savoir si l'agent a *déjà* atteint l'objectif une fois sur toute la période,
   mais de voir **l'évolution dans le temps** (semaine par semaine, ou mois par mois) :
   progresse-t-il, régresse-t-il, est-il constant ? Le `statut_objectif_50kg` actuel
   (`atteint`/`proche`/`sous_objectif`) est une photo unique sur tout l'historique — il
   faudrait une série temporelle par agent.

**Implication technique** : nécessite une nouvelle vue dbt (ou une évolution de
`vw_performance_agent`) avec un grain temporel — semaine ou mois selon ce que la Direction
veut suivre — hors périmètre dbt-1/dbt-2 déjà livré, à qualifier comme un nouveau lot de
travail dbt.

**Filtres manquants** (indépendant du point 1/2, remontée directe) :
- Filtre par **superviseur**.
- Filtre par **type_agent**.

---

## Q3 : Dashboard 5 (Stock & Fournisseur) — vue trop détaillée, filtres manquants

**Remontée par** : Direction, 20/07/2026
**Statut** : 🆕

Le tableau stock actuel liste une ligne par couple produit × fournisseur (grain déjà agrégé
côté dbt — pas de détail par lot/date de réception dans `vw_analyse_stock`), mais l'affichage
reste trop granulaire pour une lecture rapide. Le besoin exprimé est une **vision globale par
fournisseur** — par exemple :

```
Fournisseur A : Produit A, Produit B, Produit C
Fournisseur B : Produit A, Produit B
```

sans entrer dans le détail par date de réception ou autre grain plus fin. Explicitement pas
une question de date de réception — la vue dbt actuelle ne l'expose déjà pas.

**Filtres manquants** :
- Filtre par **fournisseur**.
- Filtre par **produit**.

**À clarifier avant implémentation** : cette vision globale est-elle un simple regroupement
visuel de `vw_analyse_stock` (fournisseur → liste de produits, sans nouvelle donnée), ou
attend-on aussi une valeur agrégée par fournisseur (ex. valeur totale de stock détenue chez
ce fournisseur, tous produits confondus) ? Dans le second cas, ça rejoint Q1 (agrégation
paramétrable) plutôt qu'un simple regroupement d'affichage.

---

## Suggestions (Claude, 20/07/2026)

Remontées en marge des points ci-dessus, pas demandées explicitement — à trier/prioriser par
la Direction :

- **Accès BI limité à un seul compte (`mdmaiga`)** — garde-fou temporaire posé pendant la mise
  au point (`bi/views.py`, `bi_access_required`). À remplacer par un vrai contrôle de rôle
  (ex. `type_agent == 'direction'`, comme pour l'admin `AjustementPrixAchat`) avant tout usage
  par plusieurs personnes de la Direction.
- **Comparaison M-1 et tendance 6 mois** — prévues dans le format d'export cible du
  Dictionnaire KPI (`07_Dictionnaire_KPI_Technique.md`, section « Format des Exports ») mais
  pas encore implémentées sur aucun dashboard. Rejoint Q2 (série temporelle) : si une vue
  temporelle est construite pour les agents, la même logique (comparaison période précédente)
  a de la valeur sur Dashboard 1 (Santé Globale) et Dashboard 3 (Superviseurs).
- **Export Excel/CSV des tableaux** — cohérent avec le reste de DAMS (exports déjà présents
  côté ventes/salaires dans `direction`), absent des dashboards BI pour l'instant.
- **Dépenses « Non catégorisé »** — `vw_depenses_categorie` remonte des lignes sans catégorie
  (déjà documenté comme écart DAMS, `REFERENCE_TECHNIQUE_BI.md` §6.3.22). Sans action côté
  saisie DAMS, cette part restera invisible dans le détail par catégorie — à signaler à la
  Direction comme argument pour forcer la catégorisation à la source.
- **Recherche/tri côté tableaux** — les tableaux (produits, agents, stock) n'ont ni recherche
  ni tri cliquable ; à mesure que le volume de lignes grandit (agents, produits × fournisseurs),
  ça deviendra nécessaire indépendamment des filtres serveur demandés en Q2/Q3.
