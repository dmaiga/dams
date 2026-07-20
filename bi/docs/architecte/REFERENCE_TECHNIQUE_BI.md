# Référence technique DAMS — pour construction de la couche BI (dbt + PostgreSQL)

**Date de production :** 2026-07-17
**Méthodologie :** ce document reflète le code tel qu'il est **aujourd'hui** (`core/models.py`, vues, forms, services), vérifié contre une lecture ligne à ligne du modèle et une exploration ciblée des workflows par plusieurs agents indépendants, et croisé avec une requête directe sur la base PostgreSQL de développement (`c2679735c_dams`) pour les valeurs réellement présentes. Les `APP_*.md` et `docs/decisions/*` existants ont été utilisés comme point de départ mais **jamais comme source de vérité** : toute divergence constatée avec le code est signalée explicitement en section 6, jamais tranchée silencieusement.

Toutes les tables listées ci-dessous vivent dans le schéma `public`, préfixe `core_` (app Django `core`, cf. `rules/ARCHITECTURE.md` — ADR-001 : les modèles restent dans `core`, les apps `marchandise`/`vente`/`direction`/`agents`/`paie`/`surveillance` les importent sans les posséder).

---

## Sommaire

1. [Inventaire des modèles](#1-inventaire-des-modèles)
2. [Champs et propriétés calculées](#2-champs-et-propriétés-calculées-pas-stockées-en-base)
3. [Énumérations réelles](#3-énumérations-réelles)
4. [Workflows métier bout en bout](#4-workflows-métier-bout-en-bout)
5. [Frontières d'app et permissions par capacité](#5-frontières-dapp-et-permissions-par-capacité)
6. [Écarts identifiés](#6-écarts-identifiés)

---

## 1. Inventaire des modèles

Tous les modèles sont définis dans `core/models.py`. Convention de table : `core_<nom_modèle_en_minuscules>`.

### 1.1 `Client` (`core_client`) — `core/models.py:19-34`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `nom` | CharField(100) | non | — | |
| `contact` | CharField(100) | oui/oui | — | |
| `type_client` | CharField(50), choices | non | — | `grossiste`/`detail`/`particulier` |
| `date_creation` | DateTimeField | non | `timezone.now` | |

FK entrantes : `Vente.client` (SET_NULL), `MouvementStock.client` (CASCADE).
**Table vide en base (0 ligne)** — voir §3 et §6 : `client` n'est jamais renseigné par les flux de vente actifs.

### 1.2 `Produit` (`core_produit`) — `core/models.py:36-49`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `nom` | CharField(100), unique | non | — | |
| `description` | TextField | oui/oui | — | |
| `poids_unitaire_kg` | DecimalField(6,2) | oui/oui | — | Renseigné — produit « conditionné » (carton/sac). Vide — produit vendu au kg (« vrac »). Pivot de nombreux calculs (`quantite_en_kg`, incentive paie mamies). |

### 1.3 `Alerte` (`core_alerte`) — `core/models.py:51-96`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `type_alerte` | CharField(30), choices | non | — | `solde`/`stock`/`prix`/`activite` |
| `niveau` | CharField(20), choices | non | — | `info`/`warning`/`critique` |
| `message` | TextField | non | — | |
| `superviseur` | FK — `User` | oui/oui, SET_NULL | — | ⚠️ pointe vers `django.contrib.auth.User`, pas `Agent` |
| `agent` | FK — `User` | oui/oui, SET_NULL | — | idem |
| `produit` | FK — `Produit` | oui/oui, SET_NULL | — | |
| `est_vue` | BooleanField | non | `False` | |
| `date_creation` | DateTimeField | non | `auto_now_add` | |

**En base : uniquement `type_alerte='solde'`, `niveau='critique'` sont présents (12 lignes)** — `stock`/`prix`/`activite` et `info`/`warning` sont déclarés mais jamais générés par le code actuel (cf. §3, §6). Généré par `direction/services/alertes/solde.py` uniquement — les fichiers `alertes/activite.py`, `alertes/prix.py`, `alertes/stock.py` sont vides (`0` ligne de code).

### 1.4 `Fournisseur` (`core_fournisseur`) — `core/models.py:98-175`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `nom` | CharField(100), unique | non | — | |
| `contact` | CharField(100) | oui/oui | — | |
| `adresse` | CharField(200) | oui/oui | — | |
| `email` | EmailField | oui/oui | — | |
| `date_ajout` | DateTimeField | non | `auto_now_add` | |

Pas de soft delete. Propriétés calculées détaillées en §2.

### 1.5 `Agent` (`core/models.py:177-923`, table `core_agent`)

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `user` | OneToOneField — `User` | non, CASCADE | — | |
| `type_agent` | CharField(50), choices | non | — | 8 valeurs, voir §3 |
| `superviseur` | FK — `self` | oui/oui, SET_NULL | — | `limit_choices_to={'type_agent':'entrepot'}` |
| `date_debut_fonction` | DateField | oui/oui | — | pivot du prorata paie mamies (§4) |
| `salaire_base_personnel` | DecimalField(10,2) | oui/oui | — | override du salaire théorique |
| `quartier` | CharField(150) | oui/oui | — | |
| `marche_affectation` | CharField(150) | oui/oui | — | |
| `type_contrat` | CharField(20), choices | non | `'prestation'` | `prestation`/`stage`/`cdd`/`cdi` |
| `date_fin_contrat` | DateField | oui/oui | auto (voir `save()`) | |
| `telephone` | CharField(50) | oui/oui | — | utilisé par `TelephoneBackend` |
| `ajustement_solde` | DecimalField(12,2) | non | `0` | ajustement manuel du solde superviseur |
| `est_actif` | BooleanField | non | `True` | |
| `date_creation` | DateTimeField | non | `auto_now_add` | |
| `date_expiration` | DateTimeField | oui/oui | auto (stagiaire, +14j) | |
| `date_mise_service` | DateTimeField | oui/oui | auto (stagiaire) | |

Pas de champ `est_supprime` — la « suppression » d'un agent est une opération dure (`core/views.py:186 supprimer_agent`, **vue jamais routée**, cf. §6) ou une désactivation (`Agent.desactiver()`, `core/models.py:367-371`, `est_actif=False` + `user.is_active=False`).

### 1.6 `LotEntrepot` (`core_lotentrepot`) — `core/models.py:924-1131`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `produit` | FK — `Produit` | non, CASCADE | — | related_name `lots` |
| `fournisseur` | FK — `Fournisseur` | oui/oui, SET_NULL | `None` | related_name `lots` |
| `quantite_initiale` | DecimalField(10,2) | non | — | immuable en pratique |
| `quantite_restante` | DecimalField(10,2) | non | — | décrémentée à chaque affectation |
| `prix_achat_unitaire` | DecimalField(10,2) | non | — | |
| `valeur_stock_initiale` | DecimalField(15,2) | oui/oui | calculé au `save()` | `quantite_initiale * prix_achat_unitaire` — persisté, jamais recalculé après coup si le prix change |
| `receptionne_par` | FK — `Agent` | oui/oui, SET_NULL | — | auto-rempli à la réception (`marchandise`) |
| `date_reception` | DateTimeField | non | `timezone.now` | rétroactivable |
| `date_enregistrement` | DateTimeField | non | `auto_now_add` | |
| `quantite_disponible_rot` | DecimalField(10,2) | non | `0` | champ de compatibilité historique — voir §4, incrémenté (pas décrémenté) à chaque affectation |
| `reference_lot` | CharField(100), unique | oui/oui | auto `AAAAMMJJ-NNNN` | |

Garde-fous dans `save()` (`core/models.py:988-1005`) : `quantite_restante <= quantite_initiale`, `quantite_restante >= 0`, `quantite_disponible_rot >= 0` (lève `ValidationError` sinon).

### 1.7 `MiseDispositionRot` (`core_misedispositionrot`) — `core/models.py:1132-1150`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `lot` | FK — `LotEntrepot`, CASCADE | non | — |
| `quantite` | DecimalField(10,2) | non | — |
| `effectue_par` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='gestionnaire_stock'` | oui | — |
| `date_operation` | DateTimeField | non | `auto_now_add` |
| `commentaire` | TextField | oui/oui | — |

Table d'audit immuable, créée à chaque affectation (voir §4) — **547 lignes en base**, aucune mise à jour observée dans le code (pas de `.save()` hors création).

### 1.8 `FactureLotEntrepot` (`core_facturelotentrepot`) — `core/models.py:1152-1180`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `lot` | FK — `LotEntrepot`, CASCADE, related_name `factures` | non | — |
| `paiement_fournisseur` | OneToOneField — `PaiementFournisseur`, SET_NULL, related_name `facture_associee` | oui/oui | — |
| `fichier` | FileField(`factures_entrepot/%Y/%m/`) | oui/oui | — |
| `montant` | DecimalField(10,2) | oui/oui | — |
| `description` | CharField(255) | oui | — |
| `date_upload` | DateTimeField | non | `auto_now_add` |

### 1.9 `Perte` (`core_perte`) — `core/models.py:1182-1250`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `lot` | FK — `LotEntrepot`, CASCADE, related_name `pertes` | non | — |
| `quantite_perdue` | DecimalField(10,2) | non | — |
| `quantite_perdue_originale` | DecimalField(10,2) | non | `0` — figée à la création |
| `description` | TextField | non | — |
| `date_perte` | DateTimeField | non | `timezone.now` |
| `date_modification` | DateTimeField | non | `auto_now` |
| `est_modifiee` | BooleanField | non | `False` |

`save()`/`delete()` décrémentent/restituent `lot.quantite_restante` de manière atomique (`transaction.atomic()`, `core/models.py:1204-1234`) — c'est le **seul modèle hors `AffectationLotSuperviseur`/`marchandise`** à toucher directement au stock du lot.

### 1.10 `AffectationLotSuperviseur` (`core_affectationlotsuperviseur`) — `core/models.py:1252-1337`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `lot` | FK — `LotEntrepot`, CASCADE | non | — | |
| `superviseur` | FK — `Agent`, CASCADE, `limit_choices_to type_agent='entrepot'` | non | — | related_name `lots_affectes` |
| `quantite_initiale` | DecimalField(10,2) | non | — | — immuable en théorie (commentaire code) |
| `quantite_restante` | DecimalField(10,2) | non | — | — mutable |
| `prix_gros` | DecimalField(10,2) | oui/oui | — | **jamais renseigné par les flux actifs** (`marchandise`/`vente`), voir §4 |
| `prix_detail` | DecimalField(10,2) | oui/oui | — | idem |
| `attribue_par` | FK — `Agent`, SET_NULL | oui | — | |
| `agent_terrain_direct` | FK — `Agent`, SET_NULL, related_name `affectations_directes` | oui/oui | — | renseigné uniquement si distribution directe au moment de l'affectation |
| `date_affectation` | DateField | non | — | |
| `created_at` | DateTimeField | non | `auto_now_add` | date technique d'audit |

### 1.11 `DistributionAgent` (`core_distributionagent`) — `core/models.py:1339-1421`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `superviseur` | FK — `Agent`, CASCADE, related_name `distributions_envoyees` | non | — | |
| `agent_terrain` | FK — `Agent`, CASCADE, related_name `distributions_recues` | oui/oui | — | |
| `type_distribution` | CharField(50), choices | non | `'TERRAIN'` | recalculé automatiquement au `save()` — voir §3 |
| `quantite_totale` | DecimalField(10,2) | non | `0` | |
| `valeur_gros_totale` | DecimalField(10,2) | non | `0` | |
| `valeur_detail_totale` | DecimalField(10,2) | non | `0` | |
| `nombre_produits_differents` | PositiveIntegerField | non | `0` | |
| `date_distribution` | DateTimeField | non | `timezone.now` | |
| `date_creation` | DateTimeField | non | `auto_now_add` | |
| `date_modification` | DateTimeField | non | `auto_now` | |
| `est_retroactive` | BooleanField | non | `False` | ⚠️ jamais positionné automatiquement dans les flux lus — champ déclaratif, valeur réelle en base répartie 1374(False)/1503(True) probablement héritée d'une migration/saisie manuelle, pas d'écriture programmatique confirmée |

Index sur `date_distribution` et `superviseur` (`Meta.indexes`).

### 1.12 `DetailDistribution` (`core_detaildistribution`) — `core/models.py:1423-1471`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `distribution` | FK — `DistributionAgent`, CASCADE | non | — | |
| `lot` | FK — `LotEntrepot`, CASCADE | non | — | |
| `quantite` | DecimalField(10,2) | non | `0` | quantité totale distribuée sur ce détail |
| `quantite_vendue` | DecimalField(10,2) | non | `0` | **champ stocké**, incrémenté dans `Vente.save()` (`core/models.py:1611-1614`) ⚠️ — voir divergence critique §6 |
| `prix_gros` | DecimalField(10,2) | oui/oui | — | snapshot hérité de l'affectation, toujours `None` dans les flux actifs |
| `prix_detail` | DecimalField(10,2) | oui/oui | — | idem |
| `specification` | CharField(200) | oui | — | |

**`quantite_restante_calculee`** (property, pas stockée) : voir §2 — calcule un « restant » **indépendant** du champ stocké `quantite_vendue`, en resommant les `Vente` liées avec `est_supprime=False`. C'est la source utilisée par `vente/forms.py` et `marchandise/services.py`.

### 1.13 `MouvementStock` (`core_mouvementstock`) — `core/models.py:1473-1506`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `produit` | FK — `Produit`, CASCADE | non | — |
| `lot` | FK — `LotEntrepot`, CASCADE | oui/oui | — |
| `agent` | FK — `Agent`, CASCADE | oui/oui | — |
| `client` | FK — `Client`, CASCADE | oui/oui | — |
| `detail_distribution` | FK — `DetailDistribution`, SET_NULL | oui/oui | — |
| `type_mouvement` | CharField(50), choices | non | — | `RECEPTION`/`DISTRIBUTION`/`VENTE`/`RETOUR` |
| `quantite` | DecimalField(10,2) | non | `0` |
| `date_mouvement` | DateTimeField | non | `timezone.now` |
| `created_at` | DateTimeField | non | `auto_now_add` |

**En base : uniquement `RECEPTION` (261) et `DISTRIBUTION` (605)** — voir §3/§6, aucune vente ni retour n'écrit jamais dans cette table dans les flux actifs.

### 1.14 `JournalModificationDistribution` (`core_journalmodificationdistribution`) — `core/models.py:1508-1530`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `distribution` | FK — `DistributionAgent`, CASCADE | non | — |
| `utilisateur` | FK — `User`, CASCADE | non | — |
| `type_action` | CharField(50), choices | non | — | `CREATION`/`MODIFICATION`/`SUPPRESSION`/`RESTAURATION` |
| `date_action` | DateTimeField | non | `auto_now_add` |
| `details` | TextField | oui | — |
| `anciennes_valeurs` | JSONField | oui/oui | — |
| `nouvelles_valeurs` | JSONField | oui/oui | — |

**Table vide en base (0 ligne)** — modèle défini mais jamais écrit par le code actuel exploré (aucune vue/service `marchandise`, `vente`, `agents`, `core` ne le crée). — traiter comme non alimenté pour la BI tant que confirmation contraire.

### 1.15 `Vente` (`core_vente`) — `core/models.py:1532-1735`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `agent` | FK — `Agent`, CASCADE | non | — | pas de `superviseur_id` direct — dérivé via `detail_distribution.distribution.superviseur` |
| `stagiaire` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='stagiaire'` | oui/oui | — | |
| `client` | FK — `Client`, SET_NULL | oui/oui | — | jamais renseigné en pratique (table `Client` vide) |
| `detail_distribution` | FK — `DetailDistribution`, CASCADE | non | — | source du produit/prix/lot/fournisseur |
| `specification` | CharField(200) | oui | — | auto-remplie depuis `detail_distribution.specification` si vide |
| `quantite` | DecimalField(10,2) | non | `0.00` | |
| `type_vente` | CharField(50), choices | non | `'detail'` | `gros`/`detail` |
| `prix_vente_unitaire` | DecimalField(10,2) | non | — | |
| `mode_paiement` | CharField(50), choices | non | `'comptant'` | `comptant`/`credit` — **100% `comptant` en base**, voir §3/§6 |
| `date_vente` | DateTimeField | non | `timezone.now` | rétroactivable |
| `ancienne_vente` | BooleanField | non | `False` | |
| `date_creation` | DateTimeField | non | `auto_now_add` | |
| `est_supprime` | BooleanField | non | `False` | **soft delete** |
| `date_suppression` | DateTimeField | oui/oui | — | |

`save()` (`core/models.py:1594-1623`) : détermine le prix si absent, remplit la spécification, **puis** (`is_new`) incrémente `detail_distribution.quantite_vendue`, **puis** crée une `Dette` si `mode_paiement=='credit'` (jamais atteint en pratique aujourd'hui).

### 1.16 `Dette` (`core_dette`) — `core/models.py:1736-1785`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `vente` | OneToOneField — `Vente`, CASCADE, related_name `dette` | non | — |
| `montant_total` | DecimalField(10,2) | non | — |
| `montant_restant` | DecimalField(10,2) | non | — |
| `date_creation` | DateTimeField | non | `timezone.now` |
| `date_echeance` | DateField | non | — |
| `date_reglement` | DateField | oui/oui | — |
| `statut` | CharField(50), choices | non | `'en_cours'` | `en_cours`/`partiellement_paye`/`paye`/`en_retard` |
| `nom_localite` | CharField(100) | oui | — |
| `notes` | TextField | oui | — |

**Table vide (0 ligne) en base** — confirme explicitement l'hypothèse de départ : le modèle existe et sa logique (`statut` auto-calculé au `save()`) est fonctionnelle, mais aucune vente à crédit n'a jamais été créée par le code actif.

### 1.17 `PaiementDette` (`core_paiementdette`) — `core/models.py:1787-1821`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `dette` | FK — `Dette`, CASCADE, related_name `paiements` | non | — |
| `montant` | DecimalField(10,2) | non | — |
| `date_paiement` | DateTimeField | non | `timezone.now` |
| `mode_paiement` | CharField(50), choices | non | `'espece'` | `espece`/`cheque`/`virement`/`mobile` |
| `reference` | CharField(100) | oui | — |
| `notes` | TextField | oui | — |

**Table vide (0 ligne)** — corollaire direct de `Dette` vide.

### 1.18 `BonusAgent` (`core_bonusagent`) — `core/models.py:1823-1863`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `agent` | OneToOneField — `Agent`, CASCADE, related_name `bonus` | non | — |
| `nombre_produits_recouverts` | PositiveIntegerField | non | `0` |
| `total_bonus` | DecimalField(10,2) | non | `0` |
| `date_mise_a_jour` | DateTimeField | non | `auto_now` |

Dépend de `Recouvrement.bonus_accorde` (voir 1.19) — logique distincte du calcul de paie superviseur (`paie/services/salaire_calculator.py`), non recoupée avec elle (voir §6, deux moteurs de bonus superviseur potentiellement différents).

### 1.19 `Recouvrement` (`core_recouvrement`) — `core/models.py:1865-1907`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `agent` | FK — `Agent`, CASCADE, related_name `recouvrements` | non | — |
| `superviseur` | FK — `Agent`, CASCADE, `limit_choices_to type_agent='entrepot'`, related_name `recouvrements_effectues` | oui/oui | — |
| `vente` | FK — `Vente`, CASCADE | oui/oui | — |
| `montant_recouvre` | DecimalField(10,2) | non | — |
| `commentaire` | TextField | oui | — |
| `date_recouvrement` | DateTimeField | non | `timezone.now` |
| `date_creation` | DateTimeField | non | `auto_now_add` |
| `bonus_accorde` | BooleanField | non | `False` |
| `montant_bonus` | DecimalField(10,2) | non | `0` |

Modèle du recouvrement **agent — superviseur**, créé automatiquement à chaque vente comptant (voir §4). **2696 lignes en base.**

### 1.20 `RecouvrementSuperviseur` (`core_recouvrementsuperviseur`) — `core/models.py:1908-1969`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `superviseur` | FK — `Agent`, CASCADE, `limit_choices_to type_agent='entrepot'` | non | — |
| `rot` | FK — `Agent`, CASCADE, `limit_choices_to type_agent='rot'` | non | — |
| `montant` | DecimalField(12,2) | non | — |
| `commentaire` | TextField | oui | — |
| `date_recouvrement` | DateTimeField | non | `timezone.now` |
| `date_creation` | DateTimeField | non | `auto_now_add` |

`clean()` (`core/models.py:1937-1958`) calcule `cash_disponible`/`cash_restant` mais **ne lève jamais de `ValidationError`** — garde-fou incomplet/mort (voir §6). Recouvrement **superviseur — ROT**, action manuelle (voir §4). **175 lignes en base.**

### 1.21 `VersementBancaire` (`core_versementbancaire`) — `core/models.py:1971-2070`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `superviseur` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='entrepot'` | oui/oui | — | — **déprécié**, jamais écrit par le flux actif (voir §6) |
| `effectue_par` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='rot'` | oui/oui | — | — champ actif |
| `montant_vente` | DecimalField(12,2) | non | `0` | |
| `montant_hors_vente` | DecimalField(12,2) | non | `0` | |
| `description` | HTMLField (TinyMCE) | oui | — | |
| `date_versement_reelle` | DateTimeField | non | `timezone.now` | rétroactivable |

**111 lignes en base.**

### 1.22 `RecuVersement` (`core_recuversement`) — `core/models.py:2072-2105`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `versement` | FK — `VersementBancaire`, SET_NULL, related_name `recus` | oui/oui | — |
| `fichier` | FileField(`recu_versement/%Y/%m/`) | non | — |
| `description` | CharField(255) | oui | — |
| `date_upload` | DateTimeField | non | `auto_now_add` |

### 1.23 `Depense` (`core_depense`) — `core/models.py:2107-2192`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `effectue_par` | FK — `Agent`, SET_NULL, related_name `depenses_effectuees` | oui/oui | — | — champ actif (ROT) |
| `versement` | FK — `VersementBancaire`, SET_NULL, related_name `depenses` | oui/oui | — | ⚠️ jamais renseigné à la création (voir §4/§6) |
| `montant` | DecimalField(12,2), `MinValueValidator(0.01)` | non | — | |
| `categorie` | CharField(40), choices | non | `'DIVERS'` | 7 valeurs, voir §3 — **21 lignes NULL en base malgré l'absence de `null=True` et un défaut non-NULL**, voir §6 |
| `note` | CharField(255) | oui | — | |
| `description` | HTMLField (TinyMCE) | oui | — | champ historique |
| `date_depense` | DateField | non | `timezone.localdate` | |
| `date_creation` | DateTimeField | non | `auto_now_add` | |
| `source` | CharField(20), choices | non | `'ROT'` | `ROT`/`MIGRATION`/`ADMIN` — **en base uniquement `ROT` (478) + 21 NULL**, voir §3/§6 |

### 1.24 `PaiementFournisseur` (`core_paiementfournisseur`) — `core/models.py:2194-2316`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `fournisseur` | FK — `Fournisseur`, CASCADE, related_name `paiements` | non | — | |
| `lot` | FK — `LotEntrepot`, CASCADE, related_name `paiements` | oui/oui | — | |
| `superviseur` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='entrepot'` | oui/oui | — | — déprécié, jamais écrit (voir §6) |
| `effectue_par` | FK — `Agent`, SET_NULL, `limit_choices_to type_agent='rot'` | oui/oui | — | — actif — **mais non validé comme `est_rot` dans un des deux chemins de création**, voir §4/§6 |
| `montant` | DecimalField(12,2) | non | — | |
| `date_paiement` | DateField | non | — | |
| `cree_par` | FK — `User`, SET_NULL | oui | — | |
| `created_at` | DateTimeField | non | `auto_now_add` | |
| `updated_at` | DateTimeField | non | `auto_now` | |
| `est_supprime` | BooleanField | non | `False` | soft delete |
| `supprime_par` | FK — `User`, SET_NULL | oui/oui | — | |
| `date_suppression` | DateTimeField | oui/oui | — | |

**246 lignes en base, toutes `est_supprime=False`.**

### 1.25 `ClotureMensuelle` (`core_cloturemensuelle`) — `core/models.py:2318-2411`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `superviseur` | FK — `Agent`, CASCADE, `limit_choices_to type_agent='entrepot'`, related_name `clotures_mensuelles` | non | — |
| `annee` | IntegerField | non | — |
| `mois` | IntegerField | non | — |
| `date_debut_periode` | DateField | non | — |
| `date_fin_periode` | DateField | non | — |
| `solde_ouverture` | DecimalField(15,2) | non | — |
| `solde_cloture` | DecimalField(15,2) | non | — |
| `est_cloture` | BooleanField | non | `False` |
| `date_cloture` | DateTimeField | oui/oui | — |
| `cloture_par` | FK — `User`, SET_NULL | oui/oui | — |
| `ecart_post_cloture` | DecimalField(15,2) | non | `0` |
| `date_creation` | DateTimeField | non | `auto_now_add` |
| `date_modification` | DateTimeField | non | `auto_now` |

`unique_together = ('superviseur', 'annee', 'mois')`. **32 lignes en base, toutes `est_cloture=True`** — aucune clôture en brouillon actuellement. Le modèle documente lui-même : *« La période n'est PAS forcément calendaire »* (`core/models.py:2320-2321`).

### 1.26 `AjustementSolde` (`core_ajustementsolde`) — `core/models.py:2413-2431`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `agent` | FK — `Agent`, CASCADE, related_name `ajustements_solde` | non | — |
| `montant` | DecimalField(12,2) | non | — |
| `motif` | CharField(255) | non | — |
| `date` | DateTimeField | non | `auto_now_add` |
| `cloture` | FK — `ClotureMensuelle`, SET_NULL, related_name `ajustements` | oui/oui | — |

**Table vide (0 ligne) dans la base explorée** — créé uniquement par `Agent.remettre_solde_operationnel_a_zero()` lors d'une clôture avec solde non nul (voir §4) ; la base de dev consultée n'a apparemment eu que des clôtures à solde déjà nul, ou l'historique a été purgé.

### 1.27 `RegleSalaire` (`core_reglesalaire`) — `core/models.py:2433-2457`

| Champ | Type | Null/Blank | Défaut | Notes |
|---|---|---|---|---|
| `type_agent` | CharField(20), choices, unique | non | — | `terrain`/`agent_gros`/`superviseur` |
| `dotation_fonction` | DecimalField(10,2) | non | `0` | |
| `incentive_par_kg` | DecimalField(10,2) | oui/oui | — | |
| `incentive_par_carton` | DecimalField(10,2) | oui/oui | — | |
| `actif` | BooleanField | non | `True` | |

**3 lignes en base : `agent_gros`, `superviseur`, `terrain`** — voir divergence critique §6 (`init_regles_remuneration.py` crée une règle `type_agent='entrepot'`, valeur hors choix, jamais lue par le calculateur).

### 1.28 `Salaire` (`core_salaire`) — `core/models.py:2459-2477`

| Champ | Type | Null/Blank | Défaut |
|---|---|---|---|
| `agent` | FK — `Agent`, CASCADE, related_name `salaires` | non | — |
| `date_debut` | DateField | non | — |
| `date_fin` | DateField | non | — |
| `salaire_base` | DecimalField(10,2) | non | — |
| `incentive` | DecimalField(10,2) | non | — | pour un superviseur, contient en réalité le **bonus** (pas la dotation), voir §4 |
| `salaire_total` | DecimalField(10,2) | non | — |
| `genere_le` | DateTimeField | non | `auto_now_add` |
| `valide` | BooleanField | non | `False` | figeage définitif via bulk `.update()` |

`unique_together = ('agent', 'date_debut', 'date_fin')`. **21 lignes en base, toutes `valide=False`** (aucune paie validée dans la base de dev consultée). `paie/models.py` est vide — pas de table `paie_*`.

---

## 2. Champs et propriétés calculées (PAS stockées en base)

### 2.1 `Fournisseur` (`core/models.py:105-175`)

| Propriété | Formule | Dépendance temporelle |
|---|---|---|
| `nombre_lots_actifs` | `count(lots avec quantite_restante > 0)` | non |
| `valeur_stock_total` | `Sum(quantite_restante * prix_achat_unitaire)` sur tous les lots | non |
| `dette_totale` | boucle Python : `Σ (vente.quantite * lot.prix_achat_unitaire)` pour chaque lot/vente liée — **redondant avec `dette_consomme` (agrégation SQL), calcul en double avec potentiel de divergence de résultat (arrondi/N+1)** | non |
| `total_paye` | `Sum(paiements.montant)` (tous `PaiementFournisseur`, y compris soft-deleted — pas de filtre `est_supprime=False` ici) | non |
| `dette_restante` | `max(dette_consomme - total_paye, 0)` | non |
| `dette_contractuelle` | `Sum(lot.quantite_initiale * lot.prix_achat_unitaire)` — valeur théorique totale reçue | non |
| `dette_consomme` | `Sum(vente.quantite * detail_distribution.lot.prix_achat_unitaire)` filtré sur les ventes liées à des lots de ce fournisseur — valeur des produits **effectivement vendus** | non |

### 2.2 `Agent` — propriétés financières (`core/models.py:410-923`)

Toutes conditionnées par le `type_agent` (retournent `Decimal('0.00')` sinon) :

| Propriété | Type d'agent | Formule |
|---|---|---|
| `total_ventes` | agent_vente (terrain/agent_gros) | `Sum(Vente.quantite * prix_vente_unitaire)` où `agent=self` |
| `total_recouvre` | agent_terrain | `Sum(Recouvrement.montant_recouvre)` où `agent=self` |
| `argent_en_possession` | agent_vente | `total_ventes - total_recouvre` |
| `peut_etre_recouvre` | agent_vente | `argent_en_possession > 0` |
| `total_recouvre_agents` | superviseur | `Sum(Recouvrement.montant_recouvre)` où `superviseur=self` |
| `total_depenses_superviseur` | superviseur | ⚠️ `Sum(Depense.montant)` filtré sur `versement__superviseur=self` — champ **déprécié**, jamais alimenté par le flux ROT actuel (voir §6) — le commentaire du code lui-même dit `"⚠️ OBSOLÈTE — dépenses interdites après transition"` |
| `total_versements_superviseur` | superviseur | ⚠️ `Sum(VersementBancaire.montant_vente + montant_hors_vente)` filtré sur `VersementBancaire.superviseur=self` — même champ déprécié |
| `anciennes_ventes_personnelles` | superviseur | `Sum(Vente.quantite*prix)` où `agent=self` — **verrouillé à `0.00` dès qu'une clôture a été validée** (`date_derniere_cloture` non nulle) |
| `solde_reel_superviseur` | superviseur | `total_recouvre_agents + anciennes_ventes_personnelles - total_depenses_superviseur - total_versements_superviseur + ajustement_solde` — **verrouillé à `0.00` post-clôture** (ancien monde) ; dépend des champs dépréciés ci-dessus |
| `total_versements_vente` | superviseur | `Sum(VersementBancaire.montant_vente)` où `superviseur=self` (⚠️ même champ déprécié) |
| `date_derniere_cloture` | superviseur | date de fin de la dernière `ClotureMensuelle(est_cloture=True)`, sinon `date.min` — **pivot temporel de tous les soldes post-transition** |
| `total_ventes_autorisees_superviseur` | superviseur | `Sum(Vente.quantite*prix)` où `agent=self` et `date_vente >= date_derniere_cloture` |
| `solde_transitoire_superviseur` | superviseur | `total_recouvre_agents + total_ventes_autorisees_superviseur - total_versements_vente` |
| `solde_operationnel_superviseur` | superviseur | `Recouvrement(superviseur=self, date > date_derniere_cloture).Sum + Vente(agent=self, date > date_derniere_cloture).Sum - VersementBancaire(superviseur=self, date > date_derniere_cloture).Sum(montant_vente) + ajustement_solde` ⚠️ — filtre encore sur `VersementBancaire.superviseur` (déprécié) |
| `cash_disponible_superviseur` | superviseur | `Recouvrement(> date_derniere_cloture).Sum + Vente(> date_derniere_cloture).Sum` — **sans déduire les versements** (cash brut avant remise au ROT) |
| `solde_rot` | rot | `RecouvrementSuperviseur(rot=self).Sum(montant) - VersementBancaire(effectue_par=self).Sum(montant_vente) - Depense(effectue_par=self).Sum(montant) + ajustement_solde` — **ce calcul-ci utilise bien les champs actifs (`effectue_par`)**, cohérent |

**Dépendance temporelle critique commune à `solde_operationnel_superviseur`, `cash_disponible_superviseur`, `total_ventes_autorisees_superviseur`, `solde_transitoire_superviseur`** : tous filtrent sur `date > date_derniere_cloture` — leur résultat change silencieusement dès qu'une nouvelle `ClotureMensuelle(est_cloture=True)` est créée pour ce superviseur.

Autres propriétés utilitaires : `est_expire`, `a_acces_plateforme`, `jours_restants`, `duree_service`, `periode_stage_ecoulee`, `contrat_expire` (temporelles, cf. §1.5), `type_vente_par_defaut()`, `get_prix_vente()` (méthodes, **non utilisées** dans les flux `vente`/`marchandise` actuels, voir §6).

### 2.3 `LotEntrepot` (`core/models.py:1007-1130`)

| Propriété | Formule |
|---|---|
| `montant_total` | si conditionné : `(quantite_initiale / poids_unitaire_kg) * prix_achat_unitaire` ; sinon `quantite_initiale * prix_achat_unitaire` — **⚠️ deux définitions de `montant_total` existent dans le fichier** (`core/models.py:1007-1012` et une deuxième déclaration identique à `1088-1089` qui écrase la première au chargement Python — dernière définition gagnante, donc la version simple `quantite_initiale * prix_achat_unitaire` sans division par le poids conditionné est celle réellement active) |
| `valeur_actuelle_stock` | `quantite_restante * prix_achat_unitaire` |
| `quantite_perdue_totale` | `Sum(pertes.quantite_perdue)` (Python, pas SQL) |
| `quantite_theorique_restante` | `quantite_initiale - quantite_perdue_totale` |
| `coherence_quantites` | `quantite_restante == quantite_theorique_restante` |
| `ecart_quantite` | `quantite_restante - quantite_theorique_restante` |
| `total_paye_lot` | `Sum(paiements.montant)` |
| `reste_a_payer_lot` | `max(dette_lot - total_paye_lot, 0)` ⚠️ — référence `self.dette_lot`, **attribut non défini dans le modèle** (ni champ, ni property) — code potentiellement cassé si appelé, à vérifier |
| `chiffre_affaires_theorique_lot` | `Sum(Vente.quantite * lot.prix_achat_unitaire)` pour les ventes liées à ce lot |
| `total_facture_lot` | `Sum(factures.montant)` |
| `est_solde` | `total_facture_lot >= montant_total` |
| `est_conditionne` | `bool(produit.poids_unitaire_kg)` |
| `quantite_restante_unites` / `quantite_initiale_unites` | conversion en unités (cartons/sacs) si conditionné, arrondi plancher (`ROUND_FLOOR`) |

### 2.4 `DetailDistribution` (`core/models.py:1453-1466`)

`quantite_restante_calculee` : `self.quantite - Sum(Vente.quantite où detail_distribution=self et est_supprime=False)`. **Ignore complètement le champ stocké `quantite_vendue`** — voir divergence critique §6.

### 2.5 `Vente` (`core/models.py:1627-1729`)

| Propriété | Formule |
|---|---|
| `total_vente` | `quantite * prix_vente_unitaire` (déclarée deux fois dans le fichier, `1627-1629` et `1650-1654`, résultat identique) |
| `produit_nom` / `produit_complet` | via `detail_distribution.lot.produit.nom` (+ spécification) |
| `est_credit` | `mode_paiement == 'credit'` |
| `est_recouverte` | ⚠️ `agent.total_recouvre >= agent.total_ventes` — compare les totaux **globaux** de l'agent, pas ceux propres à cette vente précise (nom trompeur : ce n'est pas "cette vente a été recouvrée" mais "l'agent est globalement à jour") |
| `est_retroactive` | `date_vente.date() < date_creation.date()` |
| `vendeur_reel` | `stagiaire` si renseigné, sinon `agent` |
| `est_recouvrable_par_superviseur` | `True` si comptant, ou si dette totalement soldée (`montant_restant == 0`) |
| `quantite_en_kg` | si produit conditionné : `quantite * poids_unitaire_kg` ; sinon `quantite` telle quelle — **formule pivot réutilisée par `agents/views.py` (détail agent) et `paie/services/salaire_calculator.py`** |

### 2.6 `AffectationLotSuperviseur.quantite_resume()` — méthode d'affichage, pas propriété financière.

### 2.7 `ClotureMensuelle`

`est_ouverte` : `not est_cloture`. `duree_periode` : `(date_fin - date_debut).days + 1`.

### 2.8 `VersementBancaire` (`core/models.py:2018-2064`)

| Propriété | Formule |
|---|---|
| `type_versement` | `'mixte'` si les deux montants > 0, `'vente'`/`'autre'`/`'aucun'` sinon |
| `montant_total` | `montant_vente + montant_hors_vente` |
| `total_depenses_associees` | `Sum(depenses.montant)` (dépenses liées via `Depense.versement`) — cohérent avec le fait que `Depense.versement` n'est jamais renseigné en pratique : **cette propriété retournera toujours `0` pour tout versement créé après la transition ROT** (voir §6) |
| `cash_depense_reel` | `montant_vente + total_depenses_associees` |
| `est_equilibre` | `total_depenses_associees <= montant_hors_vente` |

### 2.9 `PaiementFournisseur.acteur_paiement` — `effectue_par or superviseur` (fallback vers le champ déprécié si le champ actif est vide).

### 2.10 Paie (`paie/services/salaire_calculator.py`, hors `core/models.py` mais central au reporting financier)

| Type d'agent | Formule (résumé, détail en §4.3) | Dépendance temporelle |
|---|---|---|
| `terrain` (mamy) | `salaire_base (prorata si date_debut_fonction connue) + kilo_total * incentive_par_kg` | Prorata dépend de `agent.date_debut_fonction` ; si absent, salaire plein sans proratisation réelle |
| `agent_gros` | Barème par palier sur `cartons` (`Sum(Vente.quantite)`) : `<150` — linéaire, `150-199` — `50000` fixe, `—200` — `90000` fixe | non |
| `entrepot` (superviseur) | `salaire_base + dotation_fonction (RegleSalaire type_agent='superviseur' — **jamais alimentée en pratique**, voir §6) + bonus par palier sur le kilo total de ses mamies (`<18000`—0%, `<27000`—4%, `<37000`—6%, `—37000`—8%)` | recalcule intégralement chaque mamie supervisée à chaque génération |

---

## 3. Énumérations réelles

Valeurs déclarées dans les `choices` Django vs valeurs réellement présentes en base (requête `SELECT DISTINCT` sur `c2679735c_dams`, 2026-07-17).

| Modèle.champ | Valeurs déclarées | Valeurs réelles en base | —cart |
|---|---|---|---|
| `Agent.type_agent` | `direction, rot, entrepot, terrain, agent_gros, agent_polivalent, stagiaire, gestionnaire_stock` | les 8 mêmes valeurs présentes (4 direction, 2 rot, 4 entrepot, 63 terrain, 10 agent_gros, 6 agent_polivalent, 10 stagiaire, 1 gestionnaire_stock) | aucun |
| `Agent.type_contrat` | `prestation, stage, cdd, cdi` | `prestation` (94), `stage` (6) | `cdd`/`cdi` jamais utilisés |
| `Vente.type_vente` | `gros, detail` | `detail` (2246), `gros` (767) | aucun |
| `Vente.mode_paiement` | `comptant, credit` | `comptant` (3013) — **100%** | `credit` jamais utilisé en pratique (mais fonctionnellement c—blé, voir §1.15/§4) |
| `Dette.statut` | `en_cours, partiellement_paye, paye, en_retard` | — table vide (0 ligne) | aucune valeur observable |
| `PaiementDette.mode_paiement` | `espece, cheque, virement, mobile` | — table vide (0 ligne) | aucune valeur observable |
| `Depense.categorie` | `ACHAT_MARCHANDISE, TRANSPORT_MARCHANDISE, CARBURANT, MAINTENANCE_VEHICULE, FRAIS_OPERATIONNELS, TRANSFERT, DIVERS` | les 7 valeurs présentes + **21 lignes `NULL`** | ⚠️ `NULL` malgré `default='DIVERS'` sans `null=True` — voir §6 |
| `Depense.source` | `ROT, MIGRATION, ADMIN` | `ROT` (478) + **21 lignes `NULL`** | `MIGRATION`/`ADMIN` jamais utilisés ; `NULL` malgré `default='ROT'` — voir §6 |
| `MouvementStock.type_mouvement` | `RECEPTION, DISTRIBUTION, VENTE, RETOUR` | `RECEPTION` (261), `DISTRIBUTION` (605) | `VENTE`/`RETOUR` **jamais écrits** — aucune vente ni retour ne crée de `MouvementStock` dans le code actuel |
| `DistributionAgent.type_distribution` | `TERRAIN, AUTO, STAGIAIRE` | `TERRAIN` (2699), `AUTO` (152), `STAGIAIRE` (26) | aucun |
| `Client.type_client` | `grossiste, detail, particulier` | — table vide (0 ligne) | aucune valeur observable (`Client` jamais utilisé par les flux de vente actifs) |
| `RegleSalaire.type_agent` | `terrain, agent_gros, superviseur` | `terrain`(1), `agent_gros`(1), `superviseur`(1) | ⚠️ **une 4— valeur `'entrepot'` existe en base**, créée par `direction/management/commands/init_regles_remuneration.py`, hors du `choices` déclaré (Django ne contraint pas les `choices` au niveau DB) — voir §6 |
| `JournalModificationDistribution.type_action` | `CREATION, MODIFICATION, SUPPRESSION, RESTAURATION` | — table vide (0 ligne) | modèle jamais alimenté |
| `Alerte.type_alerte` | `solde, stock, prix, activite` | `solde` (12) uniquement | `stock`/`prix`/`activite` jamais générés (services vides, voir §1.3) |
| `Alerte.niveau` | `info, warning, critique` | `critique` (12) uniquement | `info`/`warning` jamais générés |

Autres booléens/valeurs de contrôle observées en base :
- `Vente.est_supprime` : 100% `False` (3013 lignes) — pas de soft-delete constaté dans les données actuelles.
- `PaiementFournisseur.est_supprime` : 100% `False` (246 lignes).
- `Salaire.valide` : 100% `False` (21 lignes) — aucune paie encore figée dans cette base.
- `ClotureMensuelle.est_cloture` : 100% `True` (32 lignes) — pas de clôture en brouillon actuellement.
- `DistributionAgent.est_retroactive` : réparti 1374 `False` / 1503 `True` — champ jamais positionné programmatiquement dans les flux lus (voir §1.11), donc l'origine de cette répartition n'est pas expliquée par le code exploré.
- `Vente.ancienne_vente` : réparti 1397 `False` / 1616 `True`.

---

## 4. Workflows métier bout en bout

### 4.1 Réception marchandise — affectation superviseur — distribution agent — vente — recouvrement

Ce flux, présenté comme linéaire dans `rules/ARCHITECTURE.md`, est en réalité **implémenté par au moins trois chemins de code concurrents et non unifiés** selon le point d'entrée (app `marchandise`/`vente`, app legacy `core`, app legacy `agents`). La BI doit traiter ces trois chemins comme des sources potentiellement divergentes des mêmes tables.

#### A. Réception d'un lot — `marchandise.views.reception_lot` (`marchandise/views.py:90-102`)

Formulaire réellement utilisé : `core.forms.ReceptionLotForm` (**pas** un form de `marchandise/`).
1. `ReceptionLotForm(request.POST)` — `form.save(commit=False)` (`core/forms.py:209-260`) : résout/crée `Fournisseur` et `Produit` (get_or_create), génère `reference_lot` (`AAAAMMJJ-NNNN`), fixe `quantite_restante = quantite_initiale`.
2. `lot.receptionne_par = agent` (`marchandise/views.py:94`).
3. `lot.save()` — `LotEntrepot.save()` recalcule `valeur_stock_initiale` et applique les gardes-fous.
4. `MouvementStock.objects.create(type_mouvement='RECEPTION', ...)` (`marchandise/views.py:96-102`).

⚠️ **Aucun `transaction.atomic()`** n'englobe les étapes 3 et 4 — deux écritures séparées non protégées ensemble.

#### B. Affectation d'un lot à un superviseur — `AffectationSuperviseurForm.save()` (`marchandise/forms.py:130-177`, dans `transaction.atomic()` ligne 141)

1. `AffectationLotSuperviseur.objects.create(lot, superviseur, quantite_initiale=quantite, quantite_restante=quantite, attribue_par=agent)` — `prix_gros`/`prix_detail` **restent `NULL`**.
2. `lot.quantite_restante -= quantite` ; `lot.quantite_disponible_rot += quantite` (champ de compatibilité, incrémenté, jamais décrémenté dans ce flux) ; `lot.save(...)`.
3. **Si `agent_terrain` renseigné** (cas normal, distribution directe) : `DistributionAgent.objects.create(...)` puis `DetailDistribution.objects.create(lot, quantite, prix_gros=None, prix_detail=None)`, puis `affectation.quantite_restante = 0`, `affectation.agent_terrain_direct = agent_terrain`.
4. **Si `agent_terrain` absent** (cas d'exception) : aucune écriture supplémentaire — le stock reste « en attente » chez le superviseur (`affectation.quantite_restante = quantite`), à charge pour l'app `vente` de le distribuer plus tard.

Correction administrative (`AffectationLotService.corriger_affectation`, `marchandise/services.py:27-88`, `transaction.atomic()` + `select_for_update()`) : recalcule le delta de quantité, met à jour `LotEntrepot`, `AffectationLotSuperviseur`, et si une distribution directe est retrouvée (résolution **heuristique** par lot+superviseur+agent_terrain_direct, refusée si ambiguë), aussi `DetailDistribution.quantite` et `DistributionAgent.quantite_totale`.

#### C. Distribution exceptionnelle (superviseur détient encore du stock) — `vente.DistributionForm.save()` (`vente/forms.py:84-110`, `transaction.atomic()` ligne 92)

1. `DistributionAgent.objects.create(...)` + `DetailDistribution.objects.create(lot=affectation.lot, quantite, prix_gros=None, prix_detail=None)`.
2. `affectation.quantite_restante -= quantite` ; **`LotEntrepot` n'est jamais retouché ici** (déjà décompté à l'affectation initiale).

Différence clé avec B : peut être appelée plusieurs fois sur la même affectation (distribution partielle progressive), ne renseigne jamais `agent_terrain_direct`, gère aussi l'auto-distribution (`agent_terrain == superviseur`).

#### D. Vente + recouvrement automatique — `vente.VenteForm.save()` + `vente.views.enregistrer_vente` (`vente/views.py:93-103`)

Dans `transaction.atomic()` (ligne 93, ouvert **dans la vue**, pas dans le form) :
1. `vente = form.save()` — `Vente.objects.create(..., mode_paiement='comptant')` (fixé en dur par le form, `vente/forms.py:225`) — déclenche `Vente.save()` qui incrémente `detail_distribution.quantite_vendue`.
2. `Recouvrement.objects.create(agent=vente.agent, superviseur=agent, vente=vente, montant_recouvre=vente.total_vente, date_recouvrement=vente.date_vente)`.

`prix_vente_unitaire` est une **saisie manuelle obligatoire** dans `VenteForm` (`vente/forms.py:152-157`) — ni `Agent.get_prix_vente()` ni `type_vente_par_defaut()` ne sont appelés côté serveur pour la calculer ; `type_vente_par_defaut()` n'est utilisé que côté AJAX (`vente/views.py:177`) pour **suggérer** une valeur au front, jamais pour valider côté serveur.

#### E. Chemins parallèles legacy (toujours actifs, non routés par `marchandise`/`vente`)

- **`core.views.enregistrer_vente`** (`core/views.py:1070-1106`) : sélectionne `VenteDetailAgentForm`/`VenteGrosAgentForm`/`VenteSuperviseurForm` (`core/forms.py:790,829,868`) selon `type_agent`, dérive le prix depuis `DetailDistribution.prix_gros/prix_detail` — **ces champs étant toujours `NULL` depuis que `marchandise`/`vente` ne les renseignent plus**, ce chemin est structurellement cassé pour toute donnée créée après la bascule vers les apps capacité, sauf s'il reste utilisé sur d'anciennes données. Ne crée pas de `Recouvrement` automatiquement — `core.views.creer_recouvrement` (`core/views.py:1906`) est un point d'entrée manuel séparé où l'agent/superviseur sélectionne une `Vente` existante à recouvrer.
- **`agents.views.detail_distribution_sup`** (`agents/views.py:832-880`, `transaction.atomic()` ligne 847) : sélectionne `VenteTerrainForm`/`VenteAgentGrosForm`/`VenteFlexForm` selon `type_agent` (défaut `VenteFlexForm` pour tout profil hors `terrain`/`agent_gros`, y compris `agent_polivalent`/`stagiaire`/`entrepot`), crée `Vente` + `Recouvrement` dans la même transaction — **ne met jamais à jour `detail.quantite_vendue`** après la vente.
- **`agents.views.vente_distribution_rapide`** (`agents/views.py:883-949`, **sans `transaction.atomic()`**) : solde intégralement le reliquat (`reste = detail.quantite - detail.quantite_vendue`, utilise le **champ stocké**, pas `quantite_restante_calculee`), crée `Vente` + `Recouvrement`, et **met à jour explicitement `detail.quantite_vendue += quantite`**.
- **`agents.views.distribuer_lot_agent`** (`agents/views.py:284-308`, commentée `# deprecier` mais **toujours routée** `agents/urls.py:22` et **toujours liée** depuis `core/templates/core/distribution/liste_distributions.html:17`), **`distribution_superviseur`** (`agents/views.py:363-427`, triple contrôle transactionnel), **`distribution_superviseur_override`** (`agents/views.py:310-361`, réservée à l'utilisateur `"jeanclaude.sup"` en dur — `agents/views.py:314` : `if superviseur.user.username != "jeanclaude.sup":`, prix de gros forcé) sont trois canaux de distribution supplémentaires, distincts de B/C.
- `core/services/distribution_service.py` (`DistributionService`) implémente encore un **quatrième modèle de distribution** (multi-lots, `etat_produit`, écrit dans `MouvementStock` de type `DISTRIBUTION`) mais **n'est appelé par aucune vue de `marchandise`, `vente`, `core` ou `agents`** dans le périmètre exploré — probable code mort ou service non branché, à confirmer avant d'en tenir compte pour la BI.

**Conséquence directe pour la BI** : `Vente`, `Recouvrement`, `DistributionAgent`, `DetailDistribution` peuvent avoir été écrits par au moins 5 chemins de code différents (D, et les 3 sous E, plus l'admin Django), avec des garanties transactionnelles et des mises à jour de `quantite_vendue` incohérentes selon le chemin. Il n'existe **aucun moyen fiable, au niveau des données, de savoir par quel chemin une ligne a été créée** (pas de champ `source`/`created_via` sur `Vente`).

#### Divergence critique : deux définitions concurrentes du « reste à vendre »

- `DetailDistribution.quantite_restante_calculee` (property, `core/models.py:1453-1466`) : `quantite - Sum(Vente.quantite où est_supprime=False)` — **recalculée en SQL à chaque appel, ignore le champ stocké `quantite_vendue`**. Utilisée par `vente/forms.py` (`VenteForm`, `DistributionForm`) et `marchandise/services.py`.
- `detail.quantite - detail.quantite_vendue` (champ stocké, mis à jour uniquement par `Vente.save()` et `agents.views.vente_distribution_rapide`) — utilisé par `agents/views.py:900` (`vente_distribution_rapide`) et par le formulaire `SupervisorDistributionForm`/`DistributionSuperviseurSimplifieeForm` d'`agents/forms.py`.

Si une vente est créée sans que `quantite_vendue` soit synchronisé (`detail_distribution_sup`, voir ci-dessus) ou si une vente est soft-supprimée (`est_supprime=True`, aucune restitution de `quantite_vendue` observée), les deux définitions divergent : l'une peut indiquer un stock épuisé quand l'autre indique encore du stock disponible, ou l'inverse. **Pour la BI, `quantite_restante_calculee` (recalcul depuis `Vente`) est la définition la plus proche de la réalité économique** (c'est celle documentée comme référence par `marchandise/APP_MARCHANDISE.md:107`), mais le champ stocké `quantite_vendue` reste ce que lisent certaines vues encore actives.

### 4.2 Dépense ROT — versement bancaire — recouvrement superviseur — ROT — clôture mensuelle

Contrairement à l'intitulé, **ce ne sont pas des étapes d'un seul pipeline mais quatre écritures indépendantes**, reliées uniquement par les *calculs de solde* (propriétés `Agent` et service `cloture_service.py`), jamais par une chaîne de `transaction.atomic()` commune.

- **Dépense** — `core.views.creer_depense` (`core/views.py:1852`) — `DepenseForm.save(agent=agent)` (`core/forms.py:1357-1399`) : crée `Depense(effectue_par=agent, source='ROT')`. `Depense.versement` **n'est jamais renseigné** par ce flux.
- **Versement bancaire** — `core.views.creer_versement` (`core/views.py:1519`) — `VersementForm.save(rot=agent_connecte)` (`core/forms.py:1278-1303`) : valide `rot.est_rot`, fixe `versement.effectue_par = rot`, crée les `RecuVersement` associés. `VersementBancaire.superviseur` (déprécié) **n'est jamais écrit** ici.
- **Recouvrement superviseur — ROT** — `agents.views.recouvrer_superviseur` (`agents/views.py:1277-1334`) — `RecouvrementSuperviseurForm` : action manuelle, `rec.rot = rot; rec.save()`. Pas de transaction, pas de déclenchement automatique par une vente ou un recouvrement agent.
- **Clôture mensuelle** — deux points d'entrée :
  - **CLI** `direction/management/commands/cloturer_mois.py` : `python manage.py cloturer_mois [--start YYYY-MM --end YYYY-MM]`, sinon mois précédent par défaut. Pour chaque superviseur actif, dans `transaction.atomic()` (ligne 79) : `update_or_create(ClotureMensuelle, solde_ouverture=<dernière clôture ou 0>, est_cloture=False)`, puis si non déjà clôturée, `calculer_solde_periode(...)`, `est_cloture=True`, `date_cloture=now()`, puis `superviseur.remettre_solde_operationnel_a_zero(cloture=cloture)`. **Aucune planification (cron/Celery beat) trouvée dans le dépôt — commande strictement manuelle/on-demand.**
  - **Vue web** `direction.views.cloturer_periode` (`direction/views.py:1346-1377`, réservée à `est_direction`) : force `date_fin_periode = hier`, recalcule le solde, marque la clôture, appelle la même méthode de remise à zéro. La fonction `ouvrir_nouvelle_periode` (`direction/views.py:1380-1398`) qui devrait créer la clôture en amont **n'est appelée par aucune URL — code mort**.
  - **Cadence réelle : manuelle, à la demande**, jamais mensuelle stricte imposée par le code (cohérent avec le commentaire du modèle `ClotureMensuelle`).

`calculer_solde_periode` (`direction/services/cloture_service.py:11-64`) :
```
solde_cloture = solde_ouverture
              + Sum(Vente.quantite * prix_vente_unitaire)   [agent=superviseur, période]
              + Sum(Recouvrement.montant_recouvre)          [superviseur=superviseur, période]
              - Sum(Depense.montant)                        [versement__superviseur=superviseur, période]
              - Sum(VersementBancaire.montant_vente)        [superviseur=superviseur, période]
```

⚠️ **Bug de calcul en production, pour la BI c'est le point le plus important de cette section** : les deux dernières lignes filtrent sur `Depense.versement__superviseur` et `VersementBancaire.superviseur` — les **champs dépréciés**, jamais alimentés par les flux de création actuels (`DepenseForm.save()` ne renseigne jamais `versement` ; `VersementForm.save()` ne renseigne jamais `superviseur`). **Conséquence : pour toute dépense/versement créé après la bascule ROT (`migrer_versements_depenses_rot.py:17`, date pivot documentée dans `rules/ARCHITECTURE.md` comme `DATE_DEBUT_ROT = date(2026,1,1)`), `calculer_solde_periode` calcule des dépenses et versements à `0`, faussant `solde_cloture`.** Le même biais affecte `Agent.total_depenses_superviseur`, `Agent.total_versements_superviseur`, `Agent.solde_reel_superviseur`, `Agent.solde_operationnel_superviseur`. En parallèle, `agents/services/rot_dashboard_service.py:98-118` calcule correctement sur `effectue_par` — donc **le dashboard ROT et le solde superviseur/clôture peuvent afficher des chiffres incohérents entre eux sur les mêmes données**.

`AjustementSolde` n'est créé **que** par `Agent.remettre_solde_operationnel_a_zero()` (`core/models.py:379-404`), elle-même appelée uniquement par les deux points d'entrée de clôture ci-dessus, et seulement si `solde_reel_superviseur != 0` au moment de la clôture.

### 4.3 Recouvrement agent — superviseur vs superviseur — ROT (cadences)

- **`Recouvrement` (agent — superviseur) : automatique, à chaque vente comptant.** Confirmé dans `vente/views.py:93-103`, `agents/views.py:847-866` (`detail_distribution_sup`) et `agents/views.py:921-939` (`vente_distribution_rapide`, cette dernière **sans** `transaction.atomic()`, contrairement aux deux autres chemins).
- **`RecouvrementSuperviseur` (superviseur — ROT) : manuel, différé**, jamais déclenché automatiquement par une vente ou un `Recouvrement`. `RecouvrementSuperviseur.clean()` calcule un `cash_restant` mais **ne lève jamais de `ValidationError`** — garde-fou de non-dépassement du cash disponible présent dans le code mais fonctionnellement inactif.

### 4.4 Paiement fournisseur

Deux chemins :
- **Facture + paiement couplés** — `core.views.gestion_factures_lot` — `FactureLotForm.save(lot, user, rot=request.user.agent)` (`core/forms.py:403-424`, `transaction.atomic()`) : crée `FactureLotEntrepot`, puis si un montant est renseigné, `PaiementFournisseur(effectue_par=rot, cree_par=user)`, puis lie `facture.paiement_fournisseur`. ⚠️ **`rot=request.user.agent` n'est jamais vérifié comme étant réellement `type_agent='rot'`** ici (contrairement au chemin ci-dessous) — n'importe quel agent connecté peut se retrouver enregistré comme auteur du paiement.
- **Paiement seul** — `direction.views.creer_paiement_fournisseur`/`modifier_paiement_fournisseur` — `PaiementFournisseurForm` (`Meta.fields` exclut `superviseur`) : `self.fields['effectue_par'].queryset = Agent.objects.filter(type_agent='rot')` (`core/forms.py:1455-1457`) — restriction correcte ici. Pas de `FactureLotEntrepot` créée dans ce chemin. Pas de `transaction.atomic()`.

Correction admin (`core/admin.py:609-627`) : bloque si `total_paye + montant > lot.valeur_stock_initiale`.

### 4.5 Génération et validation de la paie

Formules détaillées en §2.10. Séquence d'écriture (`paie/services/salaire_generation_service.py`, `@transaction.atomic` ligne 13) :
1. Garde anti-doublon **au niveau service** : `if Salaire.objects.filter(date_debut=, date_fin=).exists(): raise ValueError` (lignes 17-21) — bloque dès qu'**un** enregistrement existe pour la période, brouillon ou validé. Combinée à la garde de la **vue** (`paie/views.py:354-358`, bloque seulement si `valide=True`), la fonctionnalité de « régénération d'un brouillon » suggérée par le mode Aperçu (`deja_genere=True`, `deja_valide=False`) est en réalité **impossible** : toute tentative échoue dès qu'un brouillon existe.
2. Agents ciblés : `Agent.objects.filter(est_actif=True, type_agent__in=['terrain','agent_gros','entrepot'])`.
3. Dispatch par type — `calcul_salaire_mamy` / `calcul_salaire_gros` / `calcul_salaire_superviseur`.
4. `Salaire.objects.create(agent, date_debut, date_fin, salaire_base=calc['salaire_base'], incentive=calc.get('incentive',0)+calc.get('bonus',0), salaire_total=calc['salaire_total'])` — pour un superviseur, `incentive` stocke le **bonus**, la `dotation_fonction` n'a pas de champ dédié dans `Salaire` (absorbée uniquement dans `salaire_total`).

Validation (`paie/views.py:410-420`, `SalaireValidationView.post`) : `Salaire.objects.filter(date_debut=, date_fin=, valide=False).update(valide=True)` — bulk update SQL unique, pas de `transaction.atomic()` explicite (inutile, `.update()` est déjà atomique).

Cadence réelle : mensuelle par convention d'usage (bornes calculées via `calendar.monthrange`), mais rien dans le code n'impose une cadence — génération et validation sont deux actions manuelles distinctes déclenchées depuis l'interface direction.

⚠️ Un **second moteur de calcul de salaire existe**, non branché sur le pipeline `paie` : `direction/services/salaire_service.py` (`SalaireService`) implémente une formule totalement différente (`salaire_base = 50000` fixe si `quantite_totale > 100` sinon `quantite_totale * 250` ; incentive basé sur `Recouvrement.bonus_accorde=True` avec un dictionnaire de conversion carton codé en dur). S'il est encore appelé par une vue `direction/views.py` non explorée en détail ici, c'est une **deuxième source de vérité pour les salaires**, à vérifier explicitement avant toute reprise en dbt.

⚠️ **`RegleSalaire(type_agent='superviseur')` sans dotation effective** : `init_regles_remuneration.py:9-12` crée la règle de dotation avec `type_agent="entrepot"` (hors des `choices` du modèle, qui n'admet que `terrain`/`agent_gros`/`superviseur`), alors que `calcul_salaire_superviseur` interroge systématiquement `RegleSalaire.objects.filter(type_agent="superviseur")` — la dotation initialisée par la commande **n'est donc jamais trouvée**, `dotation_fonction` vaut structurellement `0` pour tous les superviseurs, sauf création manuelle d'une ligne `type_agent='superviseur'` ailleurs (aucune trace trouvée).

---

## 5. Frontières d'app et permissions par capacité

Pour `core`, `marchandise`, `vente`, `paie`, `agents`, `direction`, `surveillance`, `analyse_champ`, se reporter d'abord aux `APP_*.md` respectifs (à jour sur le périmètre fonctionnel déclaré) et à `rules/ARCHITECTURE.md`. Cette section ne documente que les **permissions réelles telles que vérifiées dans le code**, et les cas non couverts par un `APP_*.md`.

### 5.1 `direction` — permissions réelles par vue (non documentées dans `APP_DIRECTION.MD`)

| Vue | Mécanisme réel | Accès accordé |
|---|---|---|
| `DashboardView`, `AgentDashboardView`, `SuperviseurListView`, `AgentTerrainListView`, `AgentDetailView`, `ProductListView`, `ProductDetailView` | `LoginRequiredMixin` seul | **tout utilisateur connecté**, quel que soit `type_agent` |
| `SuperviseurDetail`, `RotDetailView` | **aucun décorateur** | tout utilisateur connecté (protection dépend d'un middleware global éventuel, non vérifié) |
| `ToutesLesVentesView`, `ExportVentesExcelView`, `ExportVentesPDFView` | `UserPassesTestMixin` : `est_direction or est_superviseur` | `direction`, `entrepot` |
| `dashboard_justificatif`, `liste_factures_fournisseurs`, `liste_versements_direction`, `detail_versement_direction`, `liste_depenses`, `detail_depense`, `analyse_financiere_direction`, `liste_paiements_fournisseur` + CRUD, `liste_clotures`, `apercu_cloture`, `admin_create_agent` | `@login_required` seul | **tout utilisateur connecté**, y compris un agent terrain, peut créer/modifier un paiement fournisseur ou consulter les soldes de clôture |
| `AnalyseFournisseursView`, `DetailFournisseurView` | `UserPassesTestMixin` : `est_direction` | `direction` uniquement |
| `cloturer_periode` | garde locale manuelle dans le corps de la vue : `if not est_direction: raise PermissionDenied` | `direction` uniquement |
| `calcul_salaires`, `detail_salaire_agent`, `export_salaires_excel`, `api_calcul_salaire_rapide` | `@user_passes_test(... est_direction)` | `direction` uniquement |
| `suivi_distributions`, `monitoring_alertes_dashboard` | **aucun décorateur du tout** | accès public, y compris non authentifié |

**— signaler explicitement pour la BI** : l'app `direction` n'a pas de gouvernance de sécurité homogène malgré son rôle de « couche de gouvernance et d'audit » (`APP_DIRECTION.MD:5`) — une majorité de vues financières sensibles (paiements fournisseurs, versements, dépenses, clôtures) sont accessibles à tout agent authentifié, et deux vues n'ont même pas `@login_required`.

### 5.2 `surveillance` — mixin de permission unique

Toutes les vues héritent de `SurveillanceAccessMixin` (`surveillance/mixins.py:3-15`) : `is_superuser` ou `agent.est_direction`. **Aucune vue surveillance n'autorise le superviseur** — à noter, `APP_SURVEILLANCE.md:7` (« aux profils de direction et de contrôle ») peut laisser croire à un accès superviseur, ce n'est pas le cas.

### 5.3 `agents` — accès dérogatoire hardcodé

`agents.views.distribution_superviseur_override` (`agents/views.py:314`) : `if superviseur.user.username != "jeanclaude.sup": ...` — canal de distribution avec override forcé du prix de gros, réservé à un **nom d'utilisateur Django littéral**, pas à un rôle ou une permission. Documenté fonctionnellement par `APP_AGENT.md:81` mais **pas qualifié de dette technique/risque** par ce document.

### 5.4 —cart de gouvernance déjà documenté par le projet — `docs/WORKFLOW-METIER.md:76-113`

Ce document interne (2026-07-11, « référence vivante ») constate déjà que les liens menu « Stock Entrepôt » (`liste_lots`) et « Dépenses » (`liste_depenses`/`creer_depense`/`detail_depense`, tous `core/views.py`) sont conditionnés par **username en dur** dans `core/templates/base.html:502,509` (`ismael.diawara`, `abdoulaye.kone`), alors que les vues elles-mêmes n'ont **aucun guard de rôle**, seulement `@login_required` — cohérent avec le constat §5.1 ci-dessus pour `direction`, et confirmant que ce n'est pas un cas isolé mais un pattern répété dans le projet (menu conditionné à vue protégée).

### 5.5 Duplication de logique `core` vs `agents` — déjà documentée par `docs/audit/comparaison-core-vs-agents.md`

Ce document interne (2026-07-07, brouillon non tranché) recense un doublon confirmé (`core.views.tableau_de_bord_superviseur`, jamais routé, code mort) et sept paires de vues fonctionnellement équivalentes mais dupliquées entre `core` et `agents` (distribution, vente, recouvrement, détail agent, CRUD agent, gestion de lots). Pour la BI, cela signifie concrètement que **plusieurs vues actives peuvent écrire les mêmes tables (`Vente`, `Recouvrement`, `DistributionAgent`) avec des règles de validation potentiellement différentes** — cf. §4.1.E ci-dessus, qui recoupe et détaille cette même observation au niveau des transactions et des formulaires.

### 5.6 `analyse_champ`

Conforme à `APP_ANALYSE_CHAMP.md` — proxy de lecture pur vers `dams_agro` via `API_URL`, aucune table `core_*` n'est concernée, non pertinent pour le modèle dbt basé sur PostgreSQL local sauf si une réplique de l'API dams_agro est prévue séparément.

---

## 6. Écarts identifiés

Liste consolidée, sans arbitrage — chaque écart cite (a) la doc existante, (b) le code, (c) l'état réel de la base si disponible.

### 6.1 Divergences critiques (impact direct sur les métriques BI)

1. **Solde superviseur / clôture mensuelle sous-évalués structurellement.** (b) `Agent.total_depenses_superviseur` (`core/models.py:688-705`), `Agent.total_versements_superviseur` (`core/models.py:707-720`), `Agent.solde_operationnel_superviseur` (`core/models.py:858`), `direction/services/cloture_service.py:37,44` filtrent tous sur les champs dépréciés `Depense.versement__superviseur` / `VersementBancaire.superviseur`. Aucun flux de création actuel (`DepenseForm.save()`, `VersementForm.save()`) ne renseigne ces champs — ils utilisent `effectue_par`. (c) Non vérifié en base faute de requête croisée date-pivot ROT, mais le mécanisme de filtrage garantit `0` pour toute donnée créée après la bascule ROT documentée par `migrer_versements_depenses_rot.py:17`. **Aucun `APP_*.md` ni ADR ne documente ce risque.**

2. **`quantite_restante_calculee` (recalcul SQL depuis `Vente`) vs `quantite - quantite_vendue` (champ stocké) : deux définitions concurrentes du reste à vendre sur `DetailDistribution`.** (b) `core/models.py:1453-1466` vs usages dans `agents/views.py:900,944-945`. Une vente créée via `agents.views.detail_distribution_sup` ne met jamais à jour `quantite_vendue`, créant un écart potentiel avec les vues qui s'appuient sur ce champ stocké. Non documenté par `APP_MARCHANDISE.md`/`APP_VENTE.md`.

3. **Au moins 5 chemins de code créent des lignes `Vente`/`Recouvrement`/`DistributionAgent`**, avec des garanties transactionnelles hétérogènes (`vente/views.py` : atomique ; `agents.views.vente_distribution_rapide` : non atomique ; `core.views.enregistrer_vente` : structurellement cassé pour les données post-bascule car dépend de `DetailDistribution.prix_gros/prix_detail` toujours `NULL`). Aucun champ ne permet de tracer par quel chemin une ligne a été créée. Documenté partiellement par `docs/audit/comparaison-core-vs-agents.md` (doublons de vues) mais jamais quantifié au niveau transactionnel.

4. **`RegleSalaire.dotation_fonction` du superviseur jamais lue** : `init_regles_remuneration.py` crée la règle avec `type_agent='entrepot'` (hors `choices`), `calcul_salaire_superviseur` lit `type_agent='superviseur'` — `dotation_fonction` vaut structurellement `0` pour tous les superviseurs. Non documenté par `APP_PAIE.md`.

5. **`RegleSalaire.get_salaire_base` fallback mort** : `salaire_calculator.py:43-48` cherche `regle.salaire_base`/`montant_base`/`salaire_fixe`, aucun de ces attributs n'existe sur le modèle `RegleSalaire` (`core/models.py:2440-2454` ne définit que `dotation_fonction`, `incentive_par_kg`, `incentive_par_carton`) — code mort, le salaire de base dépend exclusivement de `Agent.salaire_base_personnel`.

6. **Second moteur de calcul de salaire non branché** (`direction/services/salaire_service.py`, `SalaireService`) avec une formule totalement différente de `paie/services/salaire_calculator.py` — à vérifier explicitement s'il est encore appelé quelque part avant toute reprise BI.

### 6.2 Divergences de permissions / sécurité (impact sur la fiabilité des flux, pas sur la formule)

7. `direction/views.py` : la majorité des vues financières (paiements fournisseurs, versements, dépenses, clôtures) n'ont **aucun contrôle `type_agent`**, contrairement à l'image de « couche de gouvernance » de `APP_DIRECTION.MD`. Deux vues (`suivi_distributions`, `monitoring_alertes_dashboard`) n'ont même pas `@login_required`. Voir §5.1.
8. Accès hardcodé par `username` littéral (`"jeanclaude.sup"`, `agents/views.py:314`) pour le canal de distribution à prix forcé — non qualifié de risque par `APP_AGENT.md`.
9. `core.forms.gestion_factures_lot` — `FactureLotForm.save(rot=request.user.agent)` ne vérifie jamais que l'agent est effectivement `type_agent='rot'`, contrairement à `VersementForm.save()` qui le fait.
10. `RecouvrementSuperviseur.clean()` calcule un `cash_restant` mais ne lève jamais de `ValidationError` — garde-fou de non-dépassement présent dans le code mais fonctionnellement inactif.
11. Menu conditionné par `username` en dur (`core/templates/base.html:502,509`) sans garde de vue correspondant — déjà documenté par `docs/WORKFLOW-METIER.md §4`, confirmé être un pattern répété (cf. point 7).

### 6.3 Code mort / incohérences mineures

12. `LotEntrepot.montant_total` est défini deux fois dans `core/models.py` (lignes 1007-1012 et 1088-1089) — la seconde définition écrase la première ; version réellement active : `quantite_initiale * prix_achat_unitaire` (sans division par le poids conditionné).
13. `LotEntrepot.reste_a_payer_lot` référence `self.dette_lot`, attribut non défini nulle part dans le modèle — appel potentiellement en erreur si cette propriété est invoquée.
14. `Vente.total_vente` est défini deux fois (lignes 1627-1629 et 1650-1654), résultat identique — sans impact fonctionnel mais à nettoyer.
15. `Fournisseur.dette_totale` (boucle Python) fait doublon avec `dette_consomme` (agrégation SQL) — deux implémentations du même calcul, risque de divergence d'arrondi.
16. `direction/views.py:ouvrir_nouvelle_periode` (lignes 1380-1398) n'est appelée par aucune URL — code mort.
17. `core.views.tableau_de_bord_superviseur` (`core/views.py:2285-2538`) est un doublon jamais routé de `agents.views.tableau_de_bord_superviseur` (celle-ci active) — documenté par `docs/audit/comparaison-core-vs-agents.md §1` et `docs/audit/audit-app-core.md §6`. Son template associé (`core/dashboard/superviseur.html`) est également manquant sur disque.
18. `core.views.supprimer_agent` (`core/views.py:186`) n'est référencée par aucune URL du projet — code mort, template associé également manquant (`docs/audit/audit-app-core.md §6`).
19. `agents.views.distribuer_lot_agent` est commentée `# deprecier` (`agents/views.py:283`) et son form `SupervisorDistributionForm` porte l'annotation `## Deprecie` (`agents/forms.py:956`), mais la vue reste routée (`agents/urls.py:22`) et **liée depuis un template actif** (`core/templates/core/distribution/liste_distributions.html:17`) — dépréciation documentaire, pas fonctionnelle.
20. `core/services/distribution_service.py` (`DistributionService`) implémente un flux de distribution multi-lots complet mais n'est appelé par aucune vue explorée (`marchandise`, `vente`, `core`, `agents`) — statut à clarifier (code mort, ou service branché ailleurs non exploré) avant d'en tenir compte pour la BI.
21. `core/urls.py` : `toutes_les_dettes` et `tous_les_bonus` sont déclarées deux fois avec des chemins différents (`admin/...` vs `direction/analyses/...`) ; le second écrase le premier au niveau `{% url %}` — anomalie de routage documentée par `docs/audit/audit-app-core.md §2`.
22. `Depense.categorie`/`Depense.source` comptent chacun 21 lignes `NULL` en base malgré l'absence de `null=True` dans le modèle et un `default` non-NULL (`'DIVERS'`/`'ROT'`) — la migration `0094_alter_distributionagent_options_depense_categorie_and_more.py` a réintroduit ces champs après leur suppression en `0045`; l'origine exacte des 21 `NULL` (import brut, backfill incomplet, données antérieures à `0094` non re-remplies) n'a pas pu être tranchée par la lecture du code seul — signalé sans trancher.
23. `RegleSalaire` compte une 4— valeur `type_agent='entrepot'` en base (créée par `init_regles_remuneration.py`), hors du `choices` déclaré par le modèle (`terrain`/`agent_gros`/`superviseur`) — Django ne contraint pas les `choices` au niveau SQL, donc la ligne existe silencieusement sans jamais être lue par le calculateur de paie (cf. 6.1.4).
24. `surveillance` : le seuil « vente rouge » n'est pas une perte stricte mais une marge minimale de **45 FCFA** (`SEUIL_MARGE_MINIMALE`, `surveillance/services/prix_service.py:21-24` et `surveillance/services/surveillance_prix_service.py:21-24`, dupliqué à l'identique dans deux fichiers), et exclut les ventes antérieures à `DATE_PLANCHER_PRIX` (`surveillance/constants.py`) — plus restrictif/nuancé que ce que suggère `APP_SURVEILLANCE.md:41` (« ventes à perte »).
25. `direction/services/dashboard_service.py:get_periodes` ne gère explicitement que `'annee'` et `'mois'` — toute valeur `'semaine'`/`'custom'` (pourtant citée par `APP_DIRECTION.MD:11` comme granularité supportée) retombe silencieusement sur le mois calendaire courant, sans erreur.
26. `direction/services/dashboard_service.py:get_kpis_globaux` : le calcul du CA période filtre `Vente.est_supprime=False` (ligne ~209-219) mais le calcul de la marge brute période (ligne ~295-306) ne filtre pas `est_supprime` — incohérence interne entre deux métriques du même service, à corriger avant réplication dbt.
27. `direction/services/vente_analyses.py:VenteAnalyseService.filter_ventes` ne filtre pas `est_supprime=False` explicitement — à vérifier si un manager par défaut du modèle `Vente` l'exclut déjà (non confirmé par la lecture ciblée) avant de répliquer ce filtre en dbt.
28. —cran (`ToutesLesVentesView`, annotations SQL `ExpressionWrapper`) vs export (`VenteExportService`, properties Python `Vente.total_vente`) : le même queryset filtré est utilisé pour les deux (garantie "au centime près" de `APP_DIRECTION.MD §6` confirmée **au niveau du filtrage**), mais les **modes de calcul du montant affiché diffèrent** (SQL annoté vs property Python) — écart potentiel d'arrondi non exclu, non vérifié en détail sur `Vente.total_vente`/`produit_nom`.
29. `JournalModificationDistribution`, `AjustementSolde` (dans la base explorée), `Client`, `Dette`, `PaiementDette` sont des tables vides ou quasi jamais alimentées par le code actif — à exclure ou traiter comme dimensions vides dans le modèle dbt tant qu'aucune donnée n'y transite.

---

## Note méthodologique finale

Ce document a été produit par lecture intégrale de `core/models.py`, lecture des `APP_*.md`/ADR/audits internes existants, requêtes SQL directes sur la base de développement PostgreSQL, et exploration ciblée (avec citations `fichier:ligne`) des vues/forms/services des apps `marchandise`, `vente`, `core` (legacy), `agents` (legacy), `direction`, `surveillance`, `paie`. Les citations de lignes proviennent de lectures effectuées le 2026-07-17 sur la branche `main` (commit `220c820`) — elles peuvent se décaler avec toute modification ultérieure du code ; en cas de doute, revérifier le numéro de ligne exact avant de s'y fier pour une automatisation (ex. extraction dbt basée sur des offsets de fichier).
