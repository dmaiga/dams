# APP_VENTE.md

## Rôle

`vente` est la deuxième app **orientée capacité métier** de DAMS — "Ventes terrain et recouvrement".

Elle porte ce qu'il reste au superviseur à faire une fois que `marchandise` a fait son travail : enregistrer les ventes de ses agents (avec prix et type de vente saisis à la volée) et bénéficier d'un recouvrement automatique.

**Toutes les ventes sont enregistrées au comptant pour l'instant** — pas de crédit, pas de dette. Le type de vente le plus fréquent (détail) est pré-coché par défaut.

Dans le cas courant, la marchandise part **directement** du gestionnaire de stock vers l'agent (`marchandise.AffectationSuperviseurForm.agent_terrain`) — `vente` ne gère la distribution que pour les cas d'exception (voir plus bas).

---

## Frontières

| Ce que l'app possède | Ce qu'elle ne touche pas |
|---|---|
| Distribution exceptionnelle (stock non redirigé, auto-distribution) | Gestion des dettes clients (futur `finance/`) |
| Enregistrement des ventes | Versement bancaire / récupération ROT |
| Recouvrement automatique (vente comptant) | Modification/suppression de ventes existantes (`agents/`) |
| Historique des ventes | KPI financiers du dashboard superviseur (`SuperviseurDashboardService.get_finances_superviseur`) |

---

## URLs (`/vente/`)

| Nom | URL | Accès |
|---|---|---|
| `vente:liste_affectations` | `/vente/` | superviseur |
| `vente:creer_distribution` | `/vente/distribuer/` | superviseur |
| `vente:detail_distribution` | `/vente/distribution/<pk>/` | superviseur |
| `vente:enregistrer_vente` | `/vente/vente/nouvelle/` | superviseur |
| `vente:historique_ventes` | `/vente/ventes/` | superviseur |
| `vente:ajax_affectations_par_agent` | `/vente/ajax/affectations-par-agent/` | superviseur |
| `vente:ajax_distributions_par_agent` | `/vente/ajax/distributions-par-agent/` | superviseur |

Guard local : `_acces_superviseur(agent) = agent.est_superviseur` (pattern de permission par capacité, voir `rules/ARCHITECTURE.md`).

---

## Modèles utilisés (définis dans `core`)

