# APP_MONITORING.md

## Rôle

`monitoring` est une **capacité transverse** (au sens de `rules/ARCHITECTURE.md`) : elle ne possède aucun
modèle métier propre et n'importe/n'appelle que des services d'autres apps. C'est le moteur centralisé
issu du Sprint 05 / Chantier 3 (`docs/sprints/sprint-05.md`) qui unifie l'historisation, la déduplication
et la diffusion des 4 alertes métier MVP, jusqu'ici dispersées et calculées à la demande dans leurs
dashboards respectifs (`finance`, `surveillance`) :

1. **Solde superviseur** (`solde` — réconciliation matinale routine, `info`) et **solde persistant**
   (`solde_persistant` — anomalie réelle après 3 cycles de remise consécutifs sans résorption, `critique`).
2. **Stock ancien** (`stock`) — lot/affectation dormant depuis > 14 jours.
3. **Variation prix** (`prix`) — vente sous le prix d'achat + marge minimale.
4. **Baisse d'activité** (`activite`) — agent sans vente depuis > 2 jours.

Le modèle `Alerte` reste défini dans `core/models.py` (contrainte structurelle du repo, cf.
`rules/ARCHITECTURE.md`), étendu ce sprint avec un cycle de vie (`statut`, `date_resolution`,
`date_dernier_envoi`, `nombre_envois`) et deux FK de lien objet (`lot`, `distribution`).

---

## Frontières

| Ce que l'app possède | Ce qu'elle ne touche pas |
|---|---|
| `AlerteDeduplicationService` — création/renvoi/clôture des `Alerte` | Les modèles métier de `finance`/`surveillance`/`vente` — lecture seule sur leurs services |
| `AlerteMoteur` — les 4 règles d'évaluation (5 avec `solde_persistant`) | Les points de mutation existants (`vente`, `recouvrement`, `versement`) — aucun signal, aucun appel synchrone injecté ailleurs |
| `TelegramProvider` (stub log) | L'appel HTTP réel à l'API Telegram (TODO explicite, cf. ci-dessous) |
| La commande `evaluer_alertes` | Toute vue ou template — hors périmètre MVP de ce sprint |

---

## Architecture

```
monitoring/constants.py                       # ALERTES_MVP : reenvoi_heures par type_alerte
monitoring/services/deduplication_service.py  # AlerteDeduplicationService (get_ou_creer / cloturer_si_resolue)
monitoring/services/moteur_alerte.py          # AlerteMoteur : 4 méthodes, une par source réelle
monitoring/providers/telegram.py              # TelegramProvider (stub)
monitoring/management/commands/evaluer_alertes.py  # commande périodique (tâche planifiée OS)
```

Chaque méthode d'`AlerteMoteur` :
1. Lit une source réelle existante (`finance.services.lister_soldes_superviseurs`,
   `surveillance.services.stock_age_service.StockAgeService`,
   `surveillance.services.prix_service.PrixSurveillanceService`) — jamais de requête ORM dupliquée.
2. Appelle `AlerteDeduplicationService.get_ou_creer(...)` pour chaque situation détectée.
3. Notifie via `TelegramProvider.send(alerte)` uniquement si `doit_envoyer` est vrai.
4. Appelle `AlerteDeduplicationService.cloturer_si_resolue(...)` avec la liste des situations
   encore actives lors du run courant, pour clôturer automatiquement celles qui ont disparu.

Déclenchement : appels directs uniquement (décision Q2 du sprint), **pas de signal Django** — une seule
commande de management (`evaluer_alertes`) évalue les 5 règles à chaque exécution, à invoquer via tâche
planifiée OS (voir `rules/STACK.md`). La règle "solde" (1a) exige un horaire matinal (6h-7h), avant
l'action groupée quotidienne `finance:recouvrement_versement_groupe`.

---

## Points de vigilance

- **`TelegramProvider` est opérationnel** (bot `@dams_agro_bot`, credentials en `.env` depuis le
  27/07/2026). En l'absence de `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, le provider repasse
  automatiquement en mode stub (log uniquement, `logging` niveau INFO, logger `monitoring.telegram`),
  sans changer la signature de `TelegramProvider.send(alerte)`. `monitoring/tests.py` mocke
  systématiquement `requests.post` pour ne jamais déclencher de vrai envoi pendant les tests.
- `finance.services.DATE_DEBUT_FINANCE` reste au 2026-08-01 (date de bascule réelle) : les règles
  "solde"/"solde_persistant" ne produiront donc aucune alerte tant que cette date n'est pas atteinte
  — `lister_soldes_superviseurs()` renvoie un solde nul par construction avant cette date (voir
  `finance/APP_FINANCE.md`).
- Un échec de `TelegramProvider.send()` ne remonte **jamais** d'exception à l'appelant (US-05) : le
  `try/except` large dans le provider garantit que l'évaluation des règles suivantes n'est jamais
  interrompue.
- La règle `solde_persistant` (1b) nécessite d'historiser, pour chaque superviseur, le solde constaté
  juste après chacun de ses 3 derniers `RecouvrementSuperviseur` — logique de comptage propre à
  `monitoring` (`finance.services` reste un calculateur pur, sans historisation).
- `date_recouvrement` (`RecouvrementSuperviseur`) reflète le cycle métier réel même en cas de saisie
  différée (ex. bordereau du samedi saisi le lundi) : le tri par `-date_recouvrement` (pas
  `date_creation`) est le bon critère pour identifier "les 3 derniers cycles".
- `StockAgeService.agents_sans_vente_recente()` ne renvoie pas d'objet `DetailDistribution`, seulement
  un `distribution_id` — `AlerteMoteur.evaluer_baisse_activite()` l'hydrate explicitement avant de
  renseigner `Alerte.distribution`.
- Aucune nouvelle variable `.env` tant que le bot Telegram n'existe pas.
- Aucune vue, aucun template : l'exploitation UI (filtres, "alertes résolues cette semaine") est
  explicitement hors MVP (`docs/BACKLOG.md` § Chantier 3).
