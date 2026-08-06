# Sprint 06 — Corrections & arbitrages : Engagements superviseur ↔ champ (dams_agro)

**Statut** : 📋 à cadrer — constats de mdmaiga du 05/08/2026, à trancher avant la prochaine session (aucun code écrit sur ces points).

## Contexte

Suite directe de l'intégration livrée le 05/08/2026 (module `finance` + `analyse_champ` +
dashboards, consommant l'API figée de dams_agro `/api/engagements/...`). En relisant le résultat,
mdmaiga a noté 3 points à corriger/arbitrer avant de poursuivre. Aucun n'a encore de solution
tranchée — ce document capture les constats et les options, pas des décisions.

---

## Constat 1 (🔴 bug) — Un remboursement initié côté champ (dams_agro) n'alimente pas le solde du superviseur dans `dams`

### Symptôme (mdmaiga, 05/08/2026)

> « Après avoir effectué un remboursement côté technicien, le solde du superviseur n'est pas
> augmenté. » — confirmé aussi côté Direction : les transactions sont bien visibles (historique
> des mouvements), mais le solde chiffré ne bouge pas dans ce cas précis.

### Cause racine

`finance.services.rembourser_engagement_champ(depense, montant)` est le **seul** point qui crée
un `RemboursementChamp` local — c'est ce modèle qui alimente le terme `remboursements_champ` de
`solde_superviseur()`. Cette fonction n'est appelée que lorsque le remboursement est **initié
depuis `dams`** (vue `finance:rembourser_engagement_champ`, le superviseur clique "Rembourser"
sur son dashboard).

Mais un remboursement peut aussi être enregistré **directement côté dams_agro**, par le rôle
`finance` de ce repo séparé (page propre à dams_agro, `/engagements/<pk>/rembourser/`). Dans ce
cas :
- dams_agro sait que l'engagement est remboursé (son `EngagementFinancier.reste_a_rembourser`
  diminue bien, c'est visible via son API) ;
- **`dams` n'en est jamais informé** — il n'existe aucun mécanisme de synchronisation retour
  (pas de webhook dams_agro → dams, pas de polling).

Le `Depense` local reste donc affiché comme non remboursé, et le solde du superviseur dans
`dams` ne bouge pas, alors que le champ a réellement remboursé. **Ce n'est pas un bug de calcul**
(la formule `solde_superviseur` reste correcte) — c'est un problème de **synchronisation
unidirectionnelle** : `dams` ne peut refléter que ce qu'il sait, et il ne l'apprend aujourd'hui
que lorsqu'il est lui-même à l'origine de l'action.

### Pistes de correction (à trancher, aucune ne nécessite de toucher dams_agro)

1. **Réconciliation périodique** — une commande de management (dans l'esprit de
   `evaluer_alertes`/`generer_salaires_mensuel`, planifiée via tâche OS — pas d'infra Celery dans
   ce repo) qui, pour chaque superviseur actif :
   - interroge `GET /api/engagements/dashboard/?reference_superviseur=<id>` (déjà disponible côté
     dams_agro, aucune modification nécessaire) ;
   - compare le `reste_a_rembourser` distant au reste local (somme des
     `Depense.reste_a_rembourser_champ` de ce superviseur) ;
   - crée les `RemboursementChamp` manquants pour combler l'écart constaté.
   Reste à trancher : fréquence d'exécution, et si un écart doit aussi déclencher une alerte
   (`monitoring`, cf. sprint-05) en plus de la correction silencieuse.

2. **Bouton "Vérifier la synchronisation" à la demande** — sur le détail d'un engagement
   (dashboard superviseur ou détail Direction), un appel `GET /api/engagements/<reference_dams_agro>/`
   à la volée, qui affiche/comble l'écart si besoin. Plus simple à livrer qu'une tâche planifiée,
   mais dépend d'une action manuelle du superviseur ou de la Direction — un remboursement fait
   côté champ resterait invisible tant que personne ne clique.

3. **Combiner 1 et 2** — réconciliation périodique en tâche de fond + bouton manuel pour un
   contrôle immédiat ponctuel.

Écarté d'emblée : imposer une contrainte côté dams_agro (ex. interdire le remboursement direct
pour un engagement d'origine `dams`) — **dams_agro est un contrat figé, aucune modification n'y
est possible** (règle actée au sprint précédent).

