# Sprint 13 — Corrections administratives auditées (Lot, Distribution, Vente)

**Statut** : ✅ terminé (15/09/2026) — les 3 corrections (Lot, Distribution, Vente),
le journal d'audit générique, la section Admin du menu et les tests sont livrés.
Suite complète (`python manage.py test`) verte : 101 tests.

---

## Contexte

mdmaiga (Direction) intervient régulièrement, aujourd'hui via le Django admin, pour corriger des
erreurs de saisie remontées par le terrain :

1. **Complaisance/erreur du gestionnaire de stock à la création d'un lot** — quantité ou prix
   d'achat erroné saisi à la réception (`LotEntrepot`).
2. **Erreur de distribution** — le gestionnaire de stock se trompe d'agent, de produit, de
   quantité, ou de superviseur en affectant/distribuant du stock.
3. **Erreur de prix de vente** — confusion fréquente entre produit conditionné (prix au sac,
   ex. sac de 25 kg) et produit vrac (prix au kilo) : un superviseur indique parfois 800 FCFA au
   lieu de 20 000 FCFA pour un sac. `Vente.prix_vente_unitaire` et/ou `Vente.quantite` sont en
   cause.

Ces corrections se font aujourd'hui **sans trace** : pas de qui, pas de quand, pas d'avant/après,
pas de motif. mdmaiga veut un mécanisme dans l'application elle-même, auditable, qui répercute
correctement chaque correction sur les modèles en aval (effet domino), et réservé à son seul
compte (`mdmaiga`) — sur le modèle déjà en place pour la réaffectation de portefeuille.

---

## Constat 1 — Ce qui existe déjà (réutilisable)

### 1.1 — Accès "Direction unique" (`mdmaiga`)

Pattern déjà en place, à réutiliser tel quel :

```python
# direction/views.py:1500-1501
def _acces_reaffectation(user):
    return user.is_authenticated and user.username == "mdmaiga"
```

appliqué via `@login_required` + `@user_passes_test(...)`, et lien de menu masqué pour les autres
utilisateurs dans `direction/templates/base_admin.html:129` et `:221` (`{% if
request.user.username == "mdmaiga" %}`).

### 1.2 — Service de correction en cascade (le squelette à copier)

`marchandise/services.py::AffectationLotService.corriger_affectation()` corrige déjà
`AffectationLotSuperviseur` (quantité, date) et répercute en cascade, dans un
`transaction.atomic()` + `select_for_update()` :

- `LotEntrepot.quantite_restante`
- `AffectationLotSuperviseur.quantite_restante`
- `DistributionAgent` / `DetailDistribution` (si distribution directe)

avec garde-fous (refuse un stock négatif, refuse de descendre sous une quantité déjà vendue). Ce
service est le patron fonctionnel des deux nouveaux services de ce sprint.

### 1.3 — Journal d'audit existant, mais limité

`core/models.py:1620` `JournalModificationDistribution` (utilisateur, type_action,
anciennes_valeurs/nouvelles_valeurs en JSON, date) — câblé uniquement sur `DistributionAgent`
(réaffectation, suppression/restauration de distribution). Rien d'équivalent pour `LotEntrepot`,
`Vente`, `Recouvrement`.

### 1.4 — Calculs dynamiques en aval (pas de resynchronisation nécessaire)

- `Fournisseur.dette_contractuelle` est une `@property` calculée à la volée depuis
  `LotEntrepot` — se corrige automatiquement si on corrige un lot.
- `finance.services.solde_superviseur()` est calculé dynamiquement à chaque appel (somme de
  `Recouvrement`, jamais de solde stocké) — se corrige automatiquement dès que
  `Recouvrement.montant_recouvre` est à jour.

### 1.5 — Réalité terrain du recouvrement (pas de garde à ajouter)

Le recouvrement de la recette superviseur et le versement bancaire réel sont assurés par un agent
dédié, avec suivi croisé sur un groupe WhatsApp — **pas** par la direction dans DAMS aujourd'hui.
Une correction de `Vente` après coup n'a donc pas besoin de bloquer ou d'avertir si l'argent a
déjà été remis physiquement : la réconciliation réelle se fait hors système. Décision mdmaiga
(15/09/2026) — voir mémoire `project_reconciliation_recouvrement_terrain`.

---

## Décisions (mdmaiga)

1. ✅ **Journal d'audit générique** plutôt que trois journaux dédiés par modèle
   (`GenericForeignKey` sur `ContentType`) — un seul écran d'historique, `motif` obligatoire à
   chaque correction.
