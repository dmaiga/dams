# Sprint 07 — Collecte superviseur du gestionnaire de stock + alertes groupées par superviseur

**Statut** : ✅ terminé — les deux constats sont implémentés (vérifié le 14/08/2026 :
`core.views.verser_superviseurs_gestionnaire`, `VersementForm.save()` restreint à
`est_rot`/`est_direction`, regroupement par superviseur dans
`monitoring/services/moteur_alerte.py`).

## Contexte

Deux sujets indépendants, remontés par mdmaiga le 12/08/2026.

**Sujet A** — la collecte de l'argent des superviseurs existe aujourd'hui à **trois** endroits
distincts, avec des comportements différents :

1. `core.VersementForm` / vue `creer_versement` (`core/views.py:1519-1539`, `core/forms.py:1231-1304`)
   — utilisé par le gestionnaire de stock (autorisé explicitement dans `VersementForm.save()`,
   `core/forms.py:1284`). Formulaire **individuel** (pas de superviseur identifié, un seul montant
   global) : crée uniquement un `VersementBancaire`, **ne crée jamais de `RecouvrementSuperviseur`**
   — le solde du superviseur n'est donc jamais réduit par ce chemin.
2. `finance.recouvrement_versement_groupe` (`finance/views.py:190-273`) — réservé à la Direction
   (`_acces_finance = agent.est_direction`, `finance/views.py:30-31`). Formulaire **groupé** : une
   ligne par superviseur actif, montant préaffiché à partir du solde calculé
   (`lister_soldes_superviseurs`), montant_hors_vente + reçu par ligne. Crée, par ligne saisie, un
   `RecouvrementSuperviseur` (réduit le solde) **et** un `VersementBancaire` (+ `RecuVersement` si
   reçu fourni).
3. `agents.recouvrer_superviseur` (`agents/views.py:1277-1334`) — réservé au ROT. Recouvrement
   individuel via `RecouvrementSuperviseurForm`.

Conséquence du point 1 : quand le gestionnaire de stock encaisse un versement via son formulaire
actuel, le solde superviseur n'est jamais débité. Le moteur d'alerte (`monitoring`,
`evaluer_solde_superviseur`) continue donc de considérer ce superviseur en dette et répète l'alerte
« solde » indéfiniment, alors que l'argent a bien été remis dans les faits.

**Sujet B** — le moteur d'alerte (`monitoring/services/moteur_alerte.py`) envoie aujourd'hui **un
message par situation constatée** (un agent sans vente, un lot dormant), sans regroupement. Un
superviseur avec 10 agents sans vente déclenche 10 messages Telegram distincts. mdmaiga veut un
message par superviseur, listant ses agents/lots concernés.

---

## Constat 1 (🔴 bug) — Nouveau formulaire de collecte pour le gestionnaire de stock, qui réduit le solde

### Décisions actées (mdmaiga, 12/08/2026)

- **Périmètre** : un nouveau formulaire dédié au gestionnaire de stock uniquement. Les écrans
  existants de la Direction (`finance.recouvrement_versement_groupe`) et du ROT
  (`agents.recouvrer_superviseur`) restent inchangés, en parallèle.
- **Contenu de la page** : liste des superviseurs actifs (`Agent.objects.filter(type_agent='entrepot',
  est_actif=True)`), chacun avec une seule zone de saisie libre pour le montant reçu de lui.
  **Aucun solde n'est calculé ni affiché** sur cette page (contrairement à
  `recouvrement_versement_groupe`, qui préaffiche le solde courant) — le gestionnaire indique
  simplement ce qu'il a reçu, sans que le système ne suggère ou ne compare à un solde théorique.
- **Montant hors vente** : un champ **unique, au niveau de la page**, non rattaché à un superviseur
  particulier (contrairement au `montant_hors_vente` par ligne de
  `LigneRecouvrementVersementForm`).
- **Bordereau de versement** : **un seul fichier** pour toute la soumission (tous les superviseurs
  de la page confondus) — pas un fichier par ligne, contrairement au champ `recu` par ligne du
  formset `finance`.
- **Réduction du solde (le correctif du bug)** : chaque ligne avec un montant saisi doit créer un
  `RecouvrementSuperviseur` (réduit le solde individuel du superviseur concerné), exactement comme
  le fait déjà `recouvrement_versement_groupe` (`finance/views.py:234-239`). C'est ce qui manque
  aujourd'hui au chemin gestionnaire et cause les alertes de solde qui ne cessent jamais.
