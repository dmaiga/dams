# 📝 Notes de Conception & Spécifications : Module `app_direction` (DAMS)

## 1. Moteurs d’Analyse Extratemporelle & Décisionnelle

Le module `app_direction` agit comme la couche de gouvernance et d'audit de l'application. Contrairement aux modules opérationnels de saisie terrain, il repose exclusivement sur un **paradigme d'injection de services analytiques** encapsulant la complexité des calculs métiers.

### Le Pattern "Snapshot Service"

L'interface de pilotage principale (`DashboardView`) n'effectue aucune agrégation SQL directe au sein de la vue. Elle délègue cette responsabilité au `DashboardSnapshotService`.

* **Pivot Temporel Modulaire** : Le service accepte une granularité dynamique (`semaine`, `mois`, `annee`, `custom`) permettant à la direction de commuter instantanément d'une vision macro-économique annuelle à un audit micro-opérationnel.
* **Génération de Contexte Cohérent** : Le dictionnaire retourné par le snapshot fusionne les données de performance globales avec des structures analytiques précalculées.

---

## 2. Formulaires de Contrôle & Business Rules

### `CalculSalaireForm`

Formulaire d'interrogation et de simulation des rémunérations sous conditions restrictives de sécurité et de volumétrie.

* **Isolation du Queryset (`__init__`)** : La vue filtre dynamiquement le champ `agent` à l'initialisation pour exclure explicitement les profils de type `direction`. Seuls les agents opérationnels (`terrain` et `entrepot`) ayant le statut `est_actif=True` sont éligibles au calcul, classés par ordre alphabétique.
* **Garde-fous Temporels (`clean()`)** :
* **Inversion chronologique** : Interdiction stricte de soumettre une `date_debut` postérieure à la `date_fin`.
* **Contrôle de charge mémoire** : Limitation de l'écart à **90 jours maximum (3 mois)** pour prémunir le serveur contre des opérations d'agrégation de masse pénalisantes sur les tables de distribution et de vente.



---

## 3. Architecture des Services d’Audit des Agents

Le pilotage des forces de vente et des gestionnaires physiques est segmenté en sous-services spécialisés, garantissant une séparation claire des responsabilités :

### A. Pilotage de la Chaîne Logistique Amont (`SuperviseurAnalysisService`)

* Fournit une vision instantanée de la **situation financière post-clôture** pour les profils à hautes responsabilités de trésorerie (`entrepot` et `rot`).
* Isole les capitaux physiques collectés via des méthodes découplées : `get_superviseurs_finance()` et `get_rots_finance()`.

### B. Audit de Zone de Distribution (`SuperviseurAgentsService`)

Utilisé par la vue de détail pour matérialiser les flux croisés au sein d'un entrepôt spécifique :

* `get_agents_ventes(...)` : Extrait les performances individuelles des agents rattachés au superviseur sur une période donnée.
* `get_flux(...)` : Reconstitue le journal des mouvements financiers opérationnels (cash physique encaissé versus versements effectués au ROT).
* `get_matrice_distribution(...)` : Représente la matrice quantitative des produits alloués, vendus et en reliquat au sein du périmètre de l'entrepôt.

### C. Analyse Opérationnelle du Terrain (`AnalyseOperationnelleService`)

* Offre un moteur de filtrage multidimensionnel croisant la temporalité (par défaut, du 1er janvier à la date du jour), l'identifiant unique de l'agent et la référence produit.
* Permet d'isoler les comportements de vente et de déceler les anomalies de distribution à l'échelle de l'agent individuel.

---

## 4. Performance & Optimisation du Tunnel des Ventes (`ToutesLesVentesView`)

La consultation globale des ventes par la direction est une zone critique de l'application (risque d'anomalie de requêtes en boucle *N+1*). Le système implémente une stratégie d'**optimisation SQL agressive** :

### Annotations SQL Unifiées (Zéro Requête en Boucle)

Le Queryset est enrichi à l'aide d'expressions logiques et de sous-requêtes (`Subquery`), reléguant l'intégralité des calculs lourds au moteur de base de données :

```python
# Modèle conceptuel des annotations SQL intégrées dans la vue
qs.annotate(
    total_vente_sql = F("quantite") * F("prix_vente_unitaire"),
    cout_total      = F("quantite") * F("detail_distribution__lot__prix_achat_unitaire"),
    marge           = F("total_vente_sql") - F("cout_total"),
    date_recouvrement = Subquery(dernier_recouvrement.values("date_recouvrement")[:1]),
    stagiaire_nom_complet = Concat(F("stagiaire__user__first_name"), Value(" "), F("stagiaire__user__last_name"))
)

```

* **`total_vente_sql` & `marge**` : Calculent le chiffre d'affaires et la rentabilité nette par ligne de vente en effectuant une jointure implicite vers le coût d'achat du Lot d'origine.
* **`date_recouvrement`** : Injection par `Subquery` de la date précise de la dernière action de recouvrement associée, évitant le chargement ultérieur d'instances de la table `Recouvrement`.
* **Sécurité d'Accès (`UserPassesTestMixin`)** : Restreint structurellement la visibilité de cette vue aux seuls profils `direction` et `superviseur`.

---

## 5. Module d’Audit des Justificatifs Comptables & Flux Bancaires

### A. Consolidation des Factures Fournisseurs

La direction centralise le contrôle des pièces justificatives via deux méthodes distinctes :

* **Vue d'ensemble (`dashboard_justificatif`)** : Réalise une réconciliation macro entre la valeur d'acquisition initiale des stocks fournisseurs (`valeur_stock_initiale`) et la totalité des flux sortants enregistrés sur le compte `VersementBancaire`.
* **Analyse Analytique (`liste_factures_fournisseurs`)** : Utilise un `select_related` sur les relations `lot`, `fournisseur` et `produit` pour lister les pièces téléversées, agréger les montants globaux par entité commerciale et suivre le nombre d'actes d'achat.

### B. Traçabilité Fine des Flux du ROT (`liste_versements_direction`)

Cette vue surveille de manière exclusive l'activité de versement du Responsable des Opérations (`rot`) vers les comptes de l'entreprise :

* **Découpage des Flux** : Le système applique des filtres stricts pour catégoriser la nature des fonds déposés :
* **Vente** : Provenance directe des recouvrements d'exploitation (`montant_vente > 0` et `montant_hors_vente == 0`).
* **Hors-Vente** : Flux de régularisation ou injections externes (`montant_hors_vente > 0` et `montant_vente == 0`).
* **Mixte** : Opérations combinées.


* **Audit des Pièces Manquantes** : Annotation dynamique du nombre de reçus physiques scannés (`nb_recus=Count('recus')`) pour identifier immédiatement les anomalies de versement non adossées à un justificatif bancaire valide.

---

## 6. Pipelines d'Exportation Métier

Pour répondre aux besoins d'audits externes et de réunions comptables, le système délègue l'extraction de données filtrées au service `VenteExportService`.

* **Héritage strict des filtres** : Les fonctions `ExportVentesExcelView` et `ExportVentesPDFView` réutilisent exactement le même moteur de filtrage normalisé (`VenteAnalyseService.filter_ventes`) que la vue web. Cela garantit une correspondance absolue au centime près entre les données affichées à l'écran et les documents téléchargés (`.xlsx` ou `.pdf`).