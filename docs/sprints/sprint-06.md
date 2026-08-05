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

---

## Constat 3 — Amélioration performance, sprint dédié à venir

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

## Prochaine étape

Trancher les Constats 1 et 2 avec mdmaiga avant d'écrire le moindre code (méthode du projet —
voir `CLAUDE.md`/`rules/ARCHITECTURE.md` : ne jamais coder avant d'avoir tranché les questions
ouvertes).
