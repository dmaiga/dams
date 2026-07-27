# Sprint 05 — Chantier 3 : Moteur de surveillance métier (Business Monitoring Engine)

**Statut** : ✅ Terminé — les 5 volets sont livrés (app `monitoring`, modèle `Alerte` étendu, moteur d'évaluation, commande `evaluer_alertes`, 15 tests).

## Contexte

Chantier 3 du backlog (`docs/BACKLOG.md`) : DAMS produit aujourd'hui 3 sources d'alertes réelles, dispersées, non historisées et non diffusées au-delà de leur propre dashboard :

1. **Solde superviseur élevé** — `finance.services.solde_superviseur()` / `lister_soldes_superviseurs()` (`finance/services.py`), calculé à la demande dans `dashboard_finance`. Seuil : `SEUIL_ALERTE_SOLDE = 30 000 FCFA`, `solde > SEUIL_ALERTE_SOLDE` (mis à jour le 27/07/2026 ; `finance/APP_FINANCE.md` détaille la nuance métier ci-dessous).
2. **Stock ancien / baisse d'activité** — `surveillance.services.stock_age_service.StockAgeService` (Sprint 04, Chantier 2) : `lots_stock_dormant()`/`count_lots_stock_dormant()` et `agents_sans_vente_recente()`/`count_agents_sans_vente_recente()`, calculés à la demande dans `StockRotationView`.
3. **Variation prix** — `surveillance.services.prix_service.PrixSurveillanceService` : `ventes_a_perte()`/`count_anomalies()`, calculé à la demande dans `DashboardSurveillanceView`/`SurveillancePrixView`.

Aucune de ces trois sources n'est historisée, dédupliquée, ni diffusée ailleurs qu'à l'écran consulté au moment T. Le Chantier 3 crée le moteur centralisé qui unifie ce traitement pour 4 alertes MVP (les 3 ci-dessus, la 4ᵉ — baisse d'activité — étant la seconde sortie de `StockAgeService`).

### Nettoyage préalable déjà effectué (Sprint 04, extension)

`SoldeAlertService` et le dashboard `monitoring_alertes_dashboard` (`direction/`) — un système d'alerte ad hoc antérieur à ce cadrage, non lié dans la navigation et porteur d'un bug de déduplication actif — ont été supprimés, et la table `Alerte` vidée des lignes dupliquées qu'il avait produites. Ce sprint repart donc sur un modèle `Alerte` propre, sans système concurrent à absorber.

### Affinage de l'alerte "solde superviseur" (27/07/2026)

Constat de mdmaiga : le seuil statique seul a peu de valeur, parce qu'un décalage d'un jour est **normal** dans le cycle — un agent qui vend le lundi voit le superviseur détenir ce cash (`Recouvrement`) jusqu'au recouvrement/versement du lendemain matin (`RecouvrementSuperviseur`/`VersementBancaire`, via l'action groupée quotidienne `finance:recouvrement_versement_groupe`). La quasi-totalité de la recette finit toujours par être recouvrée dans ce cycle normal ; un solde élevé un matin donné n'est souvent que "la vente de la veille pas encore remise", pas une anomalie.

L'alerte MVP "solde" (ligne 1 de la fiche ci-dessous) est donc **affinée en deux sous-cas**, tous deux évalués par `AlerteMoteur.evaluer_solde_superviseur()` mais avec des sémantiques différentes :

- **1a. Réconciliation matinale** (`niveau=info`) : chaque matin, avant l'action groupée du jour, informe du solde actuel de chaque superviseur au-dessus du seuil — sert à vérifier rapidement "que ça fitte" avant le recouvrement/versement réel, pas un signal d'anomalie en soi.
- **1b. Solde persistant** (`niveau=critique`) : si le solde d'un superviseur reste `> 0` après **3 cycles de remise consécutifs** — 3 `RecouvrementSuperviseur` successifs pour ce superviseur (pas 3 jours calendaires : une ligne laissée vide dans l'action groupée ne compte pas comme un cycle traité) — c'est le signal réellement anormal, une recette qui ne se résorbe pas alors qu'elle le devrait dans le cycle normal.

`1b` nécessite d'historiser, pour chaque superviseur, le solde constaté juste après chacun de ses 3 derniers `RecouvrementSuperviseur` — logique de comptage que `finance/services.py` (calculateur pur, sans historisation, cf. ses propres invariants) ne porte pas ; elle est implémentée dans `monitoring/services/moteur_alerte.py` (Volet 5).