2. ✅ **Emplacement des services** : `direction/services/` (comme la réaffectation), pas de
   nouvelle app "corrections" — cette fonctionnalité est un pouvoir de gouvernance à un seul
   utilisateur nommé, pas une capacité métier au sens de `rules/ARCHITECTURE.md`.
3. ✅ **Correction Vente** : deux champs (`prix_vente_unitaire`, `quantite`), une seule cascade
   (`Recouvrement.montant_recouvre`), **aucune garde** liée à un recouvrement déjà effectué (voir
   Constat 1.5).
4. ✅ **Menu** : nouvelle section "Admin" dans `base_admin.html`, regroupant le lien
   "Réaffectation des agents" (déplacé) + les 3 nouvelles entrées + l'historique des corrections
   — visible uniquement pour `mdmaiga`.

---

## Tâches (ordonnées : modèles → services → forms → views → templates)

### 1. Modèle d'audit (`core/models.py` — contrainte structurelle, cf. `rules/ARCHITECTURE.md`)

```python
class CorrectionAdministrative(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.PROTECT)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    cible = GenericForeignKey('content_type', 'object_id')
    type_correction = models.CharField(max_length=30, choices=TYPES_CORRECTION)
    motif = models.TextField()
    anciennes_valeurs = models.JSONField()
    nouvelles_valeurs = models.JSONField()
    date_action = models.DateTimeField(auto_now_add=True)
```

`TYPES_CORRECTION` : `LOT_QUANTITE`, `LOT_PRIX`, `LOT_DATE`, `DISTRIBUTION_AGENT`,
`DISTRIBUTION_SUPERVISEUR`, `DISTRIBUTION_QUANTITE`, `VENTE_PRIX_QUANTITE`.

Migration `core` dédiée. `motif` non-nullable — la soumission d'une correction sans justification
doit être rejetée au niveau formulaire, pas seulement au niveau modèle.

Garde partagée (`direction/views.py` ou nouveau `direction/permissions.py`) : généraliser
`_acces_reaffectation` en `_acces_admin_mdmaiga`, un seul endroit, réutilisé par toutes les vues
de ce sprint et par la réaffectation existante.

### 2. Service — Correction Lot (`marchandise/services.py`)

`corriger_lot(lot, *, quantite_initiale=None, prix_achat_unitaire=None, date_reception=None,
motif, utilisateur)` :

- `select_for_update()` sur le `LotEntrepot`.
- Refuse si `nouvelle_quantite_initiale < (quantite_initiale actuelle - quantite_restante)`
  (quantité déjà sortie vers des superviseurs/agents).
- Recalcule et persiste `valeur_stock_initiale`.
- Une correction de date n'a aucun impact sur les stocks (même règle que
  `corriger_affectation`).
- Crée la ligne `CorrectionAdministrative` (`type_correction` selon le(s) champ(s) modifié(s)).
- Tout dans un `transaction.atomic()`.

### 3. Service — Correction Distribution (`marchandise/services.py`, aux côtés de
   `corriger_affectation`)

`corriger_distribution(detail_distribution, *, agent_terrain=None, superviseur=None,
quantite=None, motif, utilisateur)` :

- **Agent seul** : réaffecte `DistributionAgent.agent_terrain`, à condition qu'il dépende du même
  superviseur (sinon exiger aussi un nouveau `superviseur` — cf. cas suivant).
- **Superviseur (+ agent)** : réécrit `DistributionAgent.superviseur`, même mécanique que
  `direction.reaffectation_agents` (`direction/views.py:1582-1629`) — réutiliser cette logique
  plutôt que la dupliquer (extraire en fonction commune si nécessaire).
- **Quantité** : reprend la cascade de `corriger_affectation` (delta vers
  `AffectationLotSuperviseur.quantite_restante` et `LotEntrepot.quantite_restante`), refuse de
  descendre sous `DetailDistribution.quantite_vendue`.
- Crée la ligne `CorrectionAdministrative`.
- `transaction.atomic()` + `select_for_update()`.

### 4. Service — Correction Vente (`vente/services.py` — à créer si absent)

`corriger_vente(vente, *, prix_vente_unitaire=None, quantite=None, motif, utilisateur)` :

- `select_for_update()` sur la `Vente` et son `Recouvrement` lié.
- Aucune garde liée à un recouvrement déjà remis (décision n°3).
- Recalcule `Recouvrement.montant_recouvre = nouvelle_quantite × nouveau_prix_vente_unitaire`.
- Si une `Dette` existe pour cette vente (cas actuellement non exercé, `mode_paiement` toujours
  `comptant`) : garde défensive minimale — refuser la correction plutôt que recalculer sans
  scénario réel pour la tester.
