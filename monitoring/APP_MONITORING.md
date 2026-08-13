# APP_MONITORING.md

## Rôle

`monitoring` est une **capacité transverse** (au sens de `rules/ARCHITECTURE.md`) : elle ne possède aucun
modèle métier propre et n'importe/n'appelle que des services d'autres apps. C'est le moteur centralisé
issu du Sprint 05 / Chantier 3 (`docs/sprints/sprint-05.md`) qui unifie l'historisation, la déduplication
et la diffusion des alertes métier de surveillance, jusqu'ici dispersées et calculées à la demande dans
leurs dashboards respectifs (`finance`, `surveillance`).

Depuis la refonte du 2026-08-13, chaque règle diffuse **un seul message Telegram par thématique et par
évaluation** (`AlerteMoteur`, `type_alerte`), regroupé en interne par superviseur/agent plutôt qu'un
message par situation individuelle :

1. **Solde superviseur** (`solde` — un seul message listant tous les superviseurs en alerte, `info`) et
   **solde persistant** (`solde_persistant` — reste une alerte individuelle par superviseur, `critique`,
   anomalie après 3 cycles de remise consécutifs sans résorption — hors périmètre du regroupement).
2. **Stock ancien**, trois messages distincts par origine :
   - `stock_entrepot` — lots dormants à l'entrepôt central (> 15 jours).
   - `stock_superviseur` — stock en rétention chez un superviseur (> 3 jours), groupé par superviseur.
   - `stock_agent` — stock en rétention chez un agent de vente (> 3 jours), groupé par superviseur puis
     par agent.
3. **Ventes sous la marge minimale** (`prix` — vente comme référence, pas le lot, groupé par
   superviseur puis par agent ; marge < `surveillance.constants.SEUIL_MARGE_MINIMALE`, 45 FCFA).
4. **Baisse d'activité commerciale** (`activite`) — dernière vente **valide et globale** de l'agent
   (tous lots confondus), décorrélée du stock/lot, seuil
   `surveillance.constants.DELAI_ACTIVITE_COMMERCIALE_JOURS` (3 jours). Groupé par superviseur ; les
   agents sans superviseur assigné apparaissent dans une section distincte du même message.

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
monitoring/constants.py                       # ALERTES_MVP : reenvoi_heures par type_alerte
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
2. Regroupe les situations en mémoire (`_grouper_par_superviseur`, `moteur_alerte.py`) et construit un
   **texte de message unique** pour toute la thématique.
3. Appelle `AlerteDeduplicationService.get_ou_creer(type_alerte, defaults={...})` **sans clé
   d'identification** (aucun `superviseur=`/`agent=`/`lot=` passé) — il n'existe donc jamais qu'une
   seule `Alerte` ACTIVE par `type_alerte` pour ces règles agrégées.
4. Notifie via `TelegramProvider.send(alerte)` uniquement si `doit_envoyer` est vrai.
5. Appelle `AlerteDeduplicationService.cloturer_si_resolue(type_alerte, [{}] if <encore actif> else [])`
   — convention volontairement minimaliste : `[{}]` signifie "toujours quelque chose à signaler, ne pas
   clôturer" ; `[]` signifie "plus rien à signaler, clôturer l'unique Alerte ACTIVE de ce type".

`solde_persistant` reste la seule règle à utiliser une clé d'identification par superviseur
(`superviseur=superviseur.user`), sur le modèle historique (sprint-05) — cf. « Ce qui n'a volontairement
pas changé » plus bas.

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
(entrepôt 15j inchangé, superviseur et agent 3j chacun — était 15j pour le superviseur) — voir
`surveillance/APP_SURVEILLANCE.md` pour le détail. `evaluer_stock_ancien` répartit les lignes par
`origine` et envoie un message distinct par origine (`stock_entrepot`/`stock_superviseur`/
`stock_agent`) plutôt qu'un message unique mélangeant les trois, pour rester lisible.

### `core.models.Alerte.TYPES` — migration `0115_alter_alerte_type_alerte`

`type_alerte="stock"` est remplacé par trois valeurs (`stock_entrepot`/`stock_superviseur`/
`stock_agent`) ; `"prix"` et `"activite"` gardent leur clé mais un libellé mis à jour. `choices` n'étant
pas contraint au niveau SQL par Django, la migration ne touche que la définition du champ (`AlterField`),
aucune donnée existante n'est modifiée — d'anciennes `Alerte` avec `type_alerte="stock"` resteraient
lisibles telles quelles si elles existent encore en base, simplement hors des nouveaux choix affichés
par l'admin.

## Ce qui n'a volontairement pas changé

- **`solde_persistant`** reste une alerte individuelle par superviseur (clé
  `superviseur=superviseur.user`), pas regroupée en un seul message — règle critique distincte, non
  mentionnée dans la demande de regroupement, laissée inchangée pour limiter le risque sur une alerte
  déjà `critique`.
- **Le calcul du solde lui-même** (`finance.services.lister_soldes_superviseurs`/`solde_superviseur`)
  est inchangé — seule la présentation (un message listant tous les superviseurs plutôt qu'un message
  par superviseur) a évolué.
- **`AlerteDeduplicationService.cloturer_si_resolue(..., champ_cle=...)`** (ajouté lors d'une itération
  précédente pour gérer des familles de clés hétérogènes sous un même `type_alerte`) n'est plus utilisé
  par les règles agrégées (elles n'utilisent plus aucune clé d'identification), mais reste disponible et
  testé — utile si `solde_persistant` devait un jour mélanger plusieurs familles de clés.