| Modèle | Usage |
|---|---|
| `AffectationLotSuperviseur` | Stock que le superviseur détient encore (`agent_terrain_direct__isnull=True`) — cas d'exception uniquement |
| `DistributionAgent` | Distribution exceptionnelle (agent réel ou auto-distribution — `agent_terrain == superviseur`) |
| `DetailDistribution` | Détail de la distribution (lot, quantité). `prix_gros`/`prix_detail` restent `None` — aucun prix n'est hérité |
| `Vente` | Vente enregistrée par le superviseur pour un agent. `prix_vente_unitaire` saisi à chaque vente (obligatoire) ; `type_vente` pré-coché sur `detail` mais modifiable ; `mode_paiement` toujours `'comptant'` (valeur par défaut du modèle, non exposée dans le formulaire) |
| `Recouvrement` | Créé automatiquement à **chaque** vente (toutes comptant pour l'instant) |
| `Dette` | Non utilisée par cette app — `Vente.save()` (existant, non modifié) ne la crée que si `mode_paiement == 'credit'`, ce que `VenteForm` n'envoie jamais actuellement |

Aucune migration `core` n'a été nécessaire pour ce sprint — voir `docs/sprints/sprint-02.md`.

---

## Forms (`vente/forms.py`)

### `DistributionForm`

Flux **d'exception** uniquement — la majorité des affectations arrivent déjà avec un agent choisi directement par `marchandise`.

Champs : `agent_terrain` (agents gérés par le superviseur **+ lui-même**, pour l'auto-distribution), `affectation` (lots détenus par le superviseur, `agent_terrain_direct__isnull=True`, `quantite_restante > 0`), `quantite`.

- `agent_terrain.label_from_instance` : "Moi-même (vente personnelle)" si l'objet est le superviseur, sinon `full_name`.
- `save(superviseur)` : crée `DistributionAgent` + `DetailDistribution` (prix à `None`) et décrémente `affectation.quantite_restante`, dans un `transaction.atomic()`.
- Si `agent_terrain == superviseur`, `DistributionAgent.save()` (logique existante dans `core`) fixe automatiquement `type_distribution = 'AUTO'`.

### `VenteForm`

Seul point de saisie du prix et du type de vente — rien n'est plus hérité d'une distribution pré-remplie.

Champs : `agent_terrain`, `detail_distribution` (peuplé par AJAX selon l'agent), `quantite`, `type_vente` (liste déroulante — un radio-group était source de confusion pour des utilisateurs peu familiers de l'interface — **initial `'detail'`**, cas le plus fréquent, suggestion affinée côté client via `agent.type_vente_par_defaut()`, jamais imposée), `prix_vente_unitaire` (**requis, sans valeur par défaut**), `date_vente` (**date seule**, pas d'heure).

- Pas de champ `mode_paiement` : toutes les ventes sont comptant pour l'instant, `save()` force `mode_paiement='comptant'` (valeur par défaut du modèle de toute façon).
- `date_vente` : `forms.DateField` avec `<input type="date">`, `required=False` (vide = aujourd'hui). Volontairement **pas** de `DateTimeField`/`datetime-local` — source de blocages de saisie sur téléphone (fuseau, format navigateur). `save()` recompose la date/heure complète avec `datetime.combine(jour, timezone.localtime().time())` : le superviseur choisit le jour, le système fixe l'heure.
- `detail_distribution` : `none()` au GET ; en POST, filtré en Python sur `quantite_restante_calculee > 0` (propriété calculée, non filtrable en SQL direct) pour l'agent soumis.
- `clean()` : vérifie que `detail_distribution.distribution.agent_terrain == agent_terrain` et que `quantite <= detail_distribution.quantite_restante_calculee`.
- `save()` : `Vente.objects.create(...)` — la mise à jour de `quantite_vendue` est gérée par `Vente.save()` existant, **non dupliquée ici**. Aucune `Dette` n'est jamais créée puisque `mode_paiement` n'est jamais `'credit'`.

---

## Vues (`vente/views.py`)

- `enregistrer_vente` : crée la `Vente` puis, systématiquement (toutes les ventes sont comptant), crée le `Recouvrement` dans le **même** `transaction.atomic()` — pas de saisie doublon.
- `historique_ventes` : liste paginée (30/page) des ventes du superviseur (`detail_distribution__distribution__superviseur == agent`).
- `ajax_distributions_par_agent` : retourne aussi `type_vente_suggere` (via `agent.type_vente_par_defaut()`) pour présélectionner la liste `type_vente` côté client — jamais imposé côté serveur.

---

## Templates

Mobile-first, cohérent avec les conventions posées dans `marchandise/APP_MARCHANDISE.md` : double layout desktop/mobile, pas de bordures colorées superflues, bouton de validation `sticky` en bas d'écran sur mobile, libellés explicites pour les quantités ("Distribué"/"Restant").

| Template | Description |
|---|---|
| `liste_affectations.html` | Stock résiduel du superviseur (cas d'exception). Message explicite si vide : "tout est déjà distribué directement". |
| `creer_distribution.html` | Formulaire de distribution exceptionnelle — pas d'AJAX nécessaire, `DistributionForm` peuple ses querysets entièrement au `__init__`. |
| `detail_distribution_superviseur.html` | Détail d'une distribution + ventes déjà enregistrées dessus. |
| `enregistrer_vente.html` | Formulaire en 2 étapes (agent & produit → détail de la vente). AJAX sur changement d'agent pour charger les distributions actives ; JS affine le type de vente pré-coché (`detail` par défaut) selon l'agent ; bandeau statique rappelant que le recouvrement est automatique (plus de choix de mode de paiement à l'écran). |
| `historique_ventes.html` | Liste paginée (30/page). Pas de colonne "mode de paiement"/"recouvrement" — toutes les ventes étant comptant, l'information serait redondante sur chaque ligne. |

---

## Tableau de bord superviseur (`agents/`)

`agents/services/superviseur_service.py` — `get_stock_superviseur` et `get_distributions_recentes` ont été remplacés par `get_produits_en_circulation(superviseur)` : regroupe les `DetailDistribution` actives par agent/produit avec la quantité restant à vendre. Reflète l'activité réelle depuis que la marchandise ne transite plus systématiquement par le stock du superviseur.

`agents/templates/agents/dashboards/superviseur.html` — les blocs "Stock sous votre responsabilité" et "Activité récente" sont remplacés par un bloc unique "Produits en circulation". Les 4 KPI financiers du haut de page (`finances_superviseur`) et la section agents (`agents_terrain`/`agents_financiers`) sont **inchangés**.

---

## Invariants

- `quantite <= affectation.quantite_restante` — `DistributionForm.clean()`.
- `quantite <= detail_distribution.quantite_restante_calculee` — `VenteForm.clean()`.
- Décrémentation `AffectationLotSuperviseur.quantite_restante` atomique — `DistributionForm.save()`.
- Création `Recouvrement` atomique avec `Vente` — vue `enregistrer_vente`.
- `prix_vente_unitaire` obligatoire, jamais dérivé d'une distribution (elle n'a pas de prix).
- `type_vente` initial `'detail'` (cas le plus fréquent), suggéré plus finement côté client selon `agent.type_vente_par_defaut()`, jamais imposé côté serveur.
- Toutes les ventes sont `mode_paiement='comptant'` — recouvrement systématique, aucune `Dette` créée par cette app.
- `date_vente` : seul le jour est demandé à l'utilisateur ; l'heure est fixée par le serveur (`timezone.localtime().time()`) au moment de l'enregistrement, pour éviter les blocages de saisie observés avec un champ datetime complet sur mobile.
- Soft delete : `Vente.est_supprime` — jamais de suppression en dur (toutes les requêtes filtrent `est_supprime=False`).

---

## User stories couvertes

Voir `docs/sprints/sprint-02.md` (US-01 à US-06).