- Crée la ligne `CorrectionAdministrative`.
- `transaction.atomic()`.

### 5. Forms (`direction/forms.py`)

- `CorrectionLotForm`, `CorrectionDistributionForm`, `CorrectionVenteForm` — chacun pré-rempli
  avec les valeurs actuelles, champ `motif` (textarea, obligatoire) commun aux trois.
- `CorrectionDistributionForm` : `superviseur`/`agent_terrain` avec le même pattern AJAX que
  `AffectationSuperviseurForm` (queryset vide au GET, peuplé par changement de superviseur).

### 6. Views (`direction/views.py`, ou nouveau `direction/views_corrections.py` si le fichier
   existant devient trop long)

- `corriger_lot`, `corriger_distribution`, `corriger_vente`, `historique_corrections` — toutes
  protégées par `_acces_admin_mdmaiga`.
- `historique_corrections` : liste paginée de `CorrectionAdministrative`, filtrable par
  `type_correction`/date.

### 7. URLs (`direction/urls.py`)

Routes dédiées, namespace `direction` existant (comme la réaffectation).

### 8. Templates

- `direction/templates/direction/corrections/corriger_lot.html`
- `direction/templates/direction/corrections/corriger_distribution.html`
- `direction/templates/direction/corrections/corriger_vente.html`
- `direction/templates/direction/corrections/historique_corrections.html`
- `direction/templates/base_admin.html` : nouvelle section de menu "Admin" (visible seulement
  pour `mdmaiga`), regroupant le lien "Réaffectation des agents" (déplacé depuis son
  emplacement actuel) + les 4 nouveaux liens.

Mobile-first, cohérent avec les conventions déjà posées (`marchandise`/`vente`) : double layout
desktop/mobile, bouton de validation `sticky` sur mobile.

---

## Tests

- `marchandise/tests.py` :
  - `corriger_lot` refuse une quantité initiale sous ce qui est déjà sorti.
  - `corriger_lot` recalcule `valeur_stock_initiale`.
  - `corriger_distribution` (quantité) : cascade correcte vers `AffectationLotSuperviseur` et
    `LotEntrepot`, refuse sous `quantite_vendue`.
  - `corriger_distribution` (agent/superviseur) : réaffectation correcte, refuse un agent non
    rattaché au superviseur choisi.
- `vente/tests.py` :
  - `corriger_vente` recalcule `Recouvrement.montant_recouvre`.
  - `corriger_vente` : `finance.services.solde_superviseur()` reflète bien la correction sans
    intervention supplémentaire (test d'intégration cross-app).
- `direction/tests.py` :
  - accès refusé aux 4 nouvelles vues pour tout utilisateur ≠ `mdmaiga`.
  - chaque correction crée exactement une `CorrectionAdministrative` avec `anciennes_valeurs`/
    `nouvelles_valeurs` corrects et `motif` non vide.
  - soumission sans `motif` → formulaire invalide.

---

## Documentation

- `marchandise/APP_MARCHANDISE.md` : ajouter `corriger_lot` et `corriger_distribution` à côté de
  `corriger_affectation` (section Service métier + Invariants).
- `vente/APP_VENTE.md` : ajouter `corriger_vente` (nouveau `vente/services.py` si créé cette
  fois-ci).
- `direction/APP_DIRECTION.MD` (ou équivalent) : nouvelle section "Admin — corrections
  administratives" (accès, 4 écrans, modèle `CorrectionAdministrative`), mise à jour de la
  section menu pour refléter le déplacement de la réaffectation.
- `core/APP_CORE.md` : ajouter `CorrectionAdministrative` à la section modèles d'audit, à côté de
  `JournalModificationDistribution`.

---

## Definition of Done

- Les trois corrections (Lot, Distribution, Vente) sont accessibles uniquement à `mdmaiga`, dans
  une section "Admin" dédiée du menu direction.
- Chaque correction est atomique, respecte les mêmes invariants que la création (pas de stock
  négatif, pas de correction sous une quantité déjà vendue), et exige un `motif`.
- Chaque correction produit exactement une ligne `CorrectionAdministrative` consultable dans
  "Historique des corrections", filtrable par type et par date.
- Une correction de `Vente` répercute automatiquement sur `Recouvrement.montant_recouvre` et,
  sans code supplémentaire, sur `finance.services.solde_superviseur()`.
- Tests verts : `python manage.py test marchandise vente direction core`.
- Les 4 `APP_*.md` listés ci-dessus sont à jour (règle CLAUDE.md — dans la même session que le
  code, pas seulement en fin de sprint).
