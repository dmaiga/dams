# APP_MONITORING.md

## Rôle

`monitoring` est une **capacité transverse** (au sens de `rules/ARCHITECTURE.md`) : elle ne possède aucun
modèle métier propre et n'importe/n'appelle que des services d'autres apps. C'est le moteur centralisé
issu du Sprint 05 / Chantier 3 (`docs/sprints/sprint-05.md`) qui unifie l'historisation, la déduplication
et la diffusion des alertes métier de surveillance, jusqu'ici dispersées et calculées à la demande dans
leurs dashboards respectifs (`finance`, `surveillance`).

Depuis la refonte du 2026-08-13 (affinée le 24/09/2026, demande mdmaiga), chaque règle diffuse un ou
plusieurs messages Telegram par évaluation (`AlerteMoteur`, `type_alerte`) — soit un seul message
regroupant tous les superviseurs, soit un message distinct par superviseur, selon la règle :

1. **Solde superviseur** (`solde` — reste **un seul message** listant tous les superviseurs en alerte,
   `info` ; demande explicite du 24/09/2026 de conserver ce regroupement) et **solde persistant**
   (`solde_persistant` — reste une alerte individuelle par superviseur, `critique`, anomalie après 3
   cycles de remise consécutifs sans résorption).
2. **Stock ancien**, un message par origine, et par superviseur pour les deux dernières :
   - `stock_entrepot` — lots dormants à l'entrepôt central (> 15 jours), un seul message (pas de notion
     de superviseur à ce niveau). `reenvoi_heures=None` (envoi unique ; l'entrepôt se vide/re-remplit,
     donc l'alerte se résout puis se recrée naturellement).
   - `stock_superviseur` — stock en rétention chez un superviseur (> 3 jours) : **un message Telegram
     distinct par superviseur** (clé d'identification `superviseur=superviseur.user`), depuis le
     24/09/2026 (avant : un seul message listant tous les superviseurs).
   - `stock_agent` — stock en rétention chez un agent de vente (> 3 jours) : **un message distinct par
     superviseur**, listant ses propres agents (même refonte du 24/09/2026).
   - `stock_superviseur` / `stock_agent` : `reenvoi_heures=24` (quotidien depuis le 24/09/2026, était 48h
     depuis le 08/09/2026/sprint-12). Ces listes ne retombent jamais à zéro, donc l'alerte ne se résout
     jamais — sans rappel, un seul message était envoyé le jour de sa création puis plus rien. Chaque
     ligne produit est rendue par le helper commun `moteur_alerte._ligne_stock` : `• {produit} — reste
     {quantité} — reçu le {date} — {jours} j` (même niveau de détail que la commande
     `agents_stock_dormant`).
3. **Ventes sous la marge minimale** (`prix` — vente comme référence, pas le lot, un seul message groupé
   par superviseur puis par agent ; marge < `surveillance.constants.SEUIL_MARGE_MINIMALE`, 45 FCFA).
   Non concernée par la refonte du 24/09/2026 (hors périmètre de la demande).
3bis. **Ventes à prix suspect** (`prix_ecart_achat`, ajouté le 24/09/2026) — même structure de message
   qu'au point 3 (un seul message, groupé par superviseur puis par agent), mais détecte l'anomalie
   inverse : un prix de vente dépassant `prix_achat_unitaire + surveillance.constants.
   SEUIL_ECART_PRIX_ACHAT` (2500 FCFA). La règle `prix` ne couvre que les prix trop **bas** (marge
   négative) — un superviseur qui saisit 130000 FCFA au lieu de 12000 (un zéro de trop) a une marge
   largement positive et ne déclenche jamais `prix`. `reenvoi_heures=None` (même convention que
   `prix` : notification unique, silence tant que l'`Alerte` reste ACTIVE). Seuil fixe volontairement
   simple — une vraie fourchette de prix acceptable par produit serait plus juste mais jugée trop
   difficile à établir pour l'instant (variation de marché, marge de négociation réelle).
4. **Baisse d'activité commerciale** (`activite`) — dernière vente **valide et globale** de l'agent
   (tous lots confondus), décorrélée du stock/lot, seuil
   `surveillance.constants.DELAI_ACTIVITE_COMMERCIALE_JOURS` (3 jours, inchangé — seul le seuil de
   `stock_superviseur`/`stock_agent` avait été proposé à la révision, pas celui-ci). **Un message
   distinct par superviseur** depuis le 24/09/2026 (clé `superviseur=superviseur.user`) ; les agents
   sans superviseur assigné reçoivent leur propre message à part, identifié par `superviseur=None`
   plutôt que rattachés à une section du message d'un superviseur. `reenvoi_heures=24` (était 48h).

Le modèle `Alerte` reste défini dans `core/models.py` (contrainte structurelle du repo, cf.
`rules/ARCHITECTURE.md`), avec un cycle de vie (`statut`, `date_resolution`, `date_dernier_envoi`,
`nombre_envois`) et des FK de lien objet (`superviseur`, `agent`, `lot`, `produit`, `distribution`) —
**non renseignées** par les règles agrégées (voir « Convention de déduplication » ci-dessous), elles
restent utiles pour `solde_persistant` (toujours par superviseur) et pour l'admin Django.

---

## Frontières

| Ce que l'app possède | Ce qu'elle ne touche pas |
|---|---|
| `AlerteDeduplicationService` — création/renvoi/clôture des `Alerte` | Les modèles métier de `finance`/`surveillance`/`vente` — lecture seule sur leurs services |
| `AlerteMoteur` — les règles d'évaluation et la construction des messages agrégés | Les points de mutation existants (`vente`, `recouvrement`, `versement`) — aucun signal, aucun appel synchrone injecté ailleurs |
| `TelegramProvider` (opérationnel, bot `@dams_agro_bot`) | Toute règle de calcul métier (solde, marge) — déléguée à `finance`/`surveillance` |
| La commande `evaluer_alertes` | Toute vue ou template — hors périmètre MVP |

---

## Architecture

```
monitoring/constants.py                       # ALERTES_MVP : reenvoi_heures par type_alerte, DESCRIPTIONS_ALERTES : texte métier par type_alerte
monitoring/services/deduplication_service.py  # AlerteDeduplicationService (get_ou_creer / cloturer_si_resolue)
monitoring/services/moteur_alerte.py          # AlerteMoteur : une méthode par règle + construction des messages
monitoring/providers/telegram.py              # TelegramProvider
monitoring/management/commands/evaluer_alertes.py  # commande périodique (tâche planifiée OS)
```

Chaque méthode d'`AlerteMoteur` :
1. Lit une source réelle existante (`finance.services.lister_soldes_superviseurs`,
   `surveillance.services.stock_age_service.StockAgeService`,
   `surveillance.services.prix_service.PrixSurveillanceService.ventes_sous_marge_minimale`) — jamais
   de requête ORM dupliquée.
2. Regroupe les situations en mémoire (`_grouper_par_superviseur`, `moteur_alerte.py`).
3. Construit un message par situation à notifier — **soit un seul message agrégé pour toute la
   thématique** (`solde`, `stock_entrepot`, `prix`), **soit un message par superviseur**
   (`stock_superviseur`, `stock_agent`, `activite`, `solde_persistant` — refonte du 24/09/2026 pour ces
   trois premiers, `solde_persistant` déjà ainsi depuis le sprint-05).
4. Appelle `AlerteDeduplicationService.get_ou_creer(type_alerte, defaults={...}, **cles)` — `cles` est
   vide pour les règles à message unique (il n'existe alors jamais qu'une seule `Alerte` ACTIVE par
   `type_alerte`), ou `superviseur=superviseur.user` (voire `superviseur=None` pour les agents sans
   superviseur assigné, règle `activite`) pour les règles à message par superviseur — une `Alerte`
   ACTIVE par `(type_alerte, superviseur)`.
5. Notifie via `TelegramProvider.send(alerte)` uniquement si `doit_envoyer` est vrai — un appel par
   message construit, donc potentiellement plusieurs appels Telegram par règle si elle est segmentée
   par superviseur.
6. Appelle `AlerteDeduplicationService.cloturer_si_resolue(type_alerte, situations_actives)` —
   `situations_actives` est `[{}] if <encore actif> else []` pour les règles à message unique
   (convention minimaliste : `[{}]` signifie "toujours quelque chose à signaler, ne pas clôturer" ;
   `[]` signifie "plus rien à signaler, clôturer l'unique Alerte ACTIVE de ce type"), ou la liste des
   `{"superviseur": ...}` encore actifs pour les règles segmentées (clôture individuellement les
   `Alerte` des superviseurs redevenus sains, sans toucher aux autres).

Déclenchement : appels directs uniquement, **pas de signal Django** — une seule commande de management
(`evaluer_alertes`) évalue toutes les règles à chaque exécution, à invoquer via tâche planifiée OS (voir
`rules/STACK.md`). La règle "solde" exige un horaire matinal (6h-7h), avant l'action groupée quotidienne
`finance:recouvrement_versement_groupe`.

---

## Points de vigilance

- **`TelegramProvider` est opérationnel** (bot `@dams_agro_bot`, credentials en `.env`). En l'absence de
  `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, le provider repasse automatiquement en mode stub (log
  uniquement, `logging` niveau INFO, logger `monitoring.telegram`), sans changer la signature de
  `TelegramProvider.send(alerte)`. `monitoring/tests.py` mocke systématiquement `requests.post` pour ne
  jamais déclencher de vrai envoi pendant les tests.
- `finance.services.DATE_DEBUT_FINANCE` reste au 2026-08-01 (date de bascule réelle) : les règles
  "solde"/"solde_persistant" ne produiront donc aucune alerte tant que cette date n'est pas atteinte
  — `lister_soldes_superviseurs()` renvoie un solde nul par construction avant cette date (voir
  `finance/APP_FINANCE.md`).
- Un échec de `TelegramProvider.send()` ne remonte **jamais** d'exception à l'appelant (US-05) : le
  `try/except` large dans le provider garantit que l'évaluation des règles suivantes n'est jamais
  interrompue.
- La règle `solde_persistant` nécessite d'historiser, pour chaque superviseur, le solde constaté juste
  après chacun de ses 3 derniers `RecouvrementSuperviseur` — logique de comptage propre à `monitoring`
  (`finance.services` reste un calculateur pur, sans historisation).
- `date_recouvrement` (`RecouvrementSuperviseur`) reflète le cycle métier réel même en cas de saisie
  différée (ex. bordereau du samedi saisi le lundi) : le tri par `-date_recouvrement` (pas
  `date_creation`) est le bon critère pour identifier "les 3 derniers cycles".
- Aucune vue, aucun template : l'exploitation UI (filtres, "alertes résolues cette semaine") est
  explicitement hors MVP (`docs/BACKLOG.md` § Chantier 3).

---

## Refonte des règles — 2026-08-13

### Bug corrigé : activité commerciale mélangée avec l'ancienneté du lot

L'ancien calcul (`StockAgeService.agents_sans_vente_recente()`, avant refonte) évaluait, **pour chaque
`DetailDistribution`**, si la dernière vente *sur ce lot* datait de plus de 5 jours. Un agent avec
plusieurs distributions pouvait donc être signalé « sans vente » à cause d'une vieille distribution sans
vente sur *elle-même*, alors qu'il avait vendu récemment sur un lot plus récent — c'est le bug observé
en production (« Telegram signale un agent sans vente depuis 5 jours alors qu'il a vendu récemment »).

Le nouveau calcul (`surveillance/services/stock_age_service.py`) prend la dernière vente **valide et
globale** de l'agent, tous lots confondus (`Agent.objects.annotate(derniere_vente=Max('vente__date_vente',
filter=Q(vente__est_supprime=False)))`), et compare au seuil
`DELAI_ACTIVITE_COMMERCIALE_JOURS = 3` (`surveillance/constants.py`). Voir
`surveillance/APP_SURVEILLANCE.md` § Suivi Durée de Vie du Stock pour le détail complet (population,
requête, garde-fous).

### Marge minimale : source unique et vente comme référence

`PrixSurveillanceService.SEUIL_MARGE_MINIMALE` (utilisé par `evaluer_variation_prix`) importait
auparavant une valeur locale (45 FCFA) redéfinie indépendamment de `surveillance.constants.
SEUIL_MARGE_MINIMALE` (déclarée mais jamais utilisée) — corrigé, les deux services de prix
(`prix_service.py` et `surveillance_prix_service.py`, dette de duplication documentée mais non
résorbée) importent désormais cette constante unique (valeur actuelle : 45 FCFA, décision mdmaiga
du 13/08/2026 — un essai à 25 FCFA a été testé le même jour puis écarté). La comparaison est passée
de `<=` (marge ≤ seuil = anomalie) à `<` stricte (marge < seuil = anomalie) : une vente exactement au
seuil n'est plus une anomalie.

`evaluer_variation_prix` utilise une nouvelle méthode dédiée,
`PrixSurveillanceService.ventes_sous_marge_minimale()` — une ligne par **vente** (pas par lot agrégé
comme `ventes_a_perte()`, qui reste utilisée telle quelle par le dashboard `surveillance` et n'a pas
besoin de ce regroupement), groupée par superviseur puis par agent pour la construction du message.

### Stock ancien : trois origines, seuils différenciés

`StockAgeService.lots_stock_dormant()` distingue maintenant trois origines avec des seuils propres
(entrepôt 15j inchangé, superviseur et agent 3j chacun — était 15j pour le superviseur ; seuils
volontairement laissés à 3j lors de la révision du 24/09/2026, distincts des 7j de la checklist
`direction.suivi_distributions`) — voir `surveillance/APP_SURVEILLANCE.md` pour le détail.
`evaluer_stock_ancien` répartit les lignes par `origine` ; `stock_entrepot` reste un message unique,
`stock_superviseur`/`stock_agent` envoient désormais un message par superviseur (24/09/2026, au lieu
d'un message unique mélangeant tous les superviseurs) pour rester lisible.

### `core.models.Alerte.TYPES` — migration `0115_alter_alerte_type_alerte`

`type_alerte="stock"` est remplacé par trois valeurs (`stock_entrepot`/`stock_superviseur`/
`stock_agent`) ; `"prix"` et `"activite"` gardent leur clé mais un libellé mis à jour. `choices` n'étant
pas contraint au niveau SQL par Django, la migration ne touche que la définition du champ (`AlterField`),
aucune donnée existante n'est modifiée — d'anciennes `Alerte` avec `type_alerte="stock"` resteraient
lisibles telles quelles si elles existent encore en base, simplement hors des nouveaux choix affichés
par l'admin.

## Description métier dans le corps des messages (24/09/2026)

Chaque message Telegram inclut désormais, juste sous le titre, une courte description en
langage métier de ce que signifie l'alerte et de sa fréquence d'envoi —
`monitoring.constants.DESCRIPTIONS_ALERTES`, une entrée par `type_alerte`. Objectif : que le
message reste compréhensible pour un destinataire externe à l'équipe technique (ex. un
superviseur en chef), sans qu'il ait besoin du code ou de la documentation pour l'interpréter.
Ce texte est volontairement rédigé sans référence aux décisions internes (dates de décision,
noms, numéros de sprint) — contrairement aux commentaires de code, qui restent le lieu du
contexte interne. Toute modification d'un seuil (`SEUIL_MARGE_MINIMALE`, `SEUIL_ECART_PRIX_ACHAT`,
`DELAI_*`) doit être répercutée dans la description correspondante pour ne pas la rendre inexacte.

## Ce qui n'a volontairement pas changé (au 24/09/2026)

- **`solde`** reste un seul message listant tous les superviseurs en alerte — demande explicite de
  mdmaiga de conserver ce regroupement, à l'inverse de `stock_superviseur`/`stock_agent`/`activite`.
- **Le calcul du solde lui-même** (`finance.services.lister_soldes_superviseurs`/`solde_superviseur`)
  est inchangé.
- **`prix`** (ventes sous la marge minimale) reste un message unique groupé par superviseur puis par
  agent — hors périmètre de la demande du 24/09/2026, pas segmenté en messages par superviseur.
- **Les seuils** `DELAI_ACTIVITE_COMMERCIALE_JOURS` (3j) et `DELAI_RETENTION_ACTEURS_JOURS` (3j) sont
  restés inchangés — décision explicite de garder ces alertes comme un système d'alerte précoce,
  distinct de la checklist terrain à 7 jours de `direction.suivi_distributions`
  (`SEUIL_ATTENTION_JOURS`), plutôt que de les aligner.
- **`AlerteDeduplicationService.cloturer_si_resolue(..., champ_cle=...)`** reste inutilisé par
  `AlerteMoteur` (chaque type_alerte segmenté n'a qu'une seule famille de clés — `superviseur`, avec
  `None` pour les agents sans superviseur assigné sur `activite` — donc l'auto-détection des clés
  suffit), mais reste disponible et testé pour un futur type_alerte qui mélangerait plusieurs familles.