- **Retrait de l'ancien accès** : une fois le nouveau formulaire en place, le gestionnaire de stock
  perd l'accès à l'ancien `creer_versement`/`VersementForm`, pour éviter que le bug ne revienne si
  l'ancien chemin est encore utilisé par erreur. Le formulaire `VersementForm.save()`
  (`core/forms.py:1284-1285`) n'autorise donc plus `rot.est_gestionnaire_stock` ; seuls
  `est_rot`/`est_direction` restent acceptés sur ce chemin historique.

### Modèle de données à créer par soumission

Contrairement à `recouvrement_versement_groupe` qui crée un `VersementBancaire` **par ligne**, ici
un seul `VersementBancaire` est créé **par soumission** (cohérent avec « un seul bordereau ») :

- Pour chaque ligne avec un montant saisi : un `RecouvrementSuperviseur.objects.create(superviseur=...,
  rot=agent_connecte, montant=..., date_recouvrement=maintenant)`.
- Une fois la boucle terminée, si au moins une ligne a été traitée : un seul
  `VersementBancaire.objects.create(effectue_par=agent_connecte, montant_vente=<somme des montants
  saisis>, montant_hors_vente=<champ page>, date_versement_reelle=maintenant)`.
- Si un bordereau a été fourni : un seul `RecuVersement.objects.create(versement=..., fichier=...)`
  rattaché à ce `VersementBancaire` unique.
- Le tout dans un `transaction.atomic()`, sur le modèle de `finance/views.py:219-251`.

### Tâches

1. `core/forms.py` :
   - `VersementSuperviseurLigneForm(forms.Form)` — `superviseur` (`ModelChoiceField`,
     `widget=forms.HiddenInput`, queryset `Agent` `type_agent='entrepot'`/`est_actif=True`),
     `montant` (`DecimalField`, `required=False`, `min_value=0`). Pas de champ solde, pas de champ
     hors-vente, pas de champ reçu sur la ligne (contrairement à
     `finance.LigneRecouvrementVersementForm`).
   - `VersementSuperviseurFormSet = forms.formset_factory(VersementSuperviseurLigneForm, extra=0)`.
   - `VersementSuperviseurGlobalForm(forms.Form)` — `montant_hors_vente` (`DecimalField`,
     `required=False`, `min_value=0`), `bordereau` (`FileField`, `required=False`, mêmes extensions
     acceptées que `VersementForm.recus`), `description` (`CharField`/`Textarea`, `required=False`).
   - Restreindre `VersementForm.save()` (`core/forms.py:1284-1285`) : retirer
     `rot.est_gestionnaire_stock` de la condition autorisée.
