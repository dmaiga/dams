# Sprint 09 — Notes d'architecture pour une évolution ERP (au-delà du nettoyage)

**Statut** : 📋 notes ouvertes, non tranchées — observations de Claude issues de la lecture du code
pendant les sprints 07 et 08 (12/08/2026). Aucune n'est urgente ni décidée : ce document est à
lire, discuter, garder ou écarter librement, comme la section « Suggestions complémentaires » du
sprint-06.

## Contexte

À la différence du sprint-08 (dette technique ponctuelle : code mort, liens cassés, doublons de
vues), ce sprint capture des observations plus structurelles, faites en lisant `core`, `finance`,
`agents`, `monitoring`, `surveillance` et l'intégration avec `dams_agro` (via `analyse_champ`) —
des points qui n'empêchent rien aujourd'hui, mais qui comptent si DAMS doit devenir un véritable
ERP évolutif (plus de capacités métier, plus de charge, plus d'acteurs) plutôt que rester l'outil
actuel, dimensionné pour une équipe très restreinte.

---

## 1. 🔴 Le calcul du solde superviseur reste dupliqué à 4 endroits — c'est le risque le plus grave du lot

`finance/APP_FINANCE.md` le documente déjà lui-même : un calcul « dispersé et incohérent sur au
moins quatre endroits » (`Agent.solde_*` dans `core/models.py`, `direction/services/cloture_service.py`,
`agents/services/rot_dashboard_service.py`, et la nouvelle formule officielle
`finance/services.py::solde_superviseur`). `finance` se veut la source de vérité, mais les 3 autres
formules n'ont pas été dépréciées ni supprimées — elles restent lues par du code actif
(`agents.recouvrer_superviseur` s'appuie encore sur `RotDashboardService`, pas sur `finance`).

Contrairement aux doublons de *vues* traités au sprint-08 (qui affichent la même chose deux fois),
ici deux endroits différents peuvent **afficher un solde différent pour la même personne au même
moment**, selon l'écran consulté. Sur un ERP qui gère de l'argent, c'est le type de divergence qui
mine la confiance des utilisateurs le plus vite — pire qu'un lien cassé ou une page en double.

**Piste** : avant même de traiter le sprint-08, faire de `finance.solde_superviseur` la source
unique lue par *tous* les écrans (y compris `agents.recouvrer_superviseur`/`RotDashboardService`),
et retirer ou geler explicitement les 3 autres calculs (`Agent.solde_reel_superviseur`,
`solde_transitoire_superviseur`, `solde_operationnel_superviseur`, `cash_disponible_superviseur`,
`solde_rot` dans `core/models.py`) plutôt que les laisser coexister indéfiniment « au cas où ».

## 2. Aucun test automatisé sur les flux financiers

`finance/tests.py` est vide — aucun test sur `solde_superviseur`, `solde_caisse_globale`, ni sur la
synchronisation avec `dams_agro` (`synchroniser_engagements_champ`, sprint-06 Constat 1). Un ERP,
par nature, encaisse de plus en plus de flux au fil de sa croissance ; sans filet de tests sur ces
calculs, chaque changement futur (y compris les sprints 07/08 eux-mêmes) est un pari sur la
non-régression, vérifié seulement à l'œil par mdmaiga.

**Piste** : pas besoin d'une couverture exhaustive tout de suite — un noyau de tests de
non-régression ciblé sur `finance/services.py` (les formules de solde, avant/après un
`RecouvrementSuperviseur`/`VersementBancaire`/`RemboursementChamp`) donnerait le filet le plus utile
pour le rapport effort/risque, avant d'élargir. Cohérent avec le point 3 déjà noté (non tranché) au
sprint-06.

## 3. La frontière avec `dams_agro` se construit au cas par cas, pas comme un mécanisme réutilisable

`analyse_champ` est le seul point de contact avec `dams_agro`, et c'est une bonne discipline déjà en
place (API_URL, lecture seule, `dams_agro` comme « contrat figé » jamais modifié). Mais le seul
mécanisme de synchronisation qui existe (réconciliation des engagements, sprint-06 Constat 1) a été
conçu **spécifiquement** pour ce besoin précis (déclenché au clic sur un lien précis, scope à un
superviseur). Si demain un autre domaine a besoin d'apprendre un fait survenu côté `dams_agro` (un
mouvement de stock au champ, un statut d'agent, etc.), il faudra probablement réinventer le même
genre de mécanisme depuis zéro plutôt que réutiliser quelque chose d'existant.

**Piste, à horizon d'un futur besoin réel (pas maintenant)** : si un deuxième cas de synchronisation
se présente, en profiter pour extraire un petit service générique (« interroger dams_agro, comparer
à l'état local, combler l'écart ») dans `analyse_champ/services.py`, plutôt que dupliquer le motif
de `synchroniser_engagements_champ` une deuxième fois. Pas de sur-ingénierie tant qu'il n'y a qu'un
seul cas d'usage — juste un point à garder en tête pour ne pas le refaire ad hoc une deuxième fois.

## 4. Les modèles restent tous concentrés dans `core` (contrainte assumée par l'ADR-001)

L'ADR-001 le dit explicitement : les modèles restent dans `core` par choix pragmatique (coût de
migration trop élevé pour un gain immédiat), et les nouvelles apps « capacité métier »
(`marchandise`, `vente`, `finance`) importent `core.models` sans les posséder. C'est raisonnable à
l'échelle actuelle, mais chaque nouvelle capacité ajoute une dépendance de plus sur un `core`
toujours plus gros et jamais réellement démembré (`core/views.py` fait encore ~2850 lignes malgré 3
apps censées avoir repris une partie de son périmètre). Si DAMS continue à ajouter des capacités
(achats fournisseurs, RH au-delà de `paie`, etc.), `core` restera le goulot d'étranglement — pas
bloquant aujourd'hui, mais la contrainte de l'ADR mérite d'être revue explicitement le jour où une
nouvelle capacité importante est envisagée, plutôt que reconduite par défaut indéfiniment.

## 5. Permissions par capacité, mais réinventées à chaque app plutôt que centralisées

L'ADR-001 documente le bon principe (`_acces_stock`, une fonction par capacité plutôt qu'un check
par personne) — bien appliqué (`_acces_finance`, `_acces_depense`, `_acces_engagement_champ` dans
`finance/views.py`, `_acces_stock` dans `marchandise`). Mais chaque app réécrit sa propre petite
fonction locale, avec son propre nom, sans registre commun. Fonctionne bien à 5 capacités ; devient
plus dur à auditer globalement (« qui a accès à quoi ? ») si l'ERP grandit à 10-15 capacités.