**Confirmé par mdmaiga (27/07/2026)** : le bordereau de versement de chaque superviseur est enregistré en continu (un `RecouvrementSuperviseur` par jour, dès réception), à une exception près — celui du samedi est saisi le lundi mais avec `date_recouvrement` renseignée au samedi (pas la date de saisie). `date_recouvrement` reflète donc fidèlement le cycle métier réel même quand la saisie est différée : le tri par `-date_recouvrement` (et non `date_creation`) dans le squelette du Volet 5 reste le bon critère pour identifier "les 3 derniers cycles" sans se faire piéger par ce décalage samedi→lundi.

Déjà fait (hors volets, prérequis appliqué le 27/07/2026) : `finance/services.py::SEUIL_ALERTE_SOLDE` relevé à 30 000 FCFA et comparaison passée en strict `>` ; `finance/APP_FINANCE.md` documente la nuance ci-dessus.

---

## Décisions confirmées (tranchées avec mdmaiga le 27/07/2026)

Reprend les réponses aux 3 questions critiques déjà actées dans `docs/BACKLOG.md`, complétées par les points d'architecture identifiés lors de l'évaluation de maturité du socle :

1. **Nouvelle app `monitoring`** — capacité transverse au sens de `rules/ARCHITECTURE.md` (n'importe/n'appelle que des services d'autres apps, ne possède aucun modèle métier propre). Ajoutée à `INSTALLED_APPS`.
2. **`Alerte` (modèle existant, dans `core`) étendu** plutôt que `BusinessAlert` séparé (Option A, Q1) :
   - Champs ajoutés : `statut` (`ACTIVE`/`RESOLUE`/`IGNOREE`, défaut `ACTIVE`), `date_resolution`, `date_dernier_envoi`, `nombre_envois`.
   - **Lien vers l'objet source** : FK dédiées nullables `lot` (`LotEntrepot`) et `distribution` (`DetailDistribution`), plutôt qu'une `GenericForeignKey` — aucun pattern `ContentType`/générique n'existe ailleurs dans ce repo ; rester cohérent avec le style FK explicite déjà en place sur `Alerte.produit`.
   - `Alerte.superviseur`/`Alerte.agent` restent des FK vers `User` (`superviseur=agent.user`), comme aujourd'hui — il n'existe pas de modèle `Superviseur` séparé dans ce repo.
   - `niveau` (existant, valeurs `info`/`warning`/`critique`) est conservé tel quel, pas renommé en `gravite` — champ déjà adapté, migration inutile.
   - `est_vue` (existant) devient redondant avec `statut` mais n'est pas supprimé ce sprint (dépréciation à évaluer plus tard, hors MVP).
   - La migration correspondante est une migration **`core`** (le modèle `Alerte` reste défini dans `core/models.py`), pas `monitoring`.
3. **Déclenchement : appels directs, pas de signals** (Option B, Q2) — **une commande de management périodique unique** (`monitoring/management/commands/evaluer_alertes.py`) évalue les 4 règles à chaque exécution, plutôt qu'un mélange synchrone (solde, à chaque mutation financière) + périodique (stock). Raison : évite de toucher aux points de mutation déjà sensibles de `finance`/`vente` (versement, recouvrement, vente) pour brancher un appel synchrone ; plus simple à tester et à faire évoluer pour un MVP à 4 règles. Lancée via tâche planifiée OS, comme `generer_salaires_mensuel` (pas d'infra Celery/APScheduler dans ce repo, cf. `STACK.md`).
4. **Throttling** (Q3) : paramètre `reenvoi_heures` par règle dans `monitoring/constants.py`, `None` par défaut (pas de rappel tant qu'ACTIVE), sauf `solde` (rappel 24h — la réconciliation matinale se répète naturellement chaque jour tant que le solde dépasse le seuil), `solde_persistant` (rappel 24h — alerte critique, ne doit pas se perdre) et `activite` (rappel 12h).
5. **`TelegramProvider`** : cadré et codé ce sprint, mais en **stub** — aucun bot Telegram/`chat_id` disponible à ce jour. Le provider logue l'alerte formatée (`logging`, niveau INFO) au lieu d'appeler l'API Telegram. Le vrai appel HTTP est un TODO explicite, activé dès que les credentials existent (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` en `.env`, actuellement absents intentionnellement).
6. **Aucune vue, aucun template ce sprint** — le Chantier 3 est un moteur backend (historisation + dispatch). L'exploitation UI ("alertes résolues cette semaine", filtres) est explicitement hors MVP (`docs/BACKLOG.md` § Scope futur).
7. **Périmètre MVP = 4 alertes**, sur les sources réelles listées en Contexte. Pas de règle générique "prix modifié" : `Produit` n'a pas de prix propre dans ce modèle de données (prix saisi à la vente, cf. `rules/ARCHITECTURE.md` § Invariants), donc "variation prix" se limite à la détection déjà en place (`PrixSurveillanceService.ventes_a_perte`).

---

## Fiches des 4 alertes MVP

| # | `type_alerte` | Source (méthode réelle) | Condition | Gravité | Lien objet |
|---|---|---|---|---|---|
| 1a | `solde` | `finance.services.lister_soldes_superviseurs()` | `solde > SEUIL_ALERTE_SOLDE` (30 000 FCFA), évaluée tôt le matin avant l'action groupée du jour | `info` | `superviseur` (via `.user`) |
| 1b | `solde_persistant` *(nouveau choix)* | idem + historique des 3 derniers `RecouvrementSuperviseur` du superviseur | `solde > 0` après 3 cycles de remise consécutifs | `critique` | `superviseur` (via `.user`) |
| 2 | `stock` | `StockAgeService.lots_stock_dormant()` | lot/affectation non distribué depuis > `DELAI_STOCK_DORMANT_JOURS` (14j) | `warning` | `lot` |
| 3 | `prix` | `PrixSurveillanceService.ventes_a_perte()` | vente sous `prix_achat_unitaire + SEUIL_MARGE_MINIMALE` | `critique` | `lot`, `produit` |
| 4 | `activite` | `StockAgeService.agents_sans_vente_recente()` | agent sans vente depuis > `DELAI_ROTATION_JOURS` (2j) | `warning` | `agent`, `distribution` |

`1a` et `1b` sont volontairement deux `type_alerte` distincts (`solde` / `solde_persistant`), pas une seule clé partagée : la déduplication (Volet 3) clôt/renvoie par `(type_alerte, superviseur)` — les mélanger ferait que l'une bloquerait la création de l'autre pour le même superviseur alors que ce sont deux signaux différents (routine vs anomalie). `Alerte.TYPES` gagne donc une 5ᵉ entrée `("solde_persistant", "Solde persistant")` (Volet 2). Le déclenchement matinal (`1a`, avant l'action groupée) implique que la commande `evaluer_alertes` (Volet 5) doit être planifiée tôt le matin (ex. 6h-7h), pas à une heure arbitraire.

---

## User stories

**US-01 — Historisation des alertes**
En tant que mdmaiga, je veux que chaque situation anormale détectée soit tracée en base (création, renvois, résolution), pour garder un historique fiable au lieu d'un affichage éphémère.

**US-02 — Pas de spam**
En tant que mdmaiga, je veux ne recevoir qu'un nombre raisonnable de notifications pour une même situation qui persiste, pour ne pas être noyé sous des alertes répétées.

**US-03 — Résolution automatique**
En tant que mdmaiga, je veux qu'une alerte se ferme automatiquement dès que la situation qui l'a déclenchée disparaît, sans action manuelle.

**US-04 — Diffusion Telegram (préparée)**
En tant que mdmaiga, je veux que le moteur soit prêt à notifier via Telegram dès que le bot existe, sans refonte du moteur au moment de brancher le canal réel.

**US-05 — Aucune régression métier**
En tant que mdmaiga, je veux que l'échec d'un envoi de notification (Telegram indisponible, etc.) n'interrompe jamais le flux métier qui l'a déclenché (la commande périodique continue, une vue ne plante pas).

---

## Découpage en volets

5 volets, dans l'ordre (le Volet 2 conditionne les Volets 3 et 5 ; le Volet 4 peut être fait en parallèle du 2/3).

### Volet 1 — Fiches de cadrage (formalisation)

**Fichiers** : `docs/sprints/sprint-05.md` (ce document — section "Fiches des 4 alertes MVP" ci-dessus).

Aucun code. Valide que les 4 fiches (source exacte, condition, gravité, lien objet) sont correctes avant de migrer quoi que ce soit.

**DoD Volet 1** :
- [ ] Les 4 fiches ci-dessus relues et confirmées par mdmaiga (source réelle, pas une source inventée ou obsolète).
- [ ] Écart assumé sur "variation prix" (pas de règle générique prix modifié) explicitement acté.

---

### Volet 2 — Modèle `Alerte` (migration `core`)

**Fichiers** : `core/models.py` (modifier), `core/migrations/` (créer), `core/admin.py` (modifier).

```python
# core/models.py — Alerte, champs ajoutés
class Alerte(models.Model):
    STATUTS = [
        ("ACTIVE", "Active"),
        ("RESOLUE", "Résolue"),
        ("IGNOREE", "Ignorée"),
    ]

    TYPES = [
        ("solde", "Solde superviseur"),
        ("solde_persistant", "Solde persistant"),  # nouveau — voir Affinage ci-dessus
        ("stock", "Stock ancien"),
        ("prix", "Variation prix"),
        ("activite", "Baisse activité"),
    ]

    # ... champs existants (type_alerte, niveau, message, superviseur, agent, produit, est_vue, date_creation) inchangés

    lot = models.ForeignKey(
        "LotEntrepot", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="alertes"
    )
    distribution = models.ForeignKey(
        "DetailDistribution", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="alertes"
    )
    statut = models.CharField(max_length=20, choices=STATUTS, default="ACTIVE")
    date_resolution = models.DateTimeField(null=True, blank=True)
    date_dernier_envoi = models.DateTimeField(null=True, blank=True)
    nombre_envois = models.PositiveIntegerField(default=0)
```

`core/admin.py::AlerteSoldeAdmin` : ajouter `statut`, `date_dernier_envoi`, `nombre_envois` à `list_display`/`list_filter` (renommer la classe en `AlerteAdmin`, le nom actuel date de l'ancien système supprimé).

**DoD Volet 2** :
- [x] Migration appliquée sans erreur (`manage.py migrate`), aucune donnée existante perdue (table déjà vidée, cf. Contexte).
- [x] `statut` par défaut `ACTIVE` pour toute nouvelle `Alerte`.
- [x] Admin Django à jour (filtre par `statut`, tri par `date_dernier_envoi`).

---

### Volet 3 — Service de déduplication

**Fichiers** : `monitoring/__init__.py`, `monitoring/apps.py`, `monitoring/constants.py` (créer), `monitoring/services/__init__.py`, `monitoring/services/deduplication_service.py` (créer), `dams/settings.py` (modifier — `INSTALLED_APPS`).

```python
# monitoring/constants.py
ALERTES_MVP = {
    "solde":            {"reenvoi_heures": 24},   # réconciliation matinale, se répète chaque jour tant que solde > seuil
    "solde_persistant": {"reenvoi_heures": 24},   # critique — ne doit pas se perdre
    "stock":            {"reenvoi_heures": None}, # une seule notification, silence tant qu'ACTIVE
    "prix":             {"reenvoi_heures": None},
    "activite":         {"reenvoi_heures": 12},   # deux rappels par jour si agent toujours inactif
}
```

```python
# monitoring/services/deduplication_service.py (squelette)
class AlerteDeduplicationService:
    @staticmethod
    def get_ou_creer(type_alerte, defaults, **cles_identification):
        # cles_identification identifie l'alerte "logique" (ex: agent=..., ou lot=...)
        # Cherche une Alerte ACTIVE avec ces clés. Si absente : crée (nombre_envois=1,
        # date_dernier_envoi=now). Si présente : retourne (alerte, False, doit_envoyer)
        # où doit_envoyer dépend de reenvoi_heures (cf. constants.ALERTES_MVP).
        ...

    @staticmethod
    def cloturer_si_resolue(type_alerte, cles_identification_actives):
        # Pour un type_alerte donné, ferme (statut=RESOLUE, date_resolution=now)
        # toute Alerte ACTIVE dont les clés d'identification n'apparaissent plus
        # dans cles_identification_actives (situation disparue).
        ...
```

**DoD Volet 3** :
- [x] Pas de nouvelle `Alerte` créée si une `ACTIVE` existe déjà pour la même situation logique.
- [x] Renvoi (`nombre_envois` incrémenté, `date_dernier_envoi` mis à jour) uniquement si `reenvoi_heures` écoulées depuis le dernier envoi.
- [x] `stock`/`prix` : aucun renvoi tant qu'ACTIVE (`reenvoi_heures=None`).
- [x] Une situation qui disparaît clôture automatiquement l'`Alerte` correspondante (`RESOLUE`, `date_resolution` renseignée).
- [x] Tests unitaires (`monitoring/tests.py`) : création initiale, pas de doublon immédiat, renvoi après délai, silence avant délai, clôture automatique.

---

### Volet 4 — `TelegramProvider` (stub)

**Fichiers** : `monitoring/providers/__init__.py`, `monitoring/providers/telegram.py` (créer).

```python
# monitoring/providers/telegram.py
import logging

logger = logging.getLogger("monitoring.telegram")

class TelegramProvider:
    @staticmethod
    def send(alerte):
        """
        Stub : aucun bot Telegram/chat_id disponible à ce jour (TELEGRAM_BOT_TOKEN/
        TELEGRAM_CHAT_ID absents de .env). Logue l'alerte formatée au lieu de
        l'envoyer. Ne lève jamais d'exception vers l'appelant (US-05) :
        l'échec d'envoi ne doit jamais interrompre le flux appelant.
        """
        try:
            message = f"[{alerte.get_niveau_display()}] {alerte.message}"
            logger.info("Telegram (stub) — %s", message)
            # TODO : appel API Telegram réel une fois les credentials disponibles.
        except Exception:
            logger.exception("Échec d'envoi Telegram pour Alerte #%s", alerte.pk)
```

**DoD Volet 4** :
- [x] `TelegramProvider.send()` ne lève jamais d'exception (try/except large, log seulement).
- [x] Format de message cohérent (niveau + message), facile à remplacer par un vrai appel API sans changer sa signature.
- [x] `.env`/`STACK.md` **non modifiés** ce sprint (pas de variable Telegram tant qu'aucun bot n'existe) — à faire quand les credentials arrivent.

---

### Volet 5 — Moteur d'évaluation + commande périodique

**Fichiers** : `monitoring/services/moteur_alerte.py` (créer), `monitoring/management/__init__.py`, `monitoring/management/commands/__init__.py`, `monitoring/management/commands/evaluer_alertes.py` (créer).

```python
# monitoring/services/moteur_alerte.py (squelette)
from core.models import Alerte, RecouvrementSuperviseur
from finance.services import lister_soldes_superviseurs, solde_superviseur
from surveillance.services.stock_age_service import StockAgeService
from surveillance.services.prix_service import PrixSurveillanceService
from monitoring.services.deduplication_service import AlerteDeduplicationService
from monitoring.providers.telegram import TelegramProvider

class AlerteMoteur:
    @staticmethod
    def evaluer_solde_superviseur():
        """
        1a (routine) : solde > seuil, quel que soit le contexte du cycle.
        1b (anormal) : solde encore > 0 juste après chacun des 3 derniers
        RecouvrementSuperviseur de ce superviseur (3 cycles traités, pas
        3 jours calendaires).
        """
        for item in lister_soldes_superviseurs():
            superviseur = item["superviseur"]

            if item["alerte"]:
                ...  # get_ou_creer(type_alerte="solde", niveau="info", superviseur=superviseur.user, ...)

            derniers_cycles = (
                RecouvrementSuperviseur.objects
                .filter(superviseur=superviseur)
                .order_by("-date_recouvrement")[:3]
            )
            if len(derniers_cycles) == 3 and all(
                solde_superviseur(superviseur, date_fin=cycle.date_recouvrement.date())["solde"] > 0
                for cycle in derniers_cycles
            ):
                ...  # get_ou_creer(type_alerte="solde_persistant", niveau="critique", superviseur=superviseur.user, ...)
                # + TelegramProvider.send(alerte) si doit_envoyer

    @staticmethod
    def evaluer_stock_ancien():
        for lot_data in StockAgeService.lots_stock_dormant():
            ...  # get_ou_creer(type_alerte="stock", lot=lot_data["lot"], ...)

    @staticmethod
    def evaluer_variation_prix():
        for item in PrixSurveillanceService.ventes_a_perte():
            ...  # get_ou_creer(type_alerte="prix", lot=item["lot"], produit=item["produit"], ...)

    @staticmethod
    def evaluer_baisse_activite():
        for agent_data in StockAgeService.agents_sans_vente_recente():
            ...  # get_ou_creer(type_alerte="activite", agent=agent_data["agent"].user, ...)
```

```python
# monitoring/management/commands/evaluer_alertes.py
from django.core.management.base import BaseCommand
from monitoring.services.moteur_alerte import AlerteMoteur

class Command(BaseCommand):
    help = "Évalue les alertes MVP (solde, solde persistant, stock, prix, activité) et notifie via Telegram."

    def handle(self, *args, **options):
        AlerteMoteur.evaluer_solde_superviseur()
        AlerteMoteur.evaluer_stock_ancien()
        AlerteMoteur.evaluer_variation_prix()
        AlerteMoteur.evaluer_baisse_activite()
        self.stdout.write(self.style.SUCCESS("Alertes évaluées."))
```

**DoD Volet 5** :
- [x] `manage.py evaluer_alertes` exécute les 5 règles (1a, 1b, 2, 3, 4) sans erreur sur une base vide comme sur une base peuplée.
- [x] Chaque règle appelle le service source existant tel quel (`lister_soldes_superviseurs`, `solde_superviseur`, `StockAgeService`, `PrixSurveillanceService`) — aucune requête ORM dupliquée dans `monitoring`.
- [x] `1b` (solde persistant) ne se déclenche que si le superviseur a bien 3 `RecouvrementSuperviseur` historisés, tous avec un solde résiduel `> 0` à leur date respective — un superviseur avec moins de 3 cycles n'est jamais faussement alerté.
- [x] Un échec `TelegramProvider.send()` n'interrompt pas l'évaluation des règles suivantes (US-05).
- [x] Tests (`monitoring/tests.py`) : au moins un cas par règle (création d'alerte), le scénario "situation résolue" (agent qui recommence à vendre, solde qui repasse sous le seuil) → `Alerte` clôturée, et le cas `1b` (3 cycles avec solde résiduel vs 2 cycles seulement → pas d'alerte).
- [x] `STACK.md` mis à jour : `manage.py evaluer_alertes` documentée dans "Commandes de gestion courantes", avec la même remarque que `generer_salaires_mensuel` sur la tâche planifiée OS (pas d'infra Celery/APScheduler) — préciser l'horaire matinal requis pour `1a`.

---

## Invariants (valables sur tout le sprint)

- Aucun signal Django — tous les déclenchements sont des appels directs, explicites (décision Q2).
- Aucune vue, aucun template — moteur backend uniquement (historisation + dispatch).
- Un échec de `TelegramProvider.send()` ne remonte jamais d'exception à l'appelant (US-05).
- `monitoring` n'écrit jamais dans `finance`/`surveillance`/`vente` — lecture seule sur leurs services, écriture uniquement sur `Alerte` (`core`).
- Pas de nouvelle variable `.env` fonctionnelle tant que le bot Telegram n'existe pas (Volet 4).

---

## Critères de validation globaux (Definition of Done du sprint)

- [ ] Les 5 volets ci-dessus sont chacun individuellement validés (DoD par volet).
- [x] `manage.py check` propre, migration `core` appliquée.
- [x] `manage.py evaluer_alertes` exécutable manuellement sans erreur, log Telegram (stub) visible en sortie.
- [x] `docs/BACKLOG.md` (Chantier 3) mis à jour : statut → 🟡 en cours ou ✅ terminée selon l'avancement, lien vers ce sprint.
- [x] `monitoring/APP_MONITORING.md` créé, sur le modèle des autres `APP_*.md` du repo (rôle, architecture, points de vigilance — notamment le TODO Telegram réel).

---

## Fichiers à créer / modifier

| Fichier | Action |
|---|---|
| `core/models.py` | Modifier — `Alerte` : `lot`, `distribution`, `statut`, `date_resolution`, `date_dernier_envoi`, `nombre_envois` |
| `core/migrations/` | Créer — migration `Alerte` |
| `core/admin.py` | Modifier — `AlerteAdmin` (renommé), nouveaux champs |
| `dams/settings.py` | Modifier — `INSTALLED_APPS += 'monitoring'` |
| `monitoring/__init__.py`, `apps.py` | Créer — nouvelle app |
| `monitoring/constants.py` | Créer — `ALERTES_MVP` (config `reenvoi_heures` par type) |
| `monitoring/services/deduplication_service.py` | Créer — `AlerteDeduplicationService` |
| `monitoring/services/moteur_alerte.py` | Créer — `AlerteMoteur` |
| `monitoring/providers/telegram.py` | Créer — `TelegramProvider` (stub log) |
| `monitoring/management/commands/evaluer_alertes.py` | Créer — commande périodique |
| `monitoring/tests.py` | Créer — tests dédup + moteur |
| `monitoring/APP_MONITORING.md` | Créer — doc app |
| `docs/BACKLOG.md` | Modifier — statut Chantier 3 |
| `STACK.md` | Modifier — commande `evaluer_alertes` |
