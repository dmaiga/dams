# Sprint 08 — Rattrapage de dette technique (`core`/`agents`) après vérification post-audits

**Statut** : 📋 cadré — vérifications faites le 12/08/2026, plusieurs points prêts à exécuter sans
risque, d'autres nécessitent une décision de mdmaiga (aucun code écrit sur ce sprint).

## Contexte

Deux audits (`docs/audit/audit-app-core.md`, `docs/audit/audit-app-agents.md`) et une comparaison
(`docs/audit/comparaison-core-vs-agents.md`) ont été rédigés les 06-07/07/2026, avec la mention
explicite « créé, non lu / non approuvé ». Ils n'ont jamais été traités : **aucune de leurs
recommandations n'a été appliquée** depuis plus d'un mois, malgré 5 apps ajoutées entre-temps
(`marchandise`, `vente`, `finance`, `bi`, `monitoring`) et les sprints 03 à 06 exécutés.

Une repasse de vérification (12/08/2026) confirme que la quasi-totalité des constats de juillet
sont **toujours valides à l'identique** (seuls les numéros de ligne ont dérivé), et qu'une nouvelle
dette du même type s'est ajoutée depuis avec l'app `vente` (un troisième chemin pour créer une
vente, un quatrième pour distribuer un lot). Ce sprint reprend ces constats, les met à jour, et les
range en deux catégories :

- **Partie A** — corrections sans ambiguïté de comportement (bug, code mort, lien cassé) :
  exécutables directement.
- **Partie B** — duplication de logique métier **vivante des deux côtés** : nécessite un choix de
  mdmaiga sur quel chemin devient la cible, avant toute suppression.

