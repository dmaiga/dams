# Workflow métier — état actuel

**Date :** 2026-07-11
**Statut :** Référence vivante — à mettre à jour à chaque sprint qui touche un rôle ou une permission.
**But :** fixer une structure mentale claire du métier avant de démarrer un sprint (ex. `sprint-03`), pour éviter que chaque sprint reparte d'une compréhension partielle ou divergente du workflow réel.

Ce document décrit le flux métier tel qu'il fonctionne (ou est censé fonctionner) aujourd'hui, capacité par capacité, avec les rôles qui l'exécutent. Il complète `rules/ARCHITECTURE.md` (structure technique des apps) sans le dupliquer — ici, c'est le métier ; là-bas, c'est le code.

---

## 1. Vue d'ensemble de la chaîne

```
Gestionnaire de stock (Jean)          Superviseur (entrepôt)              Finance / Direction
────────────────────────────          ───────────────────────             ───────────────────
Réception lot (stockage)      →       Réception distribution        →     Recouvrement recette
Sortie lot (déstockage)       →       Vente terrain + auto-recouvr. →     Versement bancaire
                                       Distribution legacy aux agents      Dépenses
                                       Gestion de ses agents (mami)
```

Trois capacités métier se succèdent : **marchandise** (stockage/déstockage), **vente** (distribution + ventes terrain), **finance** (recouvrement/versement/dépense — sprint 03). Voir `rules/ARCHITECTURE.md` pour le détail technique par app.

---

## 2. Gestionnaire de stock — capacité `marchandise`

**Qui :** Jean (`type_agent = gestionnaire_stock`).

**Responsabilité :** il est le seul point d'entrée et de sortie du stock central.

### Stockage — réception d'un lot

Déclenché après vérification physique du produit (pesage, remplissage des sacs). Le gestionnaire enregistre :
- le produit (crée le produit s'il est nouveau) ;
- le fournisseur (crée le fournisseur s'il est nouveau) ;
- le prix d'achat ;
- la date de réception.

### Déstockage — sortie d'un lot

Le gestionnaire de stock est responsable du stock : c'est lui qui **initie** la sortie (décaissement), pas le superviseur qui la demande a posteriori. Il renseigne :
- le superviseur qui demande la sortie du lot ;
- l'agent terrain (« mami ») qui reçoit physiquement le produit ;
- le lot et le produit concernés ;
- la date de sortie.

Résumé : *en tant que gestionnaire de stock, je gère le stockage et le déstockage.*

---

## 3. Superviseur — capacité `vente`

**Qui :** agents `type_agent = entrepot` (verbose name interne : « Superviseur »).

### Ventes terrain + auto-recouvrement

Le superviseur enregistre les ventes réalisées par ses agents. Pour chaque vente :
- type de vente (détail / gros) ;
- montant de la vente ;
- date de réalisation.

Chaque vente déclenche automatiquement un `Recouvrement` — pas de saisie manuelle séparée du recouvrement (toutes les ventes sont au comptant, cf. `rules/ARCHITECTURE.md`).

### Workflow legacy encore actif

Un ancien workflow persiste **volontairement**, pour garder le système cohérent avec l'historique : le superviseur peut recevoir du stock lui-même et le redistribuer à ses agents (cas d'exception géré par `vente.DistributionForm` — cf. `AffectationLotSuperviseur.agent_terrain_direct` non renseigné).

### Autonomie du superviseur

- Créer ses propres agents terrain (« mami »).
- Consulter le kilo vendu par ses agents sur le mois en cours.

---

## 4. Permissions élargies (superviseurs avec droits spéciaux)

> ⚠️ **Écart constaté** : il n'existe **aucun contrôle d'accès par `username` au niveau des vues**. Ce qui existe réellement, c'est un affichage **conditionné par username dans le gabarit `base.html`** (`core/templates/base.html:502` et `:509`) : le lien d'entrée vers la ressource n'apparaît dans le menu que pour cet utilisateur précis. Ce n'est pas une permission — c'est un raccourci UI. Les deux vues derrière ces liens (`liste_lots` et `liste_depenses`/`creer_depense`/`detail_depense`, toutes dans `core/views.py`) n'ont **aucun guard de rôle**, seulement `@login_required` : n'importe quel agent connecté qui atteint l'URL peut y accéder, que le lien soit dans son menu ou non.

- **Accès au stock entrepôt** : lien `liste_lots` affiché uniquement à `ismael.diawara`.
- **Réalisation de dépenses** : lien `liste_depenses` affiché uniquement à `abdoulaye.kone`.

**Recommandation d'implémentation** (cohérente avec le pattern déjà en place, cf. `rules/ARCHITECTURE.md` §"Pattern de permission par capacité" et `peut_faire_depense` du sprint-03) : ajouter un vrai guard sur ces vues (`core/views.py`), puis conditionner le lien menu sur ce même guard plutôt que sur un `username` figé — pour que le menu suive l'accès réel au lieu d'un cas particulier.

---

## 5. Rôle ROT — en cours de dépréciation

**Statut cible :** le rôle `rot` (`type_agent = rot`, verbose name « Responsable Opérations ») doit disparaître du système.

**État transitoire actuel :**
- La direction (compte admin) a une **vision en lecture seule** sur l'ensemble du système.
- Pour recouvrer le montant détenu par les superviseurs, la direction se connecte **au compte ROT** existant — logique héritée à faire migrer vers un accès direct « Direction », sans passer par un compte ROT.

Ce changement de logique (ROT → Direction) est déjà amorcé dans `sprint-03` (`finance/`) : `RecouvrementSuperviseur.rot` et `VersementBancaire.effectue_par` étendent leur `limit_choices_to` de `type_agent='rot'` à `type_agent__in=['rot', 'direction']`, pour que mdmaiga (Direction) puisse agir directement sans emprunter le compte ROT. La suppression complète du rôle `rot` (migration des données historiques, retrait du type_agent) reste un sprint futur — non traitée ici.

---

## 6. Rôle Direction

- Vision en lecture sur l'ensemble du système (dashboards direction).
- Pendant la transition décrite au §5, exécute aussi les actions aujourd'hui réservées au ROT (recouvrement superviseur) via le compte ROT.

---

## 7. Dette technique identifiée par ce document

| Écart | Détail | Action recommandée |
|---|---|---|
| Stock entrepôt et dépenses sans guard de vue | `liste_lots`, `liste_depenses`/`creer_depense`/`detail_depense` (`core/views.py`) accessibles à tout agent authentifié — seule la visibilité du lien menu est restreinte | **Priorité haute** — ajouter un vrai guard par capacité sur ces vues (ex. `agent.est_direction or agent.peut_faire_depense` pour les dépenses, cf. décision sprint-03 n°7) |
| Menu `base.html` conditionné par `username` en dur | `core/templates/base.html:502,509` — visibilité des liens Stock Entrepôt / Dépenses testée sur des usernames littéraux, pas sur un guard | Une fois le guard ajouté, conditionner le lien menu dessus plutôt que sur `username` |
| Rôle ROT toujours actif dans le code | `RecouvrementSuperviseur.rot`, `VersementBancaire.effectue_par` encore couplés à `type_agent='rot'` par défaut | Suivi par `sprint-03` (extension des permissions), dépréciation complète = sprint futur |
| Accès direction au compte ROT | Palliatif manuel (connexion au compte), pas une fonctionnalité « agir en tant que » | À remplacer par un accès direct Direction une fois §5 terminé |

---

## Historique

- 2026-07-11 — Création à partir d'une récapitulation métier de l'utilisateur, corrigée et structurée.
