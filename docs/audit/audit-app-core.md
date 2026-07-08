# Audit — App `core` (Django, projet `dams`)

> **Statut : créé, non lu / non approuvé.** Réflexion encore ouverte — ce document est un brouillon de travail, pas une décision actée.

Date : 2026-07-06

## Périmètre analysé
- `core/views.py` (2849 lignes) — seul fichier de vues de l'app (aucun autre `views*.py`)
- `core/urls.py` (104 lignes)
- `dams/urls.py` (urls.py projet)
- Templates sous `core/templates/`
- `core/models.py`, `core/forms.py`, `core/admin.py`, `core/services/*`, `core/templatetags/*`, `core/management/commands/*`

---

## 1. Liste des vues de `core/views.py`

### Vues fonction (FBV)

| Ligne | Nom | Description |
|---|---|---|
| 74 | `custom_login` | Authentification (login) via téléphone ou nom d'utilisateur, utilise `TelephoneOrUsernameLoginForm` |
| 129 | `logout_user` | Déconnexion, redirige vers `login` |
| 135 | `access_denied` | Page 403 personnalisée, redirige selon le rôle de l'agent (rot, superviseur, gestionnaire stock, agent) |
| 186 | `supprimer_agent` | Supprime un agent (et son `User` associé) |
| 206 | `liste_fournisseurs` | Liste des fournisseurs |
| 299 | `detail_fournisseur` | Détail d'un fournisseur |
| 381 | `creer_fournisseur` | Création d'un fournisseur |
| 393 | `modifier_fournisseur` | Modification d'un fournisseur |
| 406 | `supprimer_fournisseur` | Suppression d'un fournisseur |
| 420 | `reception_lot` | Réception d'un lot en entrepôt |
| 460 | `liste_lots` | Liste des lots en entrepôt |
| 532 | `detail_lot` | Détail d'un lot |
| 573 | `mon_stock` | Stock personnel de l'agent connecté |
| 619 | `distribuer_produits_agent` | Distribution de produits à un agent |
| 652 | `modifier_distribution` | Modification d'une distribution |
| 705 | `supprimer_distribution` | Suppression (soft-delete probable) d'une distribution |
| 753 | `restaurer_distribution` | Restauration d'une distribution supprimée |
| 787 | `liste_distributions` | Liste des distributions |
| 923 | `detail_distribution` | Détail d'une distribution |
| 944 | `stats_superviseurs` | Statistiques des superviseurs |
| 1000 | `mes_distributions` | Distributions de l'agent connecté |
| 1070 | `enregistrer_vente` | Enregistrement d'une vente |
| 1110 | `liste_ventes` | Liste des ventes |
| 1154 | `detail_dette` | Détail d'une dette |
| 1183 | `detail_vente` | Détail d'une vente |
| 1217 | `enregistrer_paiement_dette` | Enregistrement d'un paiement de dette |
| 1265 | `consulter_bonus` | Consultation du bonus de l'agent |
| 1319 | `liste_dettes` | Liste des dettes |
| 1367 | `get_info_distribution` | Endpoint JSON (API) d'infos sur une distribution |
| 1392 | `creer_dette` | Création d'une dette |
| 1457 | `gestion_factures_lot` | Gestion des factures liées à un lot d'entrepôt |
| 1520 | `creer_versement` | Création d'un versement bancaire (par le ROT) |
| 1546 | `modifier_versement` | Modification d'un versement |
| 1586 | `liste_versement` | Liste des versements (avec pagination) |
| 1643 | `detail_versement` | Détail d'un versement |
| 1696 | `supprimer_versement` | Suppression d'un versement |
| 1743 | `recu_liste` | Liste des reçus |
| 1748 | `recu_create` | Création d'un reçu |
| 1773 | `liste_factures_entrepot` | Liste des factures entrepôt |
| 1794 | `liste_depenses` | Liste des dépenses |
| 1841 | `detail_depense` | Détail d'une dépense |
| 1855 | `creer_depense` | Création d'une dépense |
| 1877 | `modifier_depense` | Modification d'une dépense |
| 1906 | `creer_recouvrement` | Création d'un recouvrement pour un agent (contrôle de rôle superviseur) |
| 1997 | `historique_recouvrement` | Historique des recouvrements d'un agent |
| 2009 | `detail_historique` | Détail complet de l'historique de recouvrement |
| 2036 | `liste_agents_recouvrement` | Liste des agents pour le recouvrement |
| 2285 | `tableau_de_bord_superviseur` | Tableau de bord superviseur **(voir alerte §6 — doublon avec `agents.views`)** |
| 2542 | `vue_detail_agent` | Détail d'un agent dans le tableau de bord |
| 2641 | `detail_stagiaire` | Détail d'un stagiaire |
| 2777 | `toutes_les_dettes` | Vue admin : toutes les dettes |
| 2840 | `tous_les_bonus` | Vue admin : tous les bonus |

