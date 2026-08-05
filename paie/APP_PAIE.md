# 📝 Notes de Conception & Spécifications : Module `paie` (DAMS)

## 1. Philosophie & Logique Métier du Module

Le module `paie` est chargé du calcul, de l'historisation, de l'exportation et du figeage des rémunérations de l'entreprise. À l'instar d'autres briques de l'écosystème DAMS, il délègue la complexité algorithmique à des services dédiés (`paie.services`), maintenant les vues Django légères et hautement lisibles.

Le système segmente structurellement les effectifs en trois typologies d'agents possédant leurs propres règles de calcul :

1. **Les Mamies (`mamies` / agents de terrain)** : Rémunérées sur un **fixe variable indexé sur le volume réalisé** (voir § 1.bis, changement du 2026-08-03), ajusté au prorata des jours travaillés en cas d'entrée en cours de mois, complété par un système d'incitation (Incentive) indexé sur les kilogrammes ($Kg$) vendus.
2. **Les Agents Gros (`gros`)** : Rémunérés à la performance ou à l'incitation calculée directement sur le volume de cartons vendus.
3. **Les Superviseurs (`superviseurs`)** : Rémunérés sur une assiette fixe (Salaire de base + Dotations de fonction), à laquelle s'ajoutent des bonus calculés sur le volume total cumulé des kilogrammes vendus par les mamies sous leur responsabilité directe.

---

## 1.bis Fixe variable par palier de kg (Mamies, `calcul_salaire_mamy`) — 2026-08-03

Le fixe mensuel des agents terrain n'est plus une valeur statique (`Agent.salaire_base_personnel` /
`RegleSalaire`) : il est déterminé par le volume réalisé sur la période de calcul, **pour tous les
agents `type_agent='terrain'` sans exception individuelle** (les anciens ajustements salariaux
personnalisés type `salaire_base_personnel` ne sont plus lus par `calcul_salaire_mamy`) :

* **≥ 750 kg réalisés sur la période** → fixe théorique de **20 000 FCFA**.
* **< 750 kg** → fixe théorique de **10 000 FCFA**.

Le kg réalisé est calculé **avant** la détermination du fixe (même agrégation `Vente`/`quantite_en_kg`
qu'auparavant pour l'incentive). La proratisation en cas d'entrée en cours de mois (`date_debut_fonction`)
s'applique ensuite sur ce fixe théorique, inchangée dans son principe. L'incentive par kg et le bonus
superviseur restent inchangés.

Cette même règle est répliquée côté BI (`dbt_bi/models/marts/fct_salaires.sql`) pour toute ligne de
salaire dont `date_debut >= 2026-05-01` — les périodes antérieures sont ramenées à 0 dans le BI (jugées
caduques pour le reporting, cf. `dbt_bi/models/marts/fct_salaires.sql` pour le détail et le
raisonnement). Le calcul Django (ce module) et le calcul dbt sont deux implémentations séparées de la
même règle : toute évolution future du seuil/montants doit être répercutée aux deux endroits.

---

## 1.ter Éligibilité des agents à la paie (`agents_eligibles_periode`) — 05/08/2026

`SalaireGenerationService` et `SalaireListeService` partagent la même fonction
`paie.services.agent_eligibilite.agents_eligibles_periode(date_debut, date_fin, type_agent_filter="")`
pour déterminer quels agents (`terrain`, `agent_gros`, `entrepot`) entrent dans le calcul d'une période.

Règle actuelle : un agent est éligible si **`est_actif=True`**, quelles que soient ses dates de
contrat — `est_actif` est la source de vérité du statut courant. Un agent **désactivé** reste éligible
en plus pour les périodes passées où sa fenêtre d'emploi connue (`date_debut_fonction` →
`date_fin_contrat`) chevauche la période demandée (rattrapage historique) ; s'il n'a aucune de ces deux
dates renseignées, aucun rattrapage n'est possible et il reste exclu une fois désactivé.

