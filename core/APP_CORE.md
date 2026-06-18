
# 📝 Notes de Conception & Spécifications : Module `core` (DAMS)

## 1. Sécurité & Authentification Personnalisée

Pour simplifier l'utilisation sur le terrain, le système surcharge l'authentification par défaut de Django pour permettre l'identification via le numéro de téléphone portable au lieu du `username` standard.

### `TelephoneBackend`

* **Rôle** : Permettre une connexion transparente des agents via leur numéro de téléphone.
* **Fonctionnement** :
1. Capture la valeur du paramètre `username` (soumise via le formulaire de login) et effectue une recherche sur le champ `telephone` du modèle `Agent`.
2. Utilise `select_related('user')` pour optimiser l'accès à l'instance de l'utilisateur Django sous-jacente en une seule requête SQL.
3. Valide le mot de passe via `user.check_password(password)`.



---

## 2. Cartographie des Rôles et Profils Métier (`Agent`)

Le modèle `Agent` étend `User` via une relation `OneToOneField`. Les agents se répartissent selon une matrice de responsabilités précises :

* **`direction`** : Gestion globale et accès total à l'administration.
* **`rot` (Responsable Opérations)** : Supervision de la chaîne de distribution logistique et collecte des fonds auprès des superviseurs.
* **`entrepot` (Superviseur)** : Point focal physique des stocks en entrepôt et gestionnaire du cash intermédiaire de sa zone.
* **`terrain` (Mami)** : Force de vente au détail sur les marchés.
* **`agent_gros`** : Force de vente en gros.
* **`agent_polivalent`** : Profil hybride disposant de droits étendus de modification.
* **`stagiaire`** : Profil temporaire à expiration automatique.
* **`gestionnaire_stock`** : Dédié aux écritures logistiques purs.

---

## 3. Gestion Strictement Séparée des Soldes Financiers

La refonte financière post-transition impose une distinction claire entre les calculs opérationnels réels (le cash détenu) et les calculs analytiques ou historiques.

### Matrice des Flux du Superviseur (`type_agent='entrepot'`)

```
[Encaissements Agents (Recouvrement)] + [Ventes Personnelles Autorisées] 
                                    - 
                       [Versements Vente au ROT / Banque]
                                    ± 
                           [Ajustement Manuel]
                                    =
                     Solde Opérationnel du Superviseur

```

* **`solde_operationnel_superviseur`** : Représente la quantité exacte de **cash physique** théoriquement détenue par le superviseur à l'instant T. Calculé uniquement sur la période glissante depuis la date de la dernière clôture mensuelle (`date_derniere_cloture`).
* **`cash_disponible_superviseur`** : Somme brute de l'argent collecté auprès des agents de terrain et des ventes directes en entrepôt, **avant** déduction des remises de fonds au ROT.
* **`solde_reel_superviseur`** : Historique / Ancien monde. Ce calcul prend en compte l'historique global (anciennes ventes, dépenses passées désormais obsolètes). Il est **verrouillé à 0.00** dès qu'une clôture mensuelle est validée (`date_derniere_cloture` active).

### Flux de l'Agent de Vente (`terrain` / `agent_gros`)

* **`argent_en_possession`** : Différence stricte entre le montant total de ses ventes enregistrées (`total_ventes`) et l'argent qu'il a effectivement remis à son superviseur (`total_recouvre`).
* **`peut_etre_recouvre`** : Flag booléen indiquant si l'agent détient une encaisse positive (`argent_en_possession > 0`) devant faire l'objet d'un recouvrement par le superviseur.

### Flux du Responsable des Opérations (`rot`)

* **`solde_rot`** : Somme des fonds récupérés auprès des différents superviseurs, diminuée des versements bancaires globaux et des dépenses logistiques directes effectuées.

---

## 4. cycle de Vie et Gestion Temporelle

Le modèle `Agent` embarque deux logiques d'automatisation des contrats directement branchées sur la méthode `save()` :

### Statut Temporaire des Stagiaires

* Si `type_agent == 'stagiaire'`, une période de test stricte de **14 jours** est initialisée à partir de la date de mise en service (`date_mise_service`).
* À l'expiration de ce délai (`timezone.now() > date_expiration`), le flag `@property` `est_expire` passe à `True`, bloquant immédiatement son accès via `a_acces_plateforme`.

### Automatisation contractuelle (Prestation / CDI / CDD)

* **Contrat de Prestation** : Calcul automatique d'une date de fin fixée à **1 mois** après la création si aucune date n'est explicitement spécifiée.
* **CDI** : La date de fin de contrat est automatiquement forcée à `None`.
* **Garde-fous (`clean()`)** :
* Lève une `ValidationError` si un CDD ne possède pas de date de fin.
* Lève une `ValidationError` si un CDI se voit attribuer une date de fin.



---

## 5. Logistique et Traçabilité des Stocks (`LotEntrepot`)

Le modèle `LotEntrepot` est la clé de voûte de la gestion par flux. Il structure l'entrée des marchandises en provenance des fournisseurs.

* **Valorisation à la source** : La méthode `save()` calcule et stocke de façon persistante la `valeur_stock_initiale` (`quantite_initiale * prix_achat_unitaire`) pour garantir la fiabilité des analyses financières historiques en cas de modification ultérieure des prix unitaires.
* **Contrôle d'intégrité** : Le modèle interdit la survenance d'anomalies de stock (Ex: un reliquat `quantite_restante` supérieur au volume d'entrée `quantite_initiale`).

---

## 6. Structure Analytique des Fournisseurs (`Fournisseur`)

Le modèle intègre des passerelles directes avec des services d'analyse pour dissocier la dette contractuelle de la dette de consommation réelle.

* **`dette_contractuelle`** : Valeur totale théorique des marchandises réceptionnées (`quantite_initiale * prix_achat`).
* **`dette_consomme`** : Valeur financière calculée uniquement sur la base des produits **effectivement vendus** sur le terrain (Ventes liées aux détails de distribution issus de ce fournisseur).
* **`dette_restante`** : Représente la valeur due sur les produits écoulés moins les acomptes et paiements déjà effectués (`dette_consomme - total_paye`).

---

## 7. Système d'Alertes Métier (`Alerte`)

Le modèle `Alerte` centralise les notifications critiques poussées vers la direction, les superviseurs ou les agents. Il est catégorisé par niveau de criticité (`info`, `warning`, `critique`) et par déclencheur métier :

* `solde` : Alertes sur les anomalies ou dépassements de solde de cash des superviseurs.
* `stock` : Vieillissement ou dépréciation d'un stock ancien en entrepôt.
* `prix` : Variations suspectes ou forcées des prix de vente constatées sur le terrain.
* `activite` : Détection de baisses d'activité ou d'enregistrements de ventes sur une période donnée.