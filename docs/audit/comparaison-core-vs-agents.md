# Comparaison `core` vs `agents` — duplication de logique métier

> **Statut : créé, non lu / non approuvé.** Réflexion encore ouverte — ce document est un brouillon de travail, pas une décision actée.

Date : 2026-07-07
Voir aussi : [audit-app-core.md](audit-app-core.md), [audit-app-agents.md](audit-app-agents.md)

## Constat général

L'app `agents` a été créée pour porter une logique orientée « rôle » (superviseur / ROT / agent terrain / gestionnaire stock) qui, historiquement, vivait dans `core`. La migration est **partielle** : `core` garde ses anciennes vues (souvent orphelines ou en doublon), et `agents` réimplémente une version parallèle avec ses propres forms, sans réutiliser ni supprimer l'existant. Résultat : deux implémentations concurrentes du même domaine métier, sans namespace pour les distinguer côté URLs.

---

## 1. Doublon confirmé et actif : `tableau_de_bord_superviseur`

| | `core` | `agents` |
|---|---|---|
| Emplacement | `core/views.py:2285` | `agents/views.py:109` |
| Câblée dans `urls.py` ? | **Non** — absente de `core/urls.py` | **Oui** — `agents/urls.py:7` |
| Template | `core/dashboard/superviseur.html` (**manquant sur disque**) | `agents/dashboards/superviseur.html` (existe) |
| Verdict | **Code mort à supprimer** dans `core` | Version active, à conserver |

C'est le cas le plus net : `core` a gardé une ancienne implémentation jamais nettoyée après la migration vers `agents`. Recommandation : supprimer `core.views.tableau_de_bord_superviseur` (views.py:2285-2538, ~250 lignes) et le template introuvable associé.

---

## 2. Paires fonctionnellement équivalentes (logique dupliquée, les deux actives)

| Domaine | Vue `core` (active) | Vue `agents` (active) | Risque |
|---|---|---|---|
| Distribution lot→agent | `distribuer_produits_agent` (core:619) | `distribuer_lot_agent` (agents:284, **marquée `# deprecier`**) et `distribution_superviseur` (agents:363, remplaçant) | 3 implémentations vivantes du même geste métier |
| Liste des distributions | `liste_distributions` (core:787) | `liste_distribution_sup` (agents:656) | Filtrage/pagination dupliqués, périmètre différent (global vs superviseur) |
| Détail d'une distribution | `detail_distribution` (core:923) | `detail_distribution_sup` (agents:800) | Idem — la version `agents` intègre en plus vente/recouvrement immédiat |
| Enregistrement de vente | `enregistrer_vente` (core:1070) | `vente_distribution_rapide` (agents:851) | Deux chemins créent un objet `Vente` avec des règles potentiellement divergentes |
| Recouvrement | `creer_recouvrement` (core:1906) | `recouvrer_superviseur` (agents:1245) | Périmètre différent (agent vs superviseur) mais logique très proche |
| Détail agent / KPI | `vue_detail_agent` (core:2542) | `detail_agent_sup` (agents:467), `detail_agent_rot` (agents:1212) | 3 vues affichant des KPI d'agent avec des calculs probablement recalculés séparément |
| Liste d'agents | `liste_agents_recouvrement` (core:2036) | `liste_agents_sup` (agents:429), `liste_agents_rot` (agents:1179) | Logique de filtrage par rôle dupliquée à 3 endroits |
| CRUD agent | `supprimer_agent` (core:186, **jamais routée, code mort**) | `creer_agent` (agents:589), `modifier_agent` (agents:626) | CRUD éclaté : la suppression est restée orpheline dans `core`, création/modification vivent dans `agents` |
| Gestion de lots/stock | `reception_lot`, `liste_lots`, `detail_lot`, `mon_stock` (core:420,460,532,573) | `dashboard_gestionnaire_stock`, `mise_disposition_rot`, `lots_par_produit`, `historique_mise_disposition`, `affecter_lot_superviseur`, `superviseur_lots_affectes` (agents) | Domaine stock scindé : réception globale reste dans `core`, affectation/distribution vit dans `agents` — cohérent fonctionnellement mais aucun des deux ne référence l'autre explicitement |