2. `core/views.py` :
   - Nouvelle vue `verser_superviseurs_gestionnaire(request)` — accès restreint à
     `agent.est_gestionnaire_stock` (redirection `access_denied` sinon, sur le modèle de
     `_acces_finance` dans `finance/views.py:30-31`).
     - GET : liste des superviseurs actifs, `initial` du formset avec `superviseur=<pk>` et
       **`montant=None`** (jamais préaffiché à partir d'un solde calculé).
     - POST : valide formset + `VersementSuperviseurGlobalForm` ; dans `transaction.atomic()`,
       boucle sur les lignes avec montant renseigné → crée les `RecouvrementSuperviseur`, cumule le
       total, puis crée le `VersementBancaire` unique (+ `RecuVersement` unique si bordereau fourni).
       Message si aucune ligne saisie (« rien à traiter »), sur le modèle de
       `recouvrement_versement_groupe` (`finance/views.py:254-260`).
   - `creer_versement` (`core/views.py:1519-1539`) : ajouter un contrôle explicite —
     `if agent_connecte.est_gestionnaire_stock: return redirect('access_denied')` (ou message
     d'erreur + redirection) — le formulaire seul (`VersementForm.save()`) refusera de toute façon
     l'enregistrement une fois la condition retirée, mais le message d'erreur direct en entrée de
     vue est plus clair pour l'utilisateur qu'une `ValueError` remontée depuis le form.
3. `core/urls.py` : nouvelle route, ex. `versement-superviseurs/`, name
   `verser_superviseurs_gestionnaire` (à côté des routes `versement/...` existantes,
   `core/urls.py:66-71`).
4. `core/templates/core/factures/verser_superviseurs_gestionnaire.html` : nouveau template — liste
   des superviseurs actifs avec, par ligne, uniquement le nom du superviseur et le champ montant ;
   le champ hors-vente et le champ bordereau une seule fois en bas de page (ou en haut), pas par
   ligne.
5. `core/templates/base.html` (menu gestionnaire de stock, `~471-475`) : le lien « Versements »
   pointe toujours vers `liste_versement` (historique, inchangé) ; c'est le bouton « + Versement »
   **à l'intérieur** de `core/templates/core/factures/liste_versement.html:15` et `:99` qui doit
   être conditionné — pour `est_gestionnaire_stock`, pointer vers
   `verser_superviseurs_gestionnaire` au lieu de `creer_versement` ; pour les autres rôles
   (rot/direction), garder `creer_versement` inchangé.
6. `core/APP_CORE.md` : documenter le nouveau formulaire/vue, la restriction de
   `VersementForm.save()`, et le fait que le gestionnaire de stock n'a plus accès à `creer_versement`.

---

## Constat 2 (🟡 produit) — Alertes groupées par superviseur au lieu d'un message par agent/lot

### Décisions actées (mdmaiga, 12/08/2026)

- Un message **groupé par superviseur** pour l'alerte « agents sans vente » (`activite`), listant
  tous ses agents concernés dans un seul message (format donné par mdmaiga : nom du superviseur, puis
  la liste des agents en dessous).
- Un message **groupé par superviseur**, séparé du précédent, pour l'alerte « rétention de produits
  chez les agents/superviseurs » (`stock`).
- Les deux restent des messages distincts (pas de fusion activité + rétention dans un seul message).

### Constat technique

- `evaluer_baisse_activite` (`monitoring/services/moteur_alerte.py:112-147`) boucle aujourd'hui sur
  `StockAgeService.agents_sans_vente_recente()` (`surveillance/services/stock_age_service.py:50-100`)
  et crée une `Alerte` par agent (`type_alerte="activite"`, clé `agent=agent.user`). Chaque ligne
  porte déjà `superviseur` (`agents_sans_vente_recente`, champ `"superviseur": agent.superviseur`,
  qui peut être `None` si l'agent n'a pas de superviseur assigné).
- `evaluer_stock_ancien` (`moteur_alerte.py:68-86`) boucle sur `StockAgeService.lots_stock_dormant()`
  (`stock_age_service.py:128-186`), qui couvre **deux origines distinctes** :
  - `origine="entrepot"` : lots dormants au dépôt central, **sans superviseur** (`superviseur: None`)
    — ce n'est pas de la « rétention chez un agent », c'est du stock qui n'a jamais été affecté.
  - `origine="superviseur"` : lots affectés à un superviseur et non écoulés
    (`AffectationLotSuperviseur`) — c'est le cas concerné par la demande de mdmaiga (« rétention de
    produits chez les agents de vente »). Note : le regroupement se fait par **superviseur**, pas par
    agent terrain individuel — c'est le seul niveau de granularité que le modèle actuel permet
    (`AffectationLotSuperviseur` n'a pas de notion d'agent terrain, seulement de superviseur).
- Le modèle `Alerte` (`core/models.py`, migration `0109_...`) a déjà un champ `superviseur` (FK),
  utilisé par `evaluer_solde_superviseur` (`moteur_alerte.py:26-36`, clé `superviseur=superviseur.user`)
  — le même schéma de clé de dédoublonnage est réutilisable ici.
- `AlerteDeduplicationService.get_ou_creer`/`cloturer_si_resolue`
  (`monitoring/services/deduplication_service.py`) fonctionnent par clé d'identification arbitraire
  (`**cles_identification`) — passer `superviseur=superviseur.user` au lieu de `agent=agent.user` /
  `lot=lot` fonctionne sans modification du service lui-même.

### Point ouvert — agents/lots sans superviseur assigné

- `evaluer_baisse_activite` : un agent terrain sans superviseur (`agent.superviseur is None`) ne
  peut pas être rattaché à un message groupé par superviseur. Décision retenue par défaut (à
  confirmer si le cas se présente en pratique) : ces agents restent sur une alerte **individuelle**
  (comportement actuel inchangé), en parallèle des messages groupés par superviseur.
- `evaluer_stock_ancien` : les lots `origine="entrepot"` (sans superviseur) restent des alertes
  **individuelles par lot**, inchangées — seuls les lots `origine="superviseur"` sont regroupés par
  superviseur.

### Tâches

1. `monitoring/services/moteur_alerte.py` — `evaluer_baisse_activite` (112-147) :
   - Récupérer `StockAgeService.agents_sans_vente_recente()`, filtrer `type_agent == "terrain"`
     (inchangé), puis grouper les lignes restantes par `superviseur` (`itertools.groupby` sur une
     liste triée, ou `defaultdict(list)`).
   - Pour chaque superviseur avec au moins un agent sans vente : un seul
     `AlerteDeduplicationService.get_ou_creer(type_alerte="activite", superviseur=superviseur.user,
     defaults={...})`, message construit en listant chaque agent (une ligne par agent sous le nom du
     superviseur, format proposé : `f"{superviseur.full_name} — {n} agent(s) sans vente depuis plus
     de 5 jours :\n" + "\n".join(f"- {agent}" for agent in agents)`).
   - Pour les agents sans superviseur : conserver le comportement actuel (une alerte par agent, clé
     `agent=agent.user`).
   - Adapter `cloturer_si_resolue("activite", ...)` : la liste des situations actives doit maintenant
     contenir un mélange de clés `{"superviseur": ...}` (groupes) et `{"agent": ...}` (agents sans
     superviseur) — vérifier que `AlerteDeduplicationService.cloturer_si_resolue`
     (`deduplication_service.py:61-79`) gère bien des clés hétérogènes d'un item à l'autre (il
     dérive `cles_suivies` du premier élément de la liste, `ligne 69` — **à corriger si les deux
     familles de clés coexistent dans le même appel** : possible qu'il faille deux appels séparés à
     `cloturer_si_resolue`, un pour les clés `superviseur`, un pour les clés `agent`, plutôt qu'un
     seul appel mélangé).
2. `monitoring/services/moteur_alerte.py` — `evaluer_stock_ancien` (68-86) :
   - Séparer les lignes `origine="entrepot"` (comportement actuel inchangé, une alerte par lot,
     clé `lot=lot`) des lignes `origine="superviseur"` (nouveau regroupement par superviseur, clé
     `superviseur=superviseur.user`, message listant les lots retenus chez ce superviseur).
   - Même point d'attention que ci-dessus sur `cloturer_si_resolue` avec deux familles de clés — deux
     appels séparés (un pour `type_alerte="stock"` clé `lot`, un pour clé `superviseur`) plutôt qu'un
     seul mélangé, **ou** introduire un `type_alerte` distinct pour le cas superviseur (ex.
     `"stock_superviseur"`) si on préfère séparer complètement les deux familles dans
     `monitoring/constants.py::ALERTES_MVP` (a un impact sur `reenvoi_heures` : à trancher si le
     délai de renvoi doit être identique aux lots entrepôt ou différent).
3. `monitoring/constants.py` (`ALERTES_MVP`) : si un nouveau `type_alerte` est introduit au point 2,
   l'ajouter avec son `reenvoi_heures`.
4. `monitoring/APP_MONITORING.md` : documenter le regroupement par superviseur (formats de message,
   gestion des agents/lots sans superviseur).

---

## Ordre suggéré

1. **Constat 1** (bug prioritaire — les fausses alertes de solde ne cesseront pas tant que le
   nouveau formulaire n'est pas en place et l'ancien accès retiré).
2. **Constat 2** (confort — réduit le bruit Telegram, indépendant du Constat 1 mais bénéficie d'un
   solde enfin fiable pour l'alerte « solde » une fois le Constat 1 livré).

## Hors périmètre de ce sprint (sauf demande explicite contraire)

- Pas de modification des écrans `finance.recouvrement_versement_groupe` (Direction) ni
  `agents.recouvrer_superviseur` (ROT) — ils restent tels quels.
- Pas de fusion des alertes « activité » et « rétention » dans un message unique par superviseur —
  restent deux messages distincts (décision explicite de mdmaiga).
- Pas de regroupement par superviseur pour l'alerte « prix » (`evaluer_variation_prix`), non
  mentionnée dans la demande.

## Prochaine étape

Réaliser les tâches des Constats 1 et 2, puis mettre à jour `core/APP_CORE.md` et
`monitoring/APP_MONITORING.md` dans la même session, conformément à la règle « Après avoir codé » de
`CLAUDE.md`.