Historique de la correction :
* **23/07/2026** — le filtre reposait uniquement sur `est_actif=True` (statut au moment de l'appel), ce
  qui excluait à tort un agent désactivé depuis du calcul de ses salaires pour des mois où il était
  pourtant en poste (rattrapage historique impossible). Premier correctif : bascule sur la fenêtre de
  dates de contrat, avec repli sur `est_actif` seulement si aucune date n'était renseignée.
* **05/08/2026** — ce premier correctif s'est révélé plus problématique en pratique : `date_fin_contrat`
  est renseignée automatiquement à la création (contrat `prestation` → `date_creation` + 1 mois par
  défaut, cf. `Agent.save()`) mais n'est ensuite quasiment jamais mise à jour dans l'usage réel. Des
  agents toujours en poste et `est_actif=True` (ex. Safiatou Coulibaly, terrain) se retrouvaient donc
  exclus de la génération et de l'affichage des salaires dès que cette date figée passait, alors même que
  rien dans leur statut n'avait changé. Retour à `est_actif=True` comme condition suffisante à elle
  seule ; les dates de contrat ne servent plus que pour le rattrapage d'un agent désactivé depuis.

---

## 2. Analyse Analytique & Lecture de la Paie (`SalaireLectureView`)

Cette vue en mode lecture seule (`TemplateView`) centralise la restitution financière mensuelle pour la direction et les gestionnaires RH.

* **Détermination Temporelle** : Extrait dynamiquement les paramètres `month` et `year` depuis la requête GET. Si aucun filtre n'est soumis, elle applique par défaut le mois et l'année de la date du jour via `timezone.now().date()`.
* **Calcul des Bornes du Mois** : Utilise la méthode native `calendar.monthrange(year, month)` pour identifier précisément le dernier jour du mois ciblé (`last_day`), générant les objets de comparaison `date_debut` et `date_fin`.
* **Consolidation Métier** : Le service `SalaireListeService.get_salaires()` est invoqué pour restituer un dictionnaire de données complet contenant :
* Les listes segmentées d'agents.
* Les indicateurs d'effectifs globaux et sectoriels.
* Les indicateurs de volumes de ventes ($Kg$, cartons).
* Les masses salariales cumulées par catégorie et le coût global de la paie (`total_global`).



---

## 3. Moteur d’Exportation de Performance Croisée (`export_salaires_mamies_excel`)

Une fonctionnalité avancée d'audit est intégrée à l'export Excel des agents terrain (Mamies), permettant de mesurer la performance d'un mois sur l'autre (Mois $N$ vs Mois $N-1$).

* **Reconstitution de la Période Précédente ($N-1$)** : Le script embarque une logique de décrémentation chronologique prenant en charge la transition annuelle (si le mois courant est Janvier ($1$), le mois précédent devient Décembre ($12$) de l'année $year - 1$).
* **Appel Croisé de Calculateur (`CalculatorSalaire`)** : Pour chaque ligne d'agent terrain issue du mois courant ($N$), le script effectue un calcul à la volée via `CalculatorSalaire.calcul_salaire_mamy(...)` sur la période $N-1$ pour extraire le volume de ventes historique (`kilo_n_1`).
* **Analyse de la Variation** : Le document génère une colonne **"Variation Kg"** calculée par la formule :
$$\text{Variation} = \text{Kilo}_N - \text{Kilo}_{N-1}$$


* **Formatage du Fichier** : Utilise `openpyxl` pour inscrire les données, applique un style gras sur la ligne d'en-tête et exécute un redimensionnement automatique des colonnes (`column_dimensions[...].width`) basé sur la longueur maximale de la chaîne de caractères présente dans chaque cellule augmentée d'un offset de sécurité de 5 unités.

---

## 4. Pipeline de Génération & Évitement des Conflits (`SalaireGenerationView`)

Le processus de génération des fiches de paie via `SalaireGenerationService.generate(date_debut, date_fin)` est hautement sécurisé pour empêcher l'altération de données comptables historiques.

* **Mode Aperçu (`GET`)** : Analyse l'état de la base de données pour la période mensuelle courante en vérifiant l'existence d'enregistrements dans la table `Salaire`. Il retourne deux booléens au template :
* `deja_genere` : indique si des lignes de paie existent déjà (statut brouillon ou validé).
* `deja_valide` : indique si une validation finale a déjà eu lieu.


* **Sécurité de Traitement (`POST`)** : Avant de déclencher la réévaluation ou l'écriture des salaires, une vérification stricte est opérée :
```python
salaires_valides = Salaire.objects.filter(date_debut=date_debut, date_fin=date_fin, valide=True)

```


Si au moins un salaire est marqué comme validé (`valide=True`), le système lève une alerte via le framework `django.messages` et bloque l'exécution. Cela empêche l'écrasement accidentel de salaires déjà confirmés ou décaissés.

---

## 5. Figeage Comptable des Données (`SalaireValidationView`)

La validation est l'action administrative qui clôture définitivement le cycle de paie pour une période définie.

* **Idempotence et Robustesse** : La vue filtre toutes les instances de salaires non encore verrouillées pour la période donnée (`valide=False`).
* **Opération en Bloc (Bulk Update)** : Si des salaires modifiables sont trouvés, le système exécute un `.update(valide=True)` direct en base de données. Cette approche SQL globale évite les itérations individuelles en mémoire et garantit que l'intégralité de la paie de la période passe à l'état **"figée"** au cours d'une seule et unique transaction. Une fois cette opération réalisée, aucun recalcul ou modification via le module de génération n'est toléré.