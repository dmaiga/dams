# Sprint 10 — Ventes saisies côté champ (dams_agro) : synchronisation vers `dams`

**Statut** : 📋 à cadrer — besoin remonté par mdmaiga le 13/08/2026, aucune option tranchée, aucun
code écrit. Ce document capture le problème, un calcul de solde à repenser, et une question
d'architecture volontairement laissée ouverte (webhook / HTTP / autre) — pas une décision.

## Contexte

Aujourd'hui, une vente n'existe dans `dams` que si elle y est saisie directement (agent terrain ou
superviseur, `vente.enregistrer_vente`/`core.enregistrer_vente` — voir sprint-07). Rien ne permet à
un agent qui saisit côté **dams_agro** ("le champ") de déclarer qu'il a vendu tout ou partie d'une
distribution qu'il a reçue depuis `dams`, et de le voir refléter automatiquement ici.

Besoin exprimé (mdmaiga, 13/08/2026) :
1. Permettre à l'agent, côté champ, de renseigner les produits vendus à partir d'une distribution
   reçue.
2. Que cette information apparaisse **automatiquement** côté `dams` (au niveau de la distribution
   concernée), **sans** que le gestionnaire de stock n'ait à ressaisir ou acquitter manuellement
   cette réception.
3. Adapter le calcul du **solde superviseur** en conséquence — une vente réalisée côté champ ne
   remet pas d'argent physique au superviseur de la même façon qu'une vente terrain classique.
4. Une question d'architecture explicitement laissée ouverte : webhook (dams_agro pousse vers
   `dams`), on reste sur le pattern HTTP actuel (`dams` interroge dams_agro), ou une autre solution
   d'envoi/synchronisation — mdmaiga note que régler cette question réglerait aussi, par la même
   occasion, **le problème de l'engagement** (la réconciliation `EngagementChamp`/`Depense`,
   sprint-06 Constat 1).

C'est très exactement le scénario anticipé par sprint-09, point 3 : *« Si demain un autre domaine a
besoin d'apprendre un fait survenu côté dams_agro (un mouvement de stock au champ, un statut
d'agent, etc.), il faudra probablement réinventer le même genre de mécanisme depuis zéro plutôt que
réutiliser quelque chose d'existant. »* Ce sprint est ce deuxième cas d'usage.

---

## Constat 1 — Ce qui existe déjà entre `dams` et dams_agro

Vérifié dans le code (`analyse_champ/services.py`, `finance/services.py`, `core/models.py`) le
13/08/2026 :

- **Le lien n'est pas strictement lecture seule aujourd'hui**, contrairement à ce que documentent
  encore `rules/ARCHITECTURE.md:84-91` et `rules/STACK.md:37,42` (« proxy de lecture », « GET
  exclusivement ») — ces deux docs n'ont pas été mis à jour après l'introduction du POST
  engagements. Il existe un unique canal d'écriture `dams` → dams_agro :
  `analyse_champ.services.creer_engagement_dams_agro` (POST `/api/engagements/`, authentifié
  `X-Api-Key`), utilisé exclusivement pour créer une avance de trésorerie/dépense pour compte.
- **Aucun canal d'écriture dams_agro → `dams`** — ni webhook, ni endpoint qui recevrait un appel
  entrant de dams_agro. `analyse_champ/urls.py` ne définit que des routes qui, elles-mêmes,
  appellent dams_agro en GET.
- **Le seul mécanisme de "sync retour" existant** est `finance.services.synchroniser_engagements_champ`
  (sprint-06, Constat 1) : un GET déclenché **à la demande**, au chargement de la page
  `finance:mes_engagements_champ` (pas de tâche planifiée, pas de webhook), scope à un superviseur,
  qui compare le `reste_a_rembourser` distant au reste local et crée les `RemboursementChamp`
  manquants pour combler l'écart. Décision d'origine (sprint-06) : *« un clic suffit, pas de tâche
  planifiée ni de bouton séparé — le volume attendu est faible, un seul agent habilité »*. Rien
  d'équivalent n'existe pour des ventes/distributions.
- **`dams_agro` reste un contrat figé** (règle actée sprint-06) : *« aucune modification n'y est
  possible »* depuis ce repo. Toute option qui suppose un changement côté dams_agro (par exemple un
  vrai webhook sortant déclenché par dams_agro) sort du périmètre que ce repo peut décider seul —
  à vérifier/négocier séparément avec l'équipe dams_agro, pas une décision de ce sprint.
- **Aucun champ de rapprochement n'existe** sur `Vente`, `DetailDistribution` ou `DistributionAgent`
  (pas de `reference_dams_agro`, pas de champ d'origine "dams" vs "champ") — contrairement à
  `Depense.reference_dams_agro` (`core/models.py:2269`) qui existe déjà pour les engagements. S'il
  faut un jour rapprocher une vente `dams` d'un enregistrement dams_agro, ce champ est à créer, sur
  le modèle de l'existant.

---

## Constat 2 — Le calcul du solde superviseur doit être repensé, pas simplement étendu

`finance.services.solde_superviseur()` (formule actuelle, sprint-03 décision n°14) :

```
solde = encaissements (Recouvrement) − dépenses perso (Depense) − déjà remis (RecouvrementSuperviseur)
        + ajustement_solde + remboursements_champ (RemboursementChamp)
```

Cette formule suppose une chaîne physique complète : l'agent terrain vend → remet l'argent au
superviseur (`Recouvrement`) → le superviseur remet au ROT (`RecouvrementSuperviseur`). Une vente
déclarée côté champ casse cette hypothèse à la base : mdmaiga signale qu'**aucun argent n'est remis
au superviseur** pour ce type de vente — l'agent au champ vend et encaisse dans un circuit qui ne
passe pas par la caisse du superviseur `dams`.

Deux risques concrets si on se contente de créer une `Vente` `dams` "comme d'habitude" à partir
d'une information reçue de dams_agro :

1. **Double comptage** — `Vente.save()` crée une `Dette` si `mode_paiement='credit'`, et le circuit
   normal attend un `Recouvrement` puis un `RecouvrementSuperviseur` pour que l'argent "sorte" du
   solde. Si le montant de cette vente est *déjà* comptabilisé comme revenu dans dams_agro (ses
   propres `operations` financières), le dupliquer dans `solde_superviseur` compterait le même
   argent deux fois entre les deux systèmes.
2. **Sous-comptage / incohérence de stock** — à l'inverse, ne pas du tout faire remonter la quantité
   vendue laisserait `DetailDistribution.quantite_restante_calculee` (qui recalcule dynamiquement à
   partir des `Vente` liées, `core/models.py:1524-1543`) surestimer le stock réellement disponible
   chez l'agent, ce qui fausserait au minimum les alertes de rétention de stock chez les agents
   (`monitoring`, `StockAgeService`, cf. correctifs du 13/08/2026).

Ce sprint ne tranche pas la formule adaptée — il pose la question à trancher : **la quantité vendue
doit décrémenter le stock (`DetailDistribution`) sans que le montant correspondant ne réalimente
`solde_superviseur`**, sauf si l'on peut établir que dams_agro ne compte pas déjà cet argent
ailleurs. Nécessite de clarifier, avec l'équipe dams_agro ou via `docs/api/api_structure.md` (côté
dams_agro, référencé mais non consulté ici), **où est réellement comptabilisé l'argent** d'une vente
au champ aujourd'hui.

---

## Constat 3 — Question d'architecture ouverte (envoi + synchronisation)

Trois familles d'options, aucune tranchée. Présentées pour arbitrage, pas comme recommandation.

### Option A — Webhook (dams_agro pousse vers `dams` à chaque vente enregistrée)

- **Pour** : propagation quasi immédiate, pas de délai d'attente pour le gestionnaire de stock ;
  correspond le mieux à l'objectif « sans que le gestionnaire n'ait à savoir de cette réception » —
  l'information arrive d'elle-même.
- **Contre** : suppose un changement **côté dams_agro** (ajouter un envoi sortant après
  enregistrement d'une vente) — en tension directe avec la règle « contrat figé, aucune modification
  possible depuis ce repo ». Nécessite un endpoint `dams` public/authentifié capable de recevoir un
  appel entrant à tout moment (nouvelle surface d'attaque à sécuriser — authentification, rejeu,
  idempotence si le même événement est renvoyé deux fois). Aucune infra de file d'attente dans ce
  repo (pas de Celery/APScheduler, fait déjà noté sprint-05/06/09) : un webhook reçu doit soit être
  traité de façon synchrone et fiable dans la requête HTTP entrante, soit un mécanisme de retry/
  file devra être introduit — chantier plus large que ce seul besoin.

### Option B — `dams` interroge dams_agro en HTTP (extension du pattern `analyse_champ` actuel)

- **Pour** : ne nécessite **aucune** modification côté dams_agro si l'information est déjà exposée
  via une API en lecture (comme `engagements`/`operations` le sont déjà) — cohérent avec la
  contrainte du contrat figé. Réutilise un pattern déjà éprouvé (`fetch_json`/`_request_engagements`,
  `DamsAgroAPIError`).
- **Contre** : par nature un pull, donc pas instantané — dépend de quand/à quelle fréquence `dams`
  interroge. Reproduit la même limite que `synchroniser_engagements_champ` aujourd'hui (déclenché au
  clic, donc un délai variable selon l'activité de l'utilisateur) sauf si on introduit une
  planification (nécessite une tâche OS, cf. Constat 1).
- **Prérequis à vérifier** : dams_agro expose-t-il déjà un endpoint listant les ventes/opérations de
  stock par distribution/agent (`get_operations` mentionne déjà "stocks" dans son commentaire,
  `analyse_champ/services.py:62`) ? Si oui, cette option ne demande peut-être **aucun** changement
  dams_agro, juste un nouveau service `analyse_champ` + une commande/vue de rapprochement côté
  `dams`, sur le modèle exact de `synchroniser_engagements_champ`.

### Option C — Généraliser le mécanisme de réconciliation existant (suite directe de sprint-09, point 3)

- Plutôt qu'un mécanisme dédié une deuxième fois, extraire de `synchroniser_engagements_champ` un
  petit service générique de rapprochement (« interroger dams_agro, comparer à l'état local, combler
  l'écart ») réutilisable pour les engagements **et** pour les ventes champ. C'est la piste que
  sprint-09 anticipait explicitement pour "le jour où un deuxième cas de synchronisation se
  présente" — ce sprint est ce deuxième cas.
- Reste soumis au même choix push/pull que A/B pour le déclenchement (bouton à la demande, tâche
  planifiée OS, ou webhook si l'option A est retenue malgré ses contraintes) — la généralisation est
  orthogonale au mode de transport.

**Ce que ce sprint ne tranche pas** : le choix entre A/B/C, la fréquence si pull, le comportement en
cas d'échec de synchronisation (retry ? alerte `monitoring` ? silencieux comme aujourd'hui pour les
engagements ?), et le format exact de rapprochement (une vente champ correspond-elle à une seule
`Vente` `dams`, ou à un modèle distinct pour ne pas mélanger les deux origines dans les calculs qui
supposent aujourd'hui une origine unique — recouvrement, dette, etc.) ?

---

## Hors périmètre de ce sprint (sauf demande explicite contraire)

- Toute modification côté dams_agro — hors de portée de ce repo, à négocier séparément si l'option A
  est retenue.
- Le détail de la formule adaptée de `solde_superviseur` — le Constat 2 pose la question, ne la
  résout pas.
- Toute implémentation — ce document est un cadrage, pas un ticket prêt à coder.

## Prochaine étape

Faire trancher par mdmaiga, dans cet ordre :
1. **Où est comptabilisé l'argent** d'une vente réalisée côté champ aujourd'hui (dams_agro ou
   nulle part de façon fiable) — condition préalable pour répondre au Constat 2 sans risquer un
   double comptage.
2. **Option A, B ou C** (Constat 3) pour le mode de synchronisation — en particulier, si dams_agro
   expose déjà un endpoint pertinent (à vérifier via `docs/api/api_structure.md` côté dams_agro ou
   directement avec l'équipe dams_agro) avant d'écarter l'option B faute d'information.
3. Si push (option A) malgré la contrainte du contrat figé : qui, côté dams_agro, peut faire évoluer
   ce contrat, et selon quel calendrier — question d'organisation, pas technique.

Une fois ces trois points tranchés, ce sprint peut être redécoupé en tâches concrètes (modèles,
services, vues) dans un sprint dédié à l'implémentation.