**Piste, pas urgente** : le jour où auditer les permissions capacité par capacité devient pénible,
envisager un petit registre centralisé (ex. `core/permissions.py` avec une fonction par capacité,
importée par chaque app plutôt que redéfinie) — pas un système de rôles complexe, juste éviter la
duplication de la même logique `_acces_xxx` copiée-collée d'une app à l'autre.

## 6. Un seul canal d'alerte, synchrone, sans file d'attente

`monitoring` envoie uniquement via Telegram (`TelegramProvider`), appelé de façon synchrone depuis
une commande de management (`evaluer_alertes`, elle-même déclenchée par une tâche planifiée du
système, pas par une infra de queue comme Celery — choix assumé, documenté dans le sprint-06,
Constat 1 : « pas d'infra Celery dans ce repo »). Raisonnable au volume actuel. Si l'ERP ajoute
d'autres canaux (SMS, email) ou que le volume d'alertes grandit, l'absence de file d'attente/retry
deviendra plus sensible (un `TelegramProvider.send` qui échoue silencieusement, cf. son
`try/except` large, ne sera jamais rejoué).

**Piste, à horizon du jour où un deuxième canal est demandé** : pas la peine d'introduire Celery
pour un seul canal qui fonctionne ; mais si un deuxième provider s'ajoute, c'est le bon moment pour
introduire une vraie file (même simple, en base) plutôt que d'empiler les canaux de façon
synchrone dans le même appel.

---

## Ce que ces observations n'incluent volontairement pas

- Aucune proposition de découpage en microservices ou de séparation d'infrastructure — l'échelle
  actuelle (une équipe très restreinte, un seul serveur) ne le justifie pas, et ce n'est pas
  cohérent avec la posture déjà actée : priorité au ship, pas de durcissement/architecture
  proactive avant que le modèle métier soit stable (sprint-06, « Suggestions complémentaires »
  point 1).
- Aucune ré-ouverture du découpage `marchandise`/`vente`/`finance` vs `core`/`agents` — c'est
  exactement le sujet du sprint-08, volontairement tenu séparé de ce document.
- Aucune modification proposée côté `dams_agro` — rappel de la règle déjà actée (sprint-06) : c'est
  un contrat figé, aucune évolution n'y est possible depuis ce repo.

## Prochaine étape

Aucune — ce document attend une lecture et un tri de mdmaiga (garder, écarter, ou reformuler en
tâches concrètes pour un futur sprint), comme convenu. Le point 1 (solde superviseur dupliqué) est
celui que Claude recommande de prioriser en premier si un seul de ces points devait être retenu —
c'est le seul des six à toucher directement la fiabilité de l'argent affiché aux utilisateurs.