**Décision à prendre avec mdmaiga** : option 1, 2, ou 3 — et si retenue, la fréquence de la
réconciliation périodique.

### Décision finale de mdmaiga (06/08/2026)

> J'irais donc sur le clic, et je le placerais sur le lien dans le gabarit de `core/base.html` —
> dès qu'il clique sur "Engagements", avant de rendre le template du futur dashboard (celui du
> Constat 3), on fera la synchronisation à ce moment.

Retenu : **variante de l'option 2** (vérification à la demande), mais sans bouton séparé — le
déclencheur est la navigation elle-même. Concrètement :

- Le lien "Engagements champ" de `core/templates/base.html:528-532` (actuellement vers
  `finance:creer_engagement_champ`) pointe désormais vers la nouvelle page dédiée du Constat 3
  (`finance:mes_engagements_champ`, cf. ci-dessous).
- Au tout début de la vue `mes_engagements_champ` (avant de construire le contexte et de rendre le
  template), on appelle la réconciliation — mais **scopée au seul superviseur courant** (pas à
  tous, contrairement à la commande planifiée de l'option 1 initialement envisagée) : `GET
  /api/engagements/dashboard/?reference_superviseur=<id>`, comparaison au reste local, création
  des `RemboursementChamp` manquants avant l'affichage.
- Aucune modification requise côté dams_agro (contrat figé respecté) — c'est bien `dams` qui
  interroge, jamais l'inverse.

**Constat 1 entièrement tranché** — prêt à implémenter, en même temps que le Constat 3 (la
synchronisation vit dans la même vue que la nouvelle page dédiée).

---

## Constat 2 (🟡 produit / perf) — Tableau "Produits en circulation" du dashboard superviseur

### Remarque de mdmaiga

- Le tableau ne doit pas s'afficher pour tous les superviseurs : « ce n'est pas pour tous les
  superviseurs que ceci sera accordé » — à rendre conditionnel (critère à définir), ou à retirer.
- Le calcul lui-même est jugé peu utile à cet endroit : « elle n'utilise pas dans le dashboard
  pour savoir combien de produits restent avec un agent, c'est au niveau de la vente qui regarde
  le détail de la distribution » — cette information a déjà sa place dans les écrans `vente/`
  (détail de distribution), pas nécessairement dans le résumé du dashboard.

### Rappel technique (05/08/2026)

Ce tableau (`SuperviseurDashboardService.get_produits_en_circulation`) causait un N+1 majeur
(~5000 requêtes SQL sur ce seul dashboard, via `DetailDistribution.quantite_restante_calculee`
appelée en boucle) — déjà corrigé le jour même (2 requêtes groupées `annotate(Sum(...))` au lieu
de 2 requêtes par ligne). Le correctif reste valable quelle que soit la décision produit
ci-dessous, mais si le tableau est retiré ou rendu conditionnel, le calcul associé devient
inutile dans les cas où il ne s'affiche pas — à **conditionner l'exécution**, pas seulement à
l'optimiser davantage.

### Options à trancher

1. **Retirer complètement** cette section du dashboard superviseur (et son calcul associé).
2. **Rendre conditionnelle** — visible seulement pour certains superviseurs (critère à définir :
   `type_agent`, un flag dédié sur `Agent`, une permission, ou autre logique métier).
3. **Garder, mais mettre en cache** (Django cache framework, TTL à définir) si l'information est
   jugée occasionnellement utile malgré tout.

### Décision finale de mdmaiga (06/08/2026)

Option 3 retenue — **garder + mettre en cache**, TTL **1 heure** (3600s, clé de cache par
superviseur, ex. `produits_circulation:<superviseur_id>`). Le calcul
(`SuperviseurDashboardService.get_produits_en_circulation`) reste donc affiché pour tous les
superviseurs (pas de critère conditionnel à implémenter), simplement recalculé au plus une fois
par heure et par superviseur au lieu de à chaque chargement du dashboard.

**Constat 2 entièrement tranché** — prêt à implémenter.

---

## Constat 3 (🟡 produit) — Section "Engagements champ (dams_agro)" du dashboard superviseur

### Remarque de mdmaiga

Même logique que le Constat 2 (à rendre conditionnel, critère à définir, ou à retirer) mais pour
un autre bloc, oublié dans une première rédaction de ce document : la section « Engagements champ
(dams_agro) » affichée directement sur le dashboard superviseur (`agents/templates/agents/dashboards/superviseur.html:77-149`)
— le tableau détaillé des avances/dépenses pour compte, avec bouton "Nouvel engagement" et action
"Rembourser" par ligne.

**Décision de mdmaiga** : retirer ce bloc du dashboard superviseur — trop dense pour un écran de
résumé, source de confusion. Mais tout ce qui appartient à ce flux d'engagement doit rester
accessible : le superviseur (côté `dams`) doit continuer à disposer d'une liste ou d'un
dashboard dédié pour consulter son statut financier vis-à-vis de dams_agro (engagements en cours,
montants remboursés, reste à rembourser).

### Constat technique

- La vue Direction `finance:detail_solde_superviseur` (`finance/views.py:83`, réservée au rôle
  `direction`, `finance/urls.py:8`) affiche déjà un résumé **agrégé** "Engagements champ"
  (`finance/templates/finance/detail_solde_superviseur.html:58-75` : engagé / remboursé / reste à
  rembourser, en totaux) — mais pas le détail ligne à ligne, et cette vue n'est pas ouverte au
  superviseur lui-même.
- Le seul endroit où le superviseur voit le détail ligne à ligne de ses engagements (nature, date,
  montant, état, action "Rembourser") est le bloc qu'on retire du dashboard.
- Retirer le bloc sans rien y substituer ferait perdre au superviseur toute visibilité sur ses
  engagements en cours (hors le formulaire de création, dont le lien resterait à recaser).

### Options à trancher

1. **Page dédiée superviseur** — nouvelle vue/URL (ex. `finance:mes_engagements_champ`), qui
   réutilise le même tableau que celui actuellement en ligne dans le dashboard (même contexte,
   `engagements_champ`), mais sur un écran séparé, accessible via un lien/bouton depuis le
   dashboard résumé. Conserve la fonctionnalité, retire seulement l'encombrement visuel.
2. **Ouvrir `finance:detail_solde_superviseur` au superviseur concerné** — ajouter un contrôle
   d'accès (un superviseur ne peut voir que sa propre fiche, pas celle des autres) et compléter
   cette vue par le détail ligne à ligne (aujourd'hui elle n'a que les totaux). Évite une nouvelle
   vue, mais mélange un écran pensé pour la Direction avec un usage superviseur.
3. **Combiner 1 et 2** — page dédiée superviseur qui reprend la même logique que la vue Direction
   (totaux + détail), sans toucher à l'accès de `detail_solde_superviseur`.

**Décision à prendre avec mdmaiga** : quelle option, et si retenue l'option 1 ou 3, l'URL/le nom
de la nouvelle page et son point d'entrée depuis le dashboard.

### Décision finale de mdmaiga (06/08/2026)

> Que ça soit la porte d'entrée du lien vers "Engagement" — qu'il y ait un dashboard, une liste, tu
> trouves un nom adéquat — qui soit la porte d'entrée : il aura le tableau, et un lien qui le
> guide vers "Nouvel engagement".

Retenu : **option 1** (page dédiée superviseur), qui devient aussi le point d'entrée unique du
flux "Engagements champ" (remplace le lien direct vers le formulaire de création dans la nav).

- **Nom retenu** : `finance:mes_engagements_champ`, URL `/finance/mes-engagements-champ/`,
  template `finance/mes_engagements_champ.html`.
- Reprend le tableau actuellement en ligne dans `agents/templates/agents/dashboards/superviseur.html:92-149`
  (même colonnes : nature, date, commentaire, montant initial, remboursé, reste, état, action
  "Rembourser").
- Un bouton/lien "Nouvel engagement" en haut de page vers `finance:creer_engagement_champ`
  (remplace le bouton actuellement dans le header du bloc retiré).
- `core/templates/base.html:528-532` : le lien "Engagements champ" de la nav pointe désormais vers
  `finance:mes_engagements_champ` au lieu de `finance:creer_engagement_champ` — c'est ce clic qui
  déclenche aussi la synchronisation du Constat 1 (même vue, cf. décision finale du Constat 1
  ci-dessus).
- Le bloc `agents/templates/agents/dashboards/superviseur.html:77-149` ("Engagements champ") est
  supprimé du dashboard résumé.

**Constat 3 entièrement tranché** — prêt à implémenter, avec le Constat 1 (synchronisation) dans
la même vue.

---

## Constat 4 — Amélioration performance, sprint dédié à venir

mdmaiga souhaite consacrer un prochain sprint aux améliorations de performance plus largement,
au-delà du seul correctif du 05/08/2026. À cadrer précisément le moment venu — piste déjà
identifiée en grep le 05/08/2026, non traitée aujourd'hui (hors périmètre du correctif ciblé sur
le seul dashboard superviseur) : `DetailDistribution.quantite_restante_calculee` (`core/models.py`)
est appelée dans une **boucle** à plusieurs autres endroits, chacun un site N+1 potentiel :
`vente/forms.py` (`AffectationLotSuperviseurForm` ou équivalent), `vente/views.py`,
`core/services/agent_analysis_service.py`, `direction/services/agent_analysis_service.py`.

---

## Suggestions complémentaires (Claude, non tranchées) — sujets de discussion

Points remarqués en construisant le module du 05/08/2026, qui n'ont pas été soulevés par mdmaiga
mais valent la peine d'être posés sur la table. Aucun n'est urgent ni décidé — à garder ou écarter
librement.

1. **Restriction d'accès à un seul agent nommé, pas à tout `est_superviseur`.**
   Le brief initial précisait : « un seul agent dams sera habilité pour ces transactions ». Le
   guard actuel (`_acces_engagement_champ = agent.est_superviseur`) ouvre pourtant la création et
   le remboursement à **tous** les superviseurs actifs, pas au seul agent désigné. Le repo a déjà
   un précédent pour ce genre de restriction nominative (`core/templates/base.html` : le lien
   "Dépenses" n'apparaît que si `request.user.agent.user.username == "abdoulaye.kone"`). À
   discuter : faut-il un guard équivalent ici, ou l'ouverture à tout superviseur est-elle en fait
   voulue et le "un seul agent" du brief ne visait que la phase de test ?

2. **Absence de protection contre un double-clic / une double soumission.**
   Si le superviseur soumet deux fois le formulaire de création (double-clic, ou re-soumission
   après un timeout où l'appel a en réalité réussi côté dams_agro mais la réponse s'est perdue),
   rien n'empêche la création de deux engagements identiques. Pas de clé d'idempotence transmise
   à dams_agro (`reference_externe` existe côté API mais n'est pas exploitée dans ce sens). À
   discuter : vaut-il le coût d'implémentation vu le volume attendu (un seul agent, faible
   fréquence) ?

3. **Aucun test automatisé sur ce périmètre.**
   Cohérent avec l'état du reste de `finance/` (`finance/tests.py` est vide, aucun test n'existe
   non plus sur `solde_superviseur`/`solde_caisse_globale`) — mais un flux qui déplace de l'argent
   entre deux systèmes distincts, avec une stratégie remote-first à respecter scrupuleusement, est
   un candidat naturel pour au moins quelques tests de non-régression (succès, échec réseau →
   aucune écriture locale, montant excessif refusé). À discuter : à traiter isolément, ou profiter
   du sprint performance à venir (Constat 3) pour couvrir `finance/` plus largement d'un coup ?

4. **`date_engagement` non exposée côté formulaire dams.**
   L'API dams_agro accepte une date d'engagement explicite (utile pour antidater une avance déjà
   remise physiquement avant sa saisie) ; `finance.services.creer_engagement_champ` la supporte
   déjà en paramètre, mais `EngagementChampForm`/la vue ne l'exposent pas — toujours "aujourd'hui".
   À discuter : besoin réel de pouvoir antidater, ou pas nécessaire en pratique ?

5. **Pas d'annulation possible d'un engagement créé par erreur.**
   Ni côté dams, ni côté dams_agro (API figée) il n'existe de suppression/annulation d'un
   engagement. Une erreur de saisie (mauvais montant, mauvaise nature) ne peut aujourd'hui être
   corrigée que par un remboursement compensatoire manuel, ce qui laisse une trace peu lisible
   dans l'historique. À discuter : accepté comme limite du MVP, ou faut-il prévoir un mécanisme de
   correction (dans le respect de l'invariant "jamais de mutation destructive" déjà en place sur
   `Operation`/`corrects_operation` côté dams_agro) ?

---

## Constat 5 (🟢 amélioration) — Date de versement modifiable dans le formulaire groupé, affichée côté Direction

### Demande de mdmaiga (06/08/2026)

Dans `finance/templates/finance/recouvrement_versement_groupe.html`, ajouter pour chaque ligne un
champ « date de versement » ; que cette date soit la valeur affichée côté Direction sur
`direction/templates/direction/factures/liste_versements.html`, à la place de la date de création.

### Constat technique

- Le modèle `VersementBancaire` a déjà un champ prévu pour ça : `date_versement_reelle`
  (`DateTimeField`, `default=timezone.now`) — `core/models.py:2119`.
- `direction/factures/liste_versements.html:194-195` affiche **déjà** `versement.date_versement_reelle`
  (pas une date de création) ; le filtre période de la vue (`direction/views.py:809-839`) filtre
  aussi sur ce champ. Rien à changer côté affichage Direction.
- Le maillon manquant est en amont : `LigneRecouvrementVersementForm`
  (`finance/forms.py:140-172`, formset du flux groupé) n'expose pas ce champ, et la vue
  `recouvrement_versement_groupe` (`finance/views.py:227,239`) écrase systématiquement
  `date_versement_reelle` avec `timezone.now()` au moment de la création. En pratique, ce champ
  vaut donc toujours la date de création — jamais une date choisie — ce qui donne l'impression
  trompeuse que la Direction voit une "date de création" alors qu'elle voit bien
  `date_versement_reelle`, simplement jamais renseignée autrement.
- Le pattern existe déjà ailleurs dans le code pour un versement individuel :
  `VersementBancaireForm` (`finance/forms.py:52-97`) expose `date_versement_reelle` en widget
  `datetime-local` — à reprendre à l'identique pour le formset groupé.

### Changement proposé

1. Ajouter `date_versement_reelle` à `LigneRecouvrementVersementForm`, même widget
   `datetime-local` que `VersementBancaireForm`, préaffiché dans
   `recouvrement_versement_groupe.html`.
2. Préremplir la valeur initiale à `timezone.now()` (comportement actuel conservé par défaut),
   mais la rendre modifiable.
3. Dans `recouvrement_versement_groupe` (`finance/views.py:239`), utiliser
   `form.cleaned_data['date_versement_reelle']` au lieu de `maintenant` pour
   `VersementBancaire.objects.create(...)`.
4. Aucun changement nécessaire côté `liste_versements.html` — il affiche déjà le bon champ, il
   reflétera automatiquement la date saisie une fois le formulaire corrigé en amont.

### Décision de mdmaiga (06/08/2026) — distinction date système / date business

> Ce sont des recouvrements a posteriori : la date de création est pour le système (logs, audit),
> la date de versement est la valeur business à voir.

Ça tranche le point resté ouvert sur `RecouvrementSuperviseur.date_recouvrement` : ce modèle a
déjà exactement cette distinction en place — `date_recouvrement` (`DateTimeField`, éditable,
c'est la donnée business) **et** `date_creation` (`auto_now_add`, horodatage système immuable) —
voir `core/models.py:2019-2020`. C'est même déjà exposé ainsi dans
`RecouvrementSuperviseurForm` (`agents/forms.py:540-549`, label "Date de remise au ROT",
`datetime-local`) pour le flux de recouvrement individuel — seul le flux groupé
(`recouvrement_versement_groupe`) ne le reprend pas encore.

**Décision** : dans `recouvrement_versement_groupe` (`finance/views.py:233,239`), le même champ
« date de versement » saisi par l'utilisateur doit alimenter **à la fois**
`RecouvrementSuperviseur.date_recouvrement` et `VersementBancaire.date_versement_reelle` (ce sont
les deux faces business du même événement a posteriori) — `date_creation` de
`RecouvrementSuperviseur` reste `auto_now_add`, non touché, pour l'audit.

Note en passant : `VersementBancaire` n'a pas d'équivalent de `date_creation` (pas de champ
`auto_now_add` séparé) — `date_versement_reelle` y joue aujourd'hui les deux rôles. Hors du
périmètre demandé ici (pas de champ d'audit à ajouter sans demande explicite), mais à garder en
tête si un futur audit a besoin de distinguer "quand la ligne a été saisie" de "date business" sur
ce modèle précis.

### Décision de mdmaiga (06/08/2026) — borne de date

> On peut ajouter cette restriction : aujourd'hui ou hier [avant], et empêcher une date future. OK.

**Décision** : la date de versement (et donc `date_recouvrement`/`date_versement_reelle`) ne peut
pas être postérieure à aujourd'hui — validation côté formulaire (`clean_date_versement_reelle` ou
équivalent dans `LigneRecouvrementVersementForm`), qui refuse toute date `> timezone.now()`. Pas de
borne basse (une saisie a posteriori peut remonter arbitrairement dans le passé).

**Constat 5 entièrement tranché** — prêt à implémenter.

---

## Tous les constats sont tranchés — plan d'exécution du sprint

Les 5 constats ont chacun une décision actée par mdmaiga (voir ci-dessus). Découpage en tâches,
dans l'ordre suggéré (bug d'abord, puis les deux chantiers imbriqués Constat 1 + 3, puis Constat 2
et 5 indépendants) :

**Tâche A — Constat 1 + Constat 3 (imbriqués : même vue)**
1. `finance/urls.py` : nouvelle route `mes_engagements_champ`.
2. `finance/views.py` : nouvelle vue `mes_engagements_champ` — au début, réconciliation scopée au
   superviseur courant (`GET /api/engagements/dashboard/?reference_superviseur=<id>`, comparaison
   au reste local, création des `RemboursementChamp` manquants), puis contexte `engagements_champ`
   identique à celui actuellement construit pour le dashboard superviseur.
3. `finance/templates/finance/mes_engagements_champ.html` : nouveau template — reprend le tableau
   de `agents/templates/agents/dashboards/superviseur.html:92-149` + bouton "Nouvel engagement"
   vers `finance:creer_engagement_champ`.
4. `agents/templates/agents/dashboards/superviseur.html` : suppression du bloc "Engagements champ"
   (lignes 77-149).
5. `core/templates/base.html:528-532` : le lien "Engagements champ" pointe vers
   `finance:mes_engagements_champ` au lieu de `finance:creer_engagement_champ`.
6. `finance/APP_FINANCE.md` : documenter la nouvelle vue/URL et le comportement de synchronisation
   au clic.

**Tâche B — Constat 2**
1. `agents/services/superviseur_service.py` (`get_produits_en_circulation`) : mise en cache Django
   (clé `produits_circulation:<superviseur_id>`, TTL 3600s).
2. Vérifier l'invalidation : identifier les événements qui rendent le cache obsolète (nouvelle
   distribution, nouvelle vente affectant `quantite_restante_calculee`) — à trancher au moment de
   coder si une invalidation explicite est nécessaire ou si le TTL d'1h suffit tel quel.

**Tâche C — Constat 5**
1. `finance/forms.py` (`LigneRecouvrementVersementForm`) : ajouter `date_versement_reelle`
   (widget `datetime-local`), validation refusant une date future.
2. `finance/templates/finance/recouvrement_versement_groupe.html` : afficher le nouveau champ par
   ligne.
3. `finance/views.py` (`recouvrement_versement_groupe`) : utiliser la date saisie pour
   `RecouvrementSuperviseur.date_recouvrement` **et** `VersementBancaire.date_versement_reelle`
   (au lieu de `maintenant` pour les deux) ; `date_creation` reste `auto_now_add`, non touché.
4. `finance/APP_FINANCE.md` : documenter le nouveau champ et la distinction date système/business.

**Hors périmètre de ce sprint** (sauf demande explicite contraire) : les 5 points de la section
"Suggestions complémentaires" ci-dessus (restriction d'accès nominative, double-soumission, tests
automatisés, `date_engagement` non exposée, annulation d'engagement).

---

## Prochaine étape

Réaliser les tâches A, B, C ci-dessus, puis mettre à jour `finance/APP_FINANCE.md` et
`agents/APP_AGENTS.md` (ou équivalents) dans la même session, conformément à la règle "Après avoir
codé" de `CLAUDE.md`.