### Vues classe (CBV)

| Ligne | Nom | Type | Description |
|---|---|---|---|
| 1662 | `AjouterRecusView` | `UpdateView` | Ajout de reçus (upload fichiers) à un versement bancaire |
| 2180 | `ClientListView` | `LoginRequiredMixin, ListView` | Liste des clients, filtrable/recherchable, paginée |
| 2207 | `ClientDetailView` | `LoginRequiredMixin, DetailView` | Détail client + historique de ventes/statistiques |
| 2234 | `ClientCreateView` | `LoginRequiredMixin, CreateView` | Création de client |
| 2251 | `ClientUpdateView` | `LoginRequiredMixin, UpdateView` | Modification de client |
| 2270 | `ClientDeleteView` | `LoginRequiredMixin, DeleteView` | Suppression de client |

Total : **51 FBV + 6 CBV = 57 vues**.

---

## 2. URLs déclarées dans `core/urls.py` — validité des références

Toutes les URLs de `core/urls.py` référencent des vues **qui existent bien** dans `core/views.py` (aucun lien mort / import cassé détecté). Détail des correspondances (ligne url → vue) :

- L10 `access_denied` → l135 OK
- L15-19 fournisseurs (`liste_fournisseurs`, `detail_fournisseur`, `creer_fournisseur`, `modifier_fournisseur`, `supprimer_fournisseur`) → OK
- L24-27 entrepôt (`reception_lot`, `liste_lots`, `detail_lot`, `mon_stock`) → OK
- L29-37 distribution (`distribuer_produits_agent`, `modifier_distribution`, `supprimer_distribution`, `restaurer_distribution`, `liste_distributions`, `detail_distribution`, `stats_superviseurs`, `mes_distributions`) → OK
- L40-51 ventes/dettes/bonus (`enregistrer_vente`, `liste_ventes`, `detail_vente`, `creer_dette`, `liste_dettes`, `detail_dette`, `enregistrer_paiement_dette`, `consulter_bonus`) → OK
- L55-56 et L101-102 : **doublon exact** — `toutes_les_dettes` et `tous_les_bonus` sont chacune enregistrées **deux fois** sous le même nom d'URL mais avec un chemin différent (`admin/dettes/` vs `direction/analyses/dettes`, `admin/bonus/` vs `direction/analyses/bonus`). Le second `path()` écrase le premier au niveau du `reverse()` (Django résout par le dernier match), donc le chemin `admin/dettes/` et `admin/bonus/` restent accessibles en navigation directe mais ne seront **jamais générés** par `{% url 'toutes_les_dettes' %}` / `{% url 'tous_les_bonus' %}`, qui pointeront toujours vers `direction/analyses/...`. À signaler comme anomalie de configuration.
- L59 `get_info_distribution` → OK
- L61-65 `gestion_factures_lot` (importée explicitement en L4-7 via `from .views import (gestion_factures_lot)`, en plus de l'import module `from . import views` en L3) → OK, import redondant mais fonctionnel
- L66-75 versements/reçus/factures (`liste_versement`, `detail_versement`, `AjouterRecusView.as_view()`, `creer_versement`, `modifier_versement`, `supprimer_versement`, `recu_liste`, `recu_create`, `liste_factures_entrepot`) → OK
- L77-80 dépenses (`liste_depenses`, `creer_depense`, `modifier_depense`, `detail_depense`) → OK
- L84-88 clients (CBV) → OK
- L90-91 tableau de bord (`vue_detail_agent`, `detail_stagiaire`) → OK
- L93-96 recouvrement (`liste_agents_recouvrement`, `creer_recouvrement`, `historique_recouvrement`, `detail_historique`) → OK

**Aucune URL de `core/urls.py` ne référence de vue inexistante.**

---

## 3. Inclusion de `core.urls` dans le projet

Vérifié dans `dams/urls.py` (ligne 33) :
```python
path('', include('core.urls')),
```
`core.urls` **est bien inclus**, à la racine du site (préfixe vide), sans namespace (pas de `app_name` défini dans `core/urls.py`, et `include()` ne spécifie pas de `namespace=`).

**Conséquence importante** : puisque `core` n'a pas de namespace, tous ses noms d'URL vivent dans l'espace de noms global, ce qui explique le conflit du §6 avec `agents.tableau_de_bord_superviseur`, et le doublon interne du §2.

---

## 4. Templates — vérification d'existence et des tags `{% url %}`

### 4.a Templates rendus par les vues de `core/views.py` — manquants

Sur les 42 templates référencés via `render()` dans `core/views.py`, **5 sont introuvables** sur le disque :

| Template attendu | Vue concernée (ligne) | Constat |
|---|---|---|
| `core/agents/supprimer_agent.html` | `supprimer_agent` (views.py:195) | Fichier absent, dossier `core/templates/core/agents/` inexistant |
| `core/distribution/stats_superviseurs.html` | `stats_superviseurs` (views.py:996) | Absent de `core/templates/core/distribution/` |
| `core/dashboard/superviseur.html` | `tableau_de_bord_superviseur` (views.py:2538) | Absent de `core/templates/core/dashboard/` (ne contient que `detail_agent.html`, `detail_stagiaire.html`) |
| `core/analyses/liste_dettes_admin.html` | `toutes_les_dettes` (views.py:2836) | Le dossier `core/templates/core/analyses/` n'existe pas du tout |
| `core/analyses/tous_les_bonus_admin.html` | `tous_les_bonus` (views.py:2849) | Idem, dossier absent |

→ Toute requête vers ces 5 vues provoquera un `TemplateDoesNotExist` en production. À noter : des templates de nom proche existent dans **d'autres apps** (`agents/templates/agents/dashboards/superviseur.html`, `agents/templates/agents/analyses/...`, `direction/templates/direction/analyses/...`) — probable confusion/duplication entre apps.

### 4.b Tags `{% url %}` cassés dans les templates de `core`

En comparant tous les `{% url '...' %}` des templates de `core/templates` avec l'ensemble des noms d'URL réellement déclarés dans tout le projet (`core`, `agents`, `direction`, `paie`, `mobile`, `analyse_champ`, `surveillance`, `marchandise`, `dams`), **3 noms n'existent nulle part** :

| Nom cassé | Fichier / ligne | Remarque |
|---|---|---|
| `'dashboard'` | `core/templates/registration/password_change_done.html:29` | Aucune URL nommée `dashboard` n'existe dans le projet |
| `'liste_factures'` | `core/templates/core/factures/confirm_delete.html:8` | N'existe pas ; seul `liste_factures_entrepot` existe. `confirm_delete.html` n'est d'ailleurs référencé par aucun `render()` dans `core/views.py` — template probablement orphelin |
| `'tableau_de_bord'` | `core/templates/registration/password_change.html:68` | N'existe pas ; seul `tableau_de_bord_superviseur` existe |

Ces 3 pages planteront (`NoReverseMatch`) dès qu'un utilisateur cliquera sur le lien concerné.

### 4.c Tags `{% url 'core:xxx' %}`

Recherche effectuée sur tout le repo : **aucune occurrence** de `{% url 'core:...' %}`. Cohérent avec l'absence de namespace pour `core` (§3) — donc pas de lien mort de ce type, mais confirme que personne dans le code ne traite `core` comme une app avec espace de noms (bonne pratique Django non respectée si l'intention était de la namespacer).