Périmètre volontairement limité au nettoyage — **pas de proposition de nouvelle app
`distribution`** ni de refonte du découpage en apps (l'ADR-001 reste hors périmètre de ce sprint,
sauf sa mise à jour documentaire en Partie C, qui est un simple constat, pas une décision
d'architecture).

---

## Partie A — Corrections sans risque fonctionnel (prêtes à exécuter)

### A1. Liens `{% url %}` cassés dans les templates communs

Toujours cassés (`NoReverseMatch` au clic) :

- `core/templates/core/factures/confirm_delete.html:8` → `{% url 'liste_factures' %}` — n'existe
  nulle part (seul `liste_factures_entrepot` existe). Ce template est lui-même orphelin (jamais
  rendu par aucune vue de `core/views.py`, confirmé par l'audit d'origine) — **candidat à la
  suppression pure et simple** plutôt qu'à la correction du lien.
- `core/templates/registration/password_change.html:68` → `{% url 'tableau_de_bord' %}` — n'existe
  nulle part (seul `tableau_de_bord_superviseur` existe). Ce template est utilisé par **tous les
  agents** après changement de mot de passe → à corriger en priorité (remplacer par le bon nom
  d'URL selon le rôle, ou par un lien générique vers `access_denied`/dashboard adapté au rôle
  connecté).
- `core/templates/registration/password_change_done.html:29` → `{% url 'dashboard' %}` — **s'est
  résolu par accident** : `direction/urls.py:27` a introduit depuis une URL nommée `dashboard`
  (`DashboardView`), et comme `core`/`direction` ne sont pas namespacés (voir C1), ce nom se
  propage globalement. Le lien ne plante donc plus, mais pointe potentiellement vers le dashboard
  Direction pour un utilisateur qui n'est pas de la Direction — **comportement non voulu, pas une
  vraie correction**. À vérifier/corriger explicitement plutôt que laisser ce hasard de routage en
  place.

### A2. Code mort orphelin à supprimer dans `core`

- `core.views.tableau_de_bord_superviseur` (`core/views.py:2276-2529`, ~250 lignes) — jamais
  routée dans `core/urls.py`, doublon exact (même nom) de `agents.views.tableau_de_bord_superviseur`
  (`agents/views.py:110`, celle-ci bien câblée et utilisée partout). Son template
  (`core/dashboard/superviseur.html`) n'existe même pas sur le disque. **Suppression recommandée**
  — aucun risque, code strictement inatteignable.
- `core.views.supprimer_agent` (`core/views.py:186`) — jamais référencée dans aucun `urls.py` du
  projet, son template (`core/agents/supprimer_agent.html`) n'existe pas non plus. Deux options :
  **(a)** supprimer la vue (code mort, pas de suppression d'agent possible aujourd'hui — à
  confirmer que ce n'est pas un besoin réel avant de trancher), ou **(b)** la câbler réellement si
  la suppression d'agent est un besoin non couvert ailleurs (`agents.creer_agent`/`modifier_agent`
  existent, mais aucune suppression côté `agents`). **Décision à prendre avec mdmaiga.**
- `agents.forms.TelephoneOrUsernameLoginForm` (`agents/forms.py:53`) — copie strictement identique
  de `core.forms.TelephoneOrUsernameLoginForm` (`core/forms.py:43`), jamais importée nulle part
  (`agents/views.py:82` importe explicitement la version `core`). **Suppression recommandée**, sans
  risque.
  - Note : l'audit d'origine signalait aussi `MultiFileInput`/`MultiFileField` comme dupliqués à
    l'identique entre les deux fichiers (`agents/forms.py:37,40` vs `core/forms.py:27,30`) — **non
    revérifiés dans cette passe** (hors du périmètre de la vérification du 12/08), à confirmer au
    moment de coder avant de les traiter de la même façon.

### A3. Doublon de routes `toutes_les_dettes` / `tous_les_bonus`

`core/urls.py` déclare toujours les deux noms deux fois (lignes actuelles 55-56 et 101-102) :

```python
path('admin/dettes/', views.toutes_les_dettes, name='toutes_les_dettes'),      # injoignable via {% url %}
path('admin/bonus/', views.tous_les_bonus, name='tous_les_bonus'),             # injoignable via {% url %}
...
path('direction/analyses/dettes', views.toutes_les_dettes, name='toutes_les_dettes'),  # gagne le reverse()
path('direction/analyses/bonus', views.tous_les_bonus, name='tous_les_bonus'),         # gagne le reverse()
```

Le premier chemin de chaque paire (`admin/...`) reste accessible en tapant l'URL directement, mais
`{% url %}` résout toujours vers le second. **Correction recommandée** : supprimer les deux
`path()` `admin/dettes/`/`admin/bonus/` si `direction/analyses/...` est bien la route voulue
(aucune fonctionnalité perdue, juste une route en double retirée) — à confirmer que rien ne dépend
d'un accès direct à `admin/dettes/`/`admin/bonus/` en dur (lien externe, favori, etc.) avant de
supprimer.

---

## Partie B — Duplication de logique vivante (nécessite une décision)

Contrairement à la Partie A, ces vues sont **toutes actives des deux côtés** — les supprimer sans
choisir la cible casserait une fonctionnalité utilisée.

### B1. Distribution lot → agent : 4 chemins vivants (était 3 lors de l'audit de juillet)

| Vue | App | Statut |
|---|---|---|
| `distribuer_produits_agent` | `core/views.py:619` | Active |
| `distribuer_lot_agent` | `agents/views.py:284`, marquée `# deprecier` depuis juillet | **Toujours le bouton principal** « Nouvelle Distribution » de `core/templates/core/distribution/liste_distributions.html:17` — dépréciation annoncée mais jamais suivie d'effet, usage réel confirmé |
| `distribution_superviseur` | `agents/views.py:363` | Présentée comme le remplaçant recommandé (`agents/APP_AGENT.md`) |
| `vente.creer_distribution` | `vente/views.py:32` | **Nouveau depuis l'audit** — introduit par l'app `vente`, non documenté dans `vente/APP_VENTE.md` comme chevauchant les 3 précédents |

**Décision à prendre avec mdmaiga** : quel chemin devient la cible unique, et dans quel ordre
retirer les 3 autres (en commençant a minima par changer le bouton de
`liste_distributions.html:17`, qui pousse activement les utilisateurs vers la version marquée
dépréciée).

### B2. Enregistrement de vente : 3 implémentations vivantes

| Vue | App | Statut |
|---|---|---|
| `enregistrer_vente` | `core/views.py:1070` | Toujours liée depuis `core/templates/base.html:430` pour le rôle agent terrain |
| `vente_distribution_rapide` | `agents/views.py:851`, routée `agents/urls.py:28-32` | **Routée mais jamais référencée par aucun template du repo** — candidate à la suppression pure, à vérifier qu'aucun appel direct (lien externe, JS) n'existe avant de la retirer |
| `vente:enregistrer_vente` | `vente/views.py:84` | Liée depuis `core/templates/base.html:495-496` pour le rôle superviseur |

`agents.vente_distribution_rapide` ressemble à du code mort en pratique (routée, jamais cliquée nulle
part dans l'UI actuelle) — à confirmer avant suppression (recherche plus large que les templates :
API mobile, tâches planifiées, etc.). Au-delà de ce cas, `core.enregistrer_vente` et
`vente:enregistrer_vente` restent **deux implémentations actives du même geste métier pour des
rôles différents** (agent terrain vs superviseur) — recommandation de l'audit d'origine toujours
valable : auditer que les deux appliquent les mêmes règles de calcul/validation, sinon risque de
résultat incohérent selon le rôle qui vend.

### B3. Autres paires dupliquées confirmées toujours actives (sans changement depuis juillet)

Vérifiées individuellement le 12/08 — toutes encore routées et actives des deux côtés, aucune
fusionnée :

- Liste des distributions : `liste_distributions` (core) / `liste_distribution_sup` (agents)
- Détail d'une distribution : `detail_distribution` (core) / `detail_distribution_sup` (agents)
- Recouvrement : `creer_recouvrement` (core, dette d'un agent) / `recouvrer_superviseur` (agents,
  cash d'un superviseur) — **périmètres différents**, pas un doublon strict, mais logique de
  recouvrement dupliquée entre les deux ; distinct du sujet traité au sprint-07 (qui porte sur la
  collecte gestionnaire/direction/ROT, pas sur ce recouvrement agent-niveau)
- Détail agent / KPI : `vue_detail_agent` (core) / `detail_agent_sup` + `detail_agent_rot` (agents)
  — 3 vues affichant des KPI d'agent, calculs potentiellement recalculés séparément
- Liste d'agents : `liste_agents_recouvrement` (core) / `liste_agents_sup` + `liste_agents_rot`
  (agents)

**Décision à prendre avec mdmaiga**, vue par vue : lesquelles fusionner/retirer, dans quel ordre de
priorité (suggestion : traiter B1/B2 d'abord, ce sont les points d'entrée les plus visibles/cliqués
au quotidien ; B3 en second temps, plus profond et à plus faible visibilité utilisateur).

### B4. Champs legacy déjà neutralisés (dette documentée, pas nettoyée)

- `core/models.py:2414` — `PaiementFournisseur.superviseur`, `verbose_name="Superviseur
  (déprécié – ancienne logique)"`. Plus jamais écrit par le code actif (`core/forms.py:414-421`
  écrit exclusivement `effectue_par`), mais le champ existe toujours en base.
- `VersementBancaire.superviseur` (`core/models.py:2057-2078` selon `finance/APP_FINANCE.md:97,346`)
  — même schéma, documenté indépendamment par l'équipe `finance` sans lien vers cet audit `core` (les
  deux dettes ont été identifiées séparément, signe qu'aucun des deux audits ne s'est vu).

**Décision à prendre avec mdmaiga** : retirer ces champs par migration maintenant (nettoyage complet,
mais touche la base de données), ou les laisser tels quels (documentés comme legacy, neutralisés,
sans risque tant que rien ne les relit) — option la plus prudente à court terme, dans la même
logique que la priorité déjà actée au ship plutôt qu'au durcissement/nettoyage proactif tant que le
modèle métier n'est pas stable (sprint-06, « Suggestions complémentaires » point 1).

---

## Partie C — Constats structurels (hors exécution de ce sprint, sauf accord explicite)

### C1. Absence de namespace sur `core`/`agents`/`direction`/`paie`

Confirmé toujours vrai, et le contraste s'accentue : les 3 apps « business capability » créées
depuis l'ADR-001 (`marchandise`, `vente`, `finance`) ont **toutes** un namespace explicite dès leur
création, mais `core`/`agents`/`direction`/`paie` n'en ont toujours pas. C'est cette absence qui a
permis la résolution silencieuse du point A1 (`'dashboard'`) — preuve concrète du risque déjà
signalé par l'audit.

Corriger ceci proprement (ajouter `app_name` + `namespace=` dans `dams/urls.py`) impose de
préfixer **tous** les `{% url '...' %}` de ces 4 apps dans **tous** les templates du repo (y
compris ceux d'autres apps qui référencent leurs URLs sans préfixe, ex. `agents/templates/...`
pointant vers des URLs `core`) — chantier au périmètre large, à fort risque de régression si fait
partiellement. **Recommandation : traiter dans un sprint dédié, avec une passe de vérification
exhaustive des `{% url %}` avant/après (grep systématique), pas en même temps que le nettoyage de
code mort de ce sprint.**

### C2. ADR-001 désynchronisée de la réalité livrée

`docs/decisions/001-business-capability-apps.md` (tableau « Prochaines capacités à créer », lignes
117-124) liste `finance` et `distribution` comme *futures*. En réalité :

- `finance` a bien été créée (conforme à l'ADR).
- Le périmètre que l'ADR attribuait à `distribution` (« Qui vend quoi, à qui, à quel prix ? ») a
  été livré sous le nom **`vente`** — un renommage de facto, jamais reporté dans l'ADR.
- `bi` et `monitoring` ont été ajoutées sans être positionnées par rapport au principe de l'ADR
  (probablement transverses — reporting/alerting — donc pas nécessairement des « capacités métier »
  au sens strict, mais l'ADR ne le dit pas).

Correction proposée, **faible risque, purement documentaire** (peut être faite dans ce sprint sans
attendre de décision d'architecture) : mettre à jour le tableau de l'ADR pour refléter l'état
livré, et ajouter une note sur `bi`/`monitoring`. Ne rouvre pas la question d'une future app
`distribution` (hors périmètre, comme convenu).

---

## Ordre suggéré

1. **Partie A** (A1, A2, A3) — aucun choix de comportement à faire, exécutable directement.
2. **C2** — mise à jour documentaire de l'ADR, indépendante et sans risque, peut être faite en
   même temps que A.
3. **Partie B** — dès que mdmaiga a tranché quel chemin devient la cible pour B1 (distribution) et
   B2 (vente), qui sont les plus visibles au quotidien ; B3 et B4 en suivant, à un rythme plus libre.
4. **C1** — sprint séparé, dédié, avec sa propre validation.

## Hors périmètre de ce sprint (sauf demande explicite contraire)

- Toute proposition de nouvelle app `distribution` ou de refonte du découpage en apps (ADR-001) —
  périmètre volontairement exclu à la demande de mdmaiga (12/08/2026).
- L'introduction de namespaces (C1) — chantier séparé.
- Toute règle de calcul métier (ventes, recouvrement) au-delà du simple constat de duplication —
  l'audit des règles elles-mêmes (B2) est une tâche à part, pas un simple renommage/suppression.

## Prochaine étape

Faire trancher à mdmaiga : (a) le sort de `core.views.supprimer_agent` (A2), (b) le chemin cible
pour la distribution (B1) et la vente (B2), (c) le sort des champs legacy (B4). Une fois ces
décisions actées, exécuter la Partie A + C2 en premier (aucune décision requise), puis la Partie B
dans l'ordre tranché. Mettre à jour `core/APP_CORE.md` et `agents/APP_AGENT.md` (ou équivalents)
dans la même session que chaque changement, conformément à la règle « Après avoir codé » de
`CLAUDE.md`.

Une fois le sprint clos, deux mises à jour documentaires restent à faire, distinctes des
`APP_*.md` :

- `docs/decisions/001-business-capability-apps.md` — appliquer la correction du Constat C2 (tableau
  « Prochaines capacités à créer » remis à jour : `finance` livrée, `distribution` livrée sous le
  nom `vente`, note sur `bi`/`monitoring`).
- `docs/audit/audit-app-core.md`, `docs/audit/audit-app-agents.md`,
  `docs/audit/comparaison-core-vs-agents.md` — actuellement marqués « créé, non lu / non approuvé » ;
  une fois les points de ce sprint traités, mettre à jour leur statut en tête de fichier (traité /
  partiellement traité / écarté) pour chaque constat repris ici, afin qu'ils ne restent pas
  indéfiniment à l'état de brouillon alors que leur contenu aura été agi.