---

## 3. Forms dupliqués

| Classe | `core/forms.py` | `agents/forms.py` | Statut |
|---|---|---|---|
| `MultiFileInput` | ligne 27 | ligne 37 | Code strictement identique — dupliqué, à factoriser dans un module partagé |
| `MultiFileField` | ligne 30 | ligne 40 | Idem |
| `TelephoneOrUsernameLoginForm` | ligne 43 (**utilisée** — importée par `agents/views.py:81` et `core/views.py`) | ligne 53 (**jamais importée nulle part**) | La copie dans `agents/forms.py` est du code mort à supprimer |
| `BaseVenteForm` | ligne 696 (`forms.ModelForm`) | ligne 893 (`forms.Form`) | **Même nom, base différente** — piège si un import se trompe de module |
| Forms de vente par type d'agent | `VenteGrosAgentForm`, `VenteDetailAgentForm`, `VenteSuperviseurForm` (790,829,868) | `VenteTerrainForm`, `VenteAgentGrosForm`, `VenteFlexForm` (916,921,934) | Même famille fonctionnelle, deux hiérarchies de classes parallèles héritant chacune d'un `BaseVenteForm` différent |
| Forms de distribution | `DistributionForm` (core:444) | `DistributionSuperviseurSimplifieeForm`, `DistributionSuperviseurOverrideForm`, `SupervisorDistributionForm` (agents) | Même domaine, formulaires non partagés |
| Forms de recouvrement | `RecouvrementForm` (core:1111) | `RecouvrementSuperviseurForm` (agents:538) | Même domaine, logique dupliquée/spécialisée |

---

## 4. Ce qui a été proprement migré (pas de doublon)

- `agents/models.py` et `agents/admin.py` sont des stubs vides : `agents` **ne duplique pas les modèles**, elle réutilise `core.models` (`Agent`, `Vente`, `DistributionAgent`, etc.) — bon signe, la couche données est restée unique.
- Les vues purement stock/ROT (`mise_disposition_rot`, `affecter_lot_superviseur`, `rot_affectations_liste`, etc.) n'ont pas d'équivalent dans `core` — logique réellement nouvelle, pas un doublon.

---

## 5. Recommandations priorisées

1. **Trancher `tableau_de_bord_superviseur`** : supprimer la version orpheline de `core/views.py:2285` (et son template manquant). C'est la seule collision de *nom d'URL* actuelle grâce à l'absence de namespace — un nettoyage sans risque fonctionnel.
2. **Décider du sort de `distribuer_lot_agent`** (agents:284, dépréciée depuis un moment d'après `agents/APP_AGENT.md:67`) et de `distribuer_produits_agent` (core:619) : clarifier lequel des trois chemins de distribution (`distribuer_lot_agent`, `distribution_superviseur`, `distribuer_produits_agent`) est la cible finale, retirer les autres.
3. **Auditer les règles métier de vente** entre `enregistrer_vente` (core) et `vente_distribution_rapide` (agents) — s'assurer qu'elles appliquent les mêmes règles de calcul/validation, sinon risque de résultats incohérents selon le point d'entrée utilisé.
4. **Factoriser les utilitaires dupliqués** (`MultiFileInput`, `MultiFileField`, `TelephoneOrUsernameLoginForm`) dans un module commun (ex. `core/forms.py` déjà utilisé, ou un nouveau `common/forms.py`), et supprimer les copies mortes dans `agents/forms.py`.
5. **Introduire des namespaces** (`app_name` + `namespace=` dans `include()`) pour `core` et `agents`, afin que toute future collision de nom d'URL soit détectée à l'exécution plutôt que résolue silencieusement par l'ordre des `include()`.
6. **Clarifier le CRUD agent** : `supprimer_agent` (core, jamais routée) devrait soit être migrée vers `agents` aux côtés de `creer_agent`/`modifier_agent`, soit supprimée si la suppression d'agent n'est plus un besoin.