---

## 5. Fonctions/vues marquées comme dépréciées

Recherche de motifs (`deprecated`, `déprécié`, `obsolète`, `TODO: remove`, `à supprimer`, `legacy`, `ne plus utiliser`, `old`, `backup`, suffixes `_old/_backup/_v1/_deprecated`) dans `core/views.py`, `core/models.py`, `core/forms.py`, `core/admin.py`, `core/services/*.py`, `core/templatetags/*.py`, `core/management/commands/*.py` :

- **Aucune vue** de `core/views.py` n'est explicitement marquée dépréciée (pas de commentaire ni suffixe de ce type).
- Deux mentions trouvées dans `core/models.py` (hors vues, mais pertinent pour l'audit) :
  - `core/models.py:2216` — champ avec `verbose_name="Superviseur (déprécié – ancienne logique)"`
  - `core/models.py:2303` — commentaire `- sinon superviseur (legacy)`

Ces deux éléments indiquent une logique de modèle marquée comme legacy/dépréciée, à surveiller si elle est encore utilisée par des vues de `core`.

---

## 6. Vues jamais référencées dans `core/urls.py` (potentiellement mortes)

En comparant les 57 vues de `core/views.py` avec les références `views.xxx` / `xxx.as_view()` de `core/urls.py`, **4 vues ne sont référencées par aucune URL de `core`** :

| Vue | Ligne | Où est-elle utilisée réellement ? |
|---|---|---|
| `custom_login` | views.py:74 | Importée et utilisée directement dans `dams/urls.py:21,27` (`path('', custom_login, name='login')`) — donc utilisée, mais pas via `core/urls.py` |
| `logout_user` | views.py:129 | Idem, importée/utilisée dans `dams/urls.py:21,28` (`name='logout'`) — utilisée hors de `core/urls.py` |
| `supprimer_agent` | views.py:186 | **Non référencée dans aucun `urls.py` du projet.** Grep global : seule occurrence hors définition est le `render()` interne (views.py:195) vers un template lui-même manquant (§4.a). **Vue morte / inaccessible**, et son template n'existe pas non plus — code mort à supprimer ou à câbler. |
| `tableau_de_bord_superviseur` | views.py:2285 | **Non référencée dans `core/urls.py`.** Une vue **différente** portant le même nom existe dans `agents/views.py:109` et **c'est celle-ci** qui est réellement câblée dans `agents/urls.py:7` (`name='tableau_de_bord_superviseur'`) et utilisée par tous les `{% url 'tableau_de_bord_superviseur' %}` du repo (`core/templates/base.html:478-479`, `core/templates/core/dashboard/detail_agent.html:13`, `detail_stagiaire.html:28`, `registration/password_change.html:65`, `password_change_done.html:24`, `agents/templates/...`). **La version de `core/views.py` (ligne 2285-2538) est donc totalement orpheline** : jamais appelée par le routeur, code mort qui en plus référence un template inexistant (`core/dashboard/superviseur.html`, §4.a). Recommandation : supprimer cette fonction de `core/views.py` ou clarifier laquelle des deux implémentations doit faire foi (risque de confusion pour la maintenance). |

Toutes les autres vues (53) sont bien référencées dans `core/urls.py`.

---

## Synthèse des anomalies à corriger (priorité suggérée)

1. **Bloquant** — 5 templates manquants provoquant un crash certain à l'exécution (§4.a), notamment sur `tableau_de_bord_superviseur` et `toutes_les_dettes`/`tous_les_bonus`.
2. **Bloquant** — 3 `{% url %}` cassés (`dashboard`, `liste_factures`, `tableau_de_bord`) dans des templates communs (`registration/password_change*.html`) utilisés par tous les utilisateurs après changement de mot de passe (§4.b).
3. **Code mort / confusion** — `core.views.tableau_de_bord_superviseur` (views.py:2285) est un doublon non routé de `agents.views.tableau_de_bord_superviseur` ; à supprimer ou fusionner (§6).
4. **Code mort** — `core.views.supprimer_agent` (views.py:186) n'est jamais routée ; son template associé est aussi manquant (§4.a + §6).
5. **Anomalie de routage** — doublon `toutes_les_dettes` / `tous_les_bonus` déclarés deux fois avec des chemins différents dans `core/urls.py` (lignes 55-56 et 101-102) : le premier chemin (`admin/...`) devient injoignable via `{% url %}` (§2).
6. **Nettoyage mineur** — template orphelin `core/templates/core/factures/confirm_delete.html`, jamais rendu par aucune vue, et contenant lui-même un lien cassé (§4.b).
7. **Dette technique signalée dans les modèles** (hors vues) — `core/models.py:2216` et `2303` mentionnent une logique « superviseur (déprécié/legacy) », à vérifier si encore utilisée par les vues de distribution/recouvrement.
