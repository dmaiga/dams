# ADR 001 — Migration vers des apps orientées capacité métier

**Date :** 2026-07-06
**Statut :** Actif
**Décideurs :** Mahamane Daouda Maiga

---

## Contexte

DAMS a été construit autour des **utilisateurs et des rôles** : une seule personne (Abdoulaye) occupait tous les rôles (ROT, superviseur entrepôt, réception stock, dépenses). Le système a été modélisé pour refléter cette réalité individuelle.

Quand l'équipe a grandi (Ismaël superviseur, Jean gestionnaire de stock), les rôles n'ont pas été restructurés. Le système a hérité du problème :

- Abdoulaye est le seul point d'accès pour enregistrer une réception → goulot d'étranglement.
- Les permissions sont couplées aux personnes, pas aux responsabilités.
- Ajouter un nouvel employé ou changer de rôle implique de modifier des vues et des conditions métier.
- Les workflows sont construits autour de "qui fait quoi" plutôt que "quoi se passe dans le processus".

---

## Problème

> Le logiciel représente des personnes au lieu de représenter des flux.

Conséquences directes :
- Un changement organisationnel (nouvelle recrue, changement de fonction) casse le workflow.
- Les templates et les vues mélangent identité de l'utilisateur et logique métier.
- Impossible de répondre à la question "à quelle étape du flux est-on ?" sans connaître qui est connecté.

---

## Décision

### Principe directeur

Organiser les apps Django autour des **capacités métier** (Business Capabilities), pas autour des rôles ou des utilisateurs.

Une capacité métier est un ensemble de processus stables qui répond à une question métier précise. Elle survit aux changements de personnel et d'organisation.

| Capacité métier | Question métier |
|---|---|
| `marchandise` | Que contient le stock ? Qui a reçu quoi et quand ? |
| *(futur)* `finance` | Quel est le flux de trésorerie ? |
| *(futur)* `distribution` | Qui vend quoi, à qui, à quel prix ? |

### Contrainte imposée

**Les modèles Django restent dans `core`.**

Raison : déplacer des modèles existants casse les migrations, les foreign keys et l'admin Django. Le coût de migration est élevé pour aucun gain fonctionnel immédiat.

Les nouvelles apps importent les modèles de `core` sans les posséder.

```python
# marchandise/views.py
from core.models import LotEntrepot, AffectationLotSuperviseur
```

Cette contrainte sera réévaluée si une refonte totale de la base de données est planifiée.

---

## Implémentation — App `marchandise` (première capacité déployée)

### Ce qui a changé

**Avant :**
- `reception_lot` accessible uniquement par `type_agent == 'rot'` → Abdoulaye uniquement.
- `mise_disposition_rot` dans `agents/` accessible par `gestionnaire_stock`.
- Deux étapes distinctes : Jean crée `MiseDispositionRot`, puis ROT crée `AffectationLotSuperviseur`.
- Aucune vue dédiée au gestionnaire de stock pour son propre stock central.

**Après :**
- App `marchandise/` créée avec ses propres views, forms, urls et templates.
- Jean accède à `/marchandise/` : liste du stock, détail lot, réception, affectation.
- La réception est accessible à `gestionnaire_stock` **et** `rot` (pas de régression).
- Les deux étapes (MiseDispositionRot + AffectationLotSuperviseur) sont fusionnées en une seule opération par Jean, qui fixe les prix communiqués par le superviseur.
- Les templates sont mobile-first (double layout Bootstrap).

### Structure des permissions

Les permissions ne sont plus attachées à une personne mais à une **capacité** :

```python
def _acces_stock(agent):
    return agent.est_gestionnaire_stock or agent.est_rot
```

Si demain un troisième acteur doit accéder au stock central, on ajoute une condition ici — sans toucher aux templates ni aux modèles.

### Compatibilité ascendante

- `MiseDispositionRot` est toujours créé lors d'une affectation pour conserver l'historique existant.
- `lot.quantite_disponible_rot` est maintenu pour ne pas casser les dashboards existants.
- La vue `agents/mise_disposition_rot` reste accessible (non supprimée).

---

## Conséquences

### Avantages

- Jean peut travailler depuis son propre espace sans dépendre d'Abdoulaye.
- Ajouter un nouvel acteur au stock central = une ligne dans `_acces_stock`.
- Les templates sont construits pour les besoins réels du gestionnaire de stock, pas réutilisés depuis un autre rôle.
- La logique métier est dans `marchandise/`, pas éparpillée dans `core/views.py` au milieu d'autres workflows.

### Limites acceptées

- Les modèles restent dans `core` : `marchandise` a une dépendance forte sur `core.models`.
- L'endpoint AJAX `lots_par_produit` reste dans `agents/` et est réutilisé sans déplacement.
- `MiseDispositionRot` devient redondant à terme — à nettoyer lors d'une future migration.

---

## Prochaines capacités à créer

| Capacité | Périmètre pressenti |
|---|---|
| `finance` | VersementBancaire, Depense, RecouvrementSuperviseur, PaiementFournisseur |
| `distribution` | DistributionAgent, DetailDistribution, Vente, Recouvrement |

Même principe : nouvelles apps, modèles dans `core`, permissions par capacité.
