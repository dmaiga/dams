# Audit — App `agents` (Django, projet `dams`)

> **Statut : créé, non lu / non approuvé.** Réflexion encore ouverte — ce document est un brouillon de travail, pas une décision actée.

Date : 2026-07-07

## Périmètre analysé
- `agents/views.py` (1301 lignes) — seul fichier de vues de l'app
- `agents/urls.py` (49 lignes)
- `dams/urls.py`, `dams/settings.py`
- Templates sous `agents/templates/`
- `agents/models.py`, `agents/forms.py`, `agents/admin.py`, `agents/services/*`

---

## 1. Liste des vues de `agents/views.py`

Aucun autre fichier `views*.py` dans l'app. Toutes les vues sont **function-based** (aucune CBV, contrairement à `core/views.py` qui en contient 5).

| # | Fonction | Ligne | Décorateur | Description |
|---|----------|-------|------------|--------------|
| 1 | `safe_parse_date(value)` | 103 | — | Helper interne (pas une vue), parse une date GET en toute sécurité |
| 2 | `tableau_de_bord_superviseur` | 109 | `@login_required` | Dashboard superviseur — délègue à `SuperviseurDashboardService.build_dashboard_perimetre`, render `agents/dashboards/superviseur.html` |
| 3 | `tableau_de_bord_rot` | 127 | `@login_required` | Dashboard du ROT — délègue à `RotDashboardService.build_dashboard`, render `agents/dashboards/rot.html` |
| 4 | `dashboard_agent` | 145 | `@login_required` | Dashboard agent terrain — délègue à `AgentDashboardService`, render `agents/dashboards/agent.html` |
| 5 | `superviseur_lots_affectes` | 163 | `@login_required` | Liste paginée des lots affectés au superviseur avec filtres temporels (today/7j/30j/plage) et calcul de taux d'utilisation |
| 6 | `distribuer_lot_agent` | 284 | `@login_required` | **Marquée `# deprecier` (ligne 282)** — distribution "standard" superviseur→agent via `SupervisorDistributionForm` |
| 7 | `distribution_superviseur_override` | 310 | `@login_required` | Distribution dérogatoire réservée au user `"jeanclaude.sup"`, permet un override du prix de gros |
| 8 | `distribution_superviseur` | 363 | `@login_required` | Distribution "simplifiée" avec triple contrôle de sécurité en transaction atomique |
| 9 | `liste_agents_sup` | 429 | `@login_required` | Liste des agents terrain/agent_gros sous la responsabilité du superviseur connecté |
| 10 | `detail_agent_sup` | 467 | `@login_required` | Fiche détail d'un agent (ventes, recouvrement, KPI) côté superviseur |
| 11 | `creer_agent` | 589 | `@login_required` | Création d'un agent (formulaire différent selon superviseur ou ROT connecté) |
| 12 | `modifier_agent` | 626 | `@login_required` | Modification d'un agent existant, avec contrôle de périmètre |
| 13 | `liste_distribution_sup` | 656 | `@login_required` | Liste paginée des distributions du superviseur avec filtres (agent/produit/lot/date) |
| 14 | `get_form_class(agent_concerne)` | 790 | — | Helper interne (pas une vue), choisit la classe de form de vente selon le type d'agent |
| 15 | `detail_distribution_sup` | 800 | `@login_required` | Détail d'une distribution + formulaire de vente/recouvrement immédiat (transaction atomique) |
| 16 | `vente_distribution_rapide` | 851 | `@login_required` | Liquidation instantanée en un clic (vente totale + recouvrement automatique) |
| 17 | `dashboard_gestionnaire_stock` | 927 | `@login_required` | Dashboard du gestionnaire de stock (stock global, dernières affectations) |
| 18 | `mise_disposition_rot` | 955 | `@login_required` | Mise à disposition d'un lot au ROT, historisée dans `MiseDispositionRot` |
| 19 | `lots_par_produit` | 991 | *(pas de login_required)* | Endpoint AJAX (`JsonResponse`) retournant les lots disponibles pour un produit |
| 20 | `historique_mise_disposition` | 1016 | `@login_required` | Historique des mises à disposition |
| 21 | `affecter_lot_superviseur` | 1033 | `@login_required` | Le ROT affecte un lot à un superviseur |
| 22 | `rot_affectations_liste` | 1072 | `@login_required` | Liste paginée des affectations faites par le ROT, avec filtres et stats |
| 23 | `liste_agents_rot` | 1179 | `@login_required` | Liste des superviseurs et de leurs agents gérés, vue ROT |
| 24 | `detail_agent_rot` | 1212 | `@login_required` | Détail d'un agent/superviseur côté ROT, via `AgentDataService.get_agent_complete_data` |
| 25 | `recouvrer_superviseur` | 1245 | `@login_required` | Recouvrement du cash d'un superviseur par le ROT |

**Alerte sécurité** : `lots_par_produit` (ligne 991) n'a **pas** de `@login_required`, contrairement à toutes ses voisines — incohérence à corriger.

---

## 2. URLs déclarées dans `agents/urls.py` (49 lignes) — validité

| Ligne | Path | name= | Vue référencée | Statut |
|---|---|---|---|---|
| 7 | `tableau-de-bord/superviseur/` | `tableau_de_bord_superviseur` | `views.tableau_de_bord_superviseur` | OK (l.109) |
| 8 | `dashboard/` | `dashboard_rot` | `views.tableau_de_bord_rot` | OK (l.127) — nom d'URL ≠ nom de fonction |
| 9 | `agent/dashboard/` | `dashboard_agent` | `views.dashboard_agent` | OK (l.145) |
| 11 | `sup/agent/liste/` | `liste_agents_sup` | `views.liste_agents_sup` | OK (l.429) |
| 12 | `sup/agent/<int:agent_id>/` | `detail_agent_sup` | `views.detail_agent_sup` | OK (l.467) |
| 13 | `sup/agents/creer/` | `creer_agent` | `views.creer_agent` | OK (l.589) |
| 14 | `sup/agents/modifier/<int:agent_id>/` | `modifier_agent` | `views.modifier_agent` | OK (l.626) |
| 16 | `stock/dashboard/` | `dashboard_gestionnaire_stock` | `views.dashboard_gestionnaire_stock` | OK (l.927) |
| 17 | `stock/mise-disposition/` | `mise_disposition_rot` | `views.mise_disposition_rot` | OK (l.955) |
| 18 | `stock/mise-disposition/historique/` | `historique_mise_disposition` | `views.historique_mise_disposition` | OK (l.1016) |
| 19 | `ajax/lots-par-produit/` | `lots_par_produit` | `views.lots_par_produit` | OK (l.991) |
| 20 | `affectation/lot` | `superviseur_lots_affectes` | `views.superviseur_lots_affectes` | OK (l.163) |
| 22 | `affectation/agent` | `distribuer_lot_agent` | `views.distribuer_lot_agent` | OK (l.284) — **vue dépréciée toujours câblée** |
| 23 | `affectation/agent/override` | `distribution_superviseur_override` | `views.distribution_superviseur_override` | OK (l.310) |
| 25 | `distribution/agent` | `distribution_superviseur` | `views.distribution_superviseur` | OK (l.363) |
| 27 | `sup/distribution/liste` | `liste_distribution_sup` | `views.liste_distribution_sup` | OK (l.656) |
| 28-32 | `sup/distribution/vente/<int:detail_id>/` | `vente_distribution_rapide` | `views.vente_distribution_rapide` | OK (l.851) |
| 33-37 | `superviseur/distribution/detail/<int:detail_id>/` | `detail_distribution_sup` | `views.detail_distribution_sup` | OK (l.800) |
| 39 | `affectation/liste_rot` | `rot_affectations_liste` | `views.rot_affectations_liste` | OK (l.1072) |
| 40 | `affectation/creer_rot` | `affecter_lot_superviseur` | `views.affecter_lot_superviseur` | OK (l.1033) |
| 41 | `rot/agents/` | `liste_agents_rot` | `views.liste_agents_rot` | OK (l.1179) |
| 42 | `rot/agents/<int:agent_id>/` | `detail_agent_rot` | `views.detail_agent_rot` | OK (l.1212) |
| 44-48 | `rot/recouvrement/superviseur/` | `recouvrer_superviseur` | `views.recouvrer_superviseur` | OK (l.1245) |

**Aucun lien mort** : les 23 URLs référencent chacune une vue existante et valide.

Anomalie mineure : ligne 8, le `name=` de l'URL (`dashboard_rot`) diffère du nom de la vue Python (`tableau_de_bord_rot`) — source de confusion potentielle mais pas un bug fonctionnel.

---

## 3. Inclusion dans le projet + namespace

- `dams/urls.py:35` : `path('agents/', include('agents.urls')),` → les URLs de `agents` **sont bien incluses**, sous le préfixe `/agents/`.
- Comparaison : `marchandise.urls` est inclus avec un `namespace="marchandise"` explicite, mais **`agents.urls` est inclus sans namespace**, comme `core.urls`, `direction.urls`, `paie.urls`.
- **Aucun `app_name`** défini ni dans `agents/urls.py` ni dans `core/urls.py` (confirmé). Toutes les URL names de `agents` vivent donc dans le même espace de noms global que `core` — un conflit de nom entre les deux casserait le résolveur d'URL, point de vigilance vu le chevauchement fonctionnel constaté au §7.

---

## 4. Templates

### Templates de l'app (`agents/templates/agents/`, 23 fichiers)
Tous les `render()` de `agents/views.py` pointent vers des templates qui **existent bien** — aucun template manquant.

### Templates orphelins (existent mais jamais rendus)
- `agents/templates/agents/affectations/affectations_liste.html` — non utilisé (à ne pas confondre avec `agents/templates/agents/rot/affectations_liste.html`, bien rendu par `rot_affectations_liste`)
- `agents/templates/agents/affectations/affecter_lot_agent.html` — non utilisé (à ne pas confondre avec `agents/rot/affecter_lot.html`)
- `agents/templates/agents/analyses/analyse_operationnelle.html` — non utilisé par aucune vue de `agents/views.py` (existe une variante distincte dans `direction/templates/direction/analyses/agents/analyse_operationnelle.html`, utilisée par `direction/views.py:333`)

### Tags `{% url %}` dans les templates de `agents`
Tous résolvent correctement, mais certains pointent vers des URLs **d'autres apps**, ce qui ne fonctionne que parce qu'il n'y a pas de namespace :
- `enregistrer_vente`, `mon_stock`, `liste_dettes`, `liste_clients` (dans `agents/dashboards/agent.html:78,84,90,96`) → définis dans `core/urls.py`
- `creer_recouvrement`, `historique_recouvrement` (dans `agents/superviseur/detail_agent.html:26,176,181`) → définis dans `core/urls.py`

**Aucun tag `{% url %}` mort détecté.**

---

## 5. Fonctions/vues dépréciées ou marquées legacy

- `agents/views.py:282` — commentaire `# deprecier` juste au-dessus de `distribuer_lot_agent` (ligne 284).
- `agents/APP_AGENT.md:67` — documentation confirmant : *"Distribution Standard (`distribuer_lot_agent`) - En cours de dépréciation"*.
- Aucune autre occurrence de motifs "deprecated/obsolète/legacy/backup/_old/_v1" dans `agents/views.py`, `models.py`, `forms.py`, `admin.py`, `services/*`.
- `distribuer_lot_agent` reste câblée (`agents/urls.py:22`) et rendue (`agents/superviseur/distribuer_lot.html`) malgré la dépréciation annoncée. Elle coexiste avec `distribution_superviseur` (remplaçant recommandé selon la doc) et `distribution_superviseur_override` (canal dérogatoire).

---

## 6. Vues jamais référencées

Chacune des 23 vues de `agents/views.py` (hors helpers `safe_parse_date` et `get_form_class`) apparaît **exactement une fois** dans `agents/urls.py`. **Aucune vue orpheline** dans l'app `agents` elle-même, et aucune n'est réutilisée depuis une autre app.

À noter : `distribuer_lot_agent` (l.284), bien que câblée, est fonctionnellement obsolète (§5) — une "vue morte en sursis" plutôt qu'une vue jamais référencée.

---

## 7. Chevauchement avec `core` — doublons/logique dupliquée

Confirmation du doublon déjà connu :
- `agents.views.tableau_de_bord_superviseur` (agents/views.py:109, câblée agents/urls.py:7) **↔** `core.views.tableau_de_bord_superviseur` (core/views.py:2285, orpheline côté `core`) — nom **identique**.

Autres paires identifiées :

| Vue `agents` | Vue `core` | Nature du chevauchement |
|---|---|---|
| `tableau_de_bord_superviseur` (agents:109) | `tableau_de_bord_superviseur` (core:2285) | **Nom identique**, doublon confirmé |
| `distribuer_lot_agent` (agents:284) | `distribuer_produits_agent` (core:619) | Nom très proche, même logique : distribuer un lot/produit à un agent |
| `liste_distribution_sup` (agents:656) | `liste_distributions` (core:787) | Même fonction : lister les distributions (périmètre superviseur vs global) |
| `detail_distribution_sup` (agents:800) | `detail_distribution` (core:923) | Même fonction : détail d'une distribution |
| `vente_distribution_rapide` (agents:851) | `enregistrer_vente` (core:1070) | Les deux créent un objet `Vente` — logique de vente dupliquée |
| `recouvrer_superviseur` (agents:1245) | `creer_recouvrement` (core:1906) | Même domaine (recouvrement), périmètre différent (superviseur vs agent) |
| `detail_agent_sup` / `detail_agent_rot` (agents:467, 1212) | `vue_detail_agent` (core:2542) | Même fonction : fiche détail agent avec KPI |
| `liste_agents_sup` / `liste_agents_rot` (agents:429, 1179) | `liste_agents_recouvrement` (core:2036) | Chevauchement partiel : listes d'agents à des fins différentes mais logique de filtrage similaire |
| `creer_agent` / `modifier_agent` (agents:589, 626) | `supprimer_agent` (core:186) | `core` ne gère que la suppression — logique CRUD "agent" éclatée entre les deux apps |
| `dashboard_gestionnaire_stock`, `mise_disposition_rot`, `lots_par_produit`, `historique_mise_disposition`, `affecter_lot_superviseur`, `superviseur_lots_affectes` (agents, domaine stock/lots) | `liste_lots` (core:460), `detail_lot` (core:532), `mon_stock` (core:573), `reception_lot` (core:420) | Même domaine (gestion de lots/stock), noms différents — logique éclatée entre `core` (réception/lots globaux) et `agents` (affectation/distribution) |

---

## 8. Comparaison des Forms (`agents/forms.py` vs `core/forms.py`)

### Classes définies dans `agents/forms.py` (1258 lignes)
`MultiFileInput` (37), `MultiFileField` (40), `TelephoneOrUsernameLoginForm` (53), `DirectionAgentCreationForm` (70), `RotSupervisorCreationForm` (179), `SupervisorTerrainAgentCreationForm` (221), `SupervisorTerrainAgentUpdateForm` (325), `RotAffectationLotSuperviseurForm` (373), `RecouvrementSuperviseurForm` (538), `DistributionSuperviseurSimplifieeForm` (582), `DistributionSuperviseurOverrideForm` (670), `MiseDispositionRotForm` (736), `BaseVenteForm` (893, `forms.Form`), `VenteTerrainForm` (916), `VenteAgentGrosForm` (921), `VenteFlexForm` (934), `SupervisorDistributionForm` (957), `SupervisorOverrideForm` (1110)

### Classes définies dans `core/forms.py` (1510 lignes)
`MultiFileInput` (27), `MultiFileField` (30), `TelephoneOrUsernameLoginForm` (43), `FournisseurForm` (61), `ReceptionLotForm` (66), `FactureLotForm` (278), `PerteForm` (433), `DistributionForm` (444), `BaseVenteForm` (696, `forms.ModelForm`), `VenteGrosAgentForm` (790), `VenteDetailAgentForm` (829), `VenteSuperviseurForm` (868), `DetteForm` (917), `PaiementDetteForm` (981), `BonusAgentForm` (1044), `RapportDettesForm` (1058), `RecouvrementForm` (1111), `VersementForm` (1231), `RecuVersementForm` (1307), `DepenseForm` (1357), `PaiementFournisseurForm` (1408)

### Doublons détectés

| Classe | agents/forms.py | core/forms.py | Remarque |
|---|---|---|---|
| `MultiFileInput` | ligne 37 | ligne 27 | **Code identique** (widget utilitaire dupliqué) |
| `MultiFileField` | ligne 40 | ligne 30 | **Code identique** (dupliqué) |
| `TelephoneOrUsernameLoginForm` | ligne 53 | ligne 43 | **Code strictement identique**. `agents/views.py:81` importe **`core.forms.TelephoneOrUsernameLoginForm`**, pas celle d'`agents/forms.py` — la classe d'`agents/forms.py:53` semble **totalement inutilisée / morte** (aucun import depuis `agents.forms` trouvé dans le repo) |
| `BaseVenteForm` | ligne 893 (`forms.Form`) | ligne 696 (`forms.ModelForm`) | **Même nom, bases différentes** — piège potentiel en cas de mauvais import |
| `VenteTerrainForm`/`VenteAgentGrosForm`/`VenteFlexForm` (agents:916,921,934) | — | `VenteGrosAgentForm`/`VenteDetailAgentForm`/`VenteSuperviseurForm` (core:790,829,868) | Noms différents, même famille fonctionnelle (formulaires de vente par type d'agent) — duplication probable |
| `DistributionSuperviseurSimplifieeForm`, `DistributionSuperviseurOverrideForm`, `SupervisorDistributionForm` (agents) | — | `DistributionForm` (core:444) | Même domaine (distribution de lots), formulaires distincts non partagés |
| `RecouvrementSuperviseurForm` (agents:538) | — | `RecouvrementForm` (core:1111) | Même domaine (recouvrement) — logique probablement dupliquée/spécialisée |

---

## Points complémentaires

- `agents/models.py` et `agents/admin.py` sont des **stubs vides (3 lignes)** — l'app `agents` ne définit aucun modèle propre, elle réutilise entièrement les modèles de `core.models` (`Agent`, `Vente`, `DistributionAgent`, etc.).
- `agents` est bien dans `INSTALLED_APPS` (`dams/settings.py:81`), juste après `core` (ligne 80).
- Import dupliqué dans `agents/views.py:36-37` : `AnalyseOperationnelleService` importé deux fois de suite (redondance mineure, sans impact fonctionnel).

---

## Synthèse des anomalies à corriger (priorité suggérée)

1. **Sécurité** — `lots_par_produit` (agents/views.py:991) n'a pas de `@login_required`, contrairement à toutes les autres vues de l'app.
2. **Dette technique confirmée** — `distribuer_lot_agent` (agents/views.py:284) est explicitement marquée `# deprecier` depuis un moment (documenté dans `agents/APP_AGENT.md:67`) mais reste câblée et utilisée ; à planifier pour suppression au profit de `distribution_superviseur`.
3. **Code mort** — `TelephoneOrUsernameLoginForm` dans `agents/forms.py:53` est un doublon strictement identique à celui de `core/forms.py:43`, jamais importé nulle part : à supprimer.
4. **Duplication de logique** — de nombreuses paires vues/forms entre `core` et `agents` couvrent le même domaine métier (distribution, vente, recouvrement, gestion agent) avec des implémentations distinctes (§7, §8) : risque de divergence de comportement et de double maintenance.
5. **Absence de namespace** — ni `core` ni `agents` n'ont de `namespace`/`app_name`, ce qui permet déjà un chevauchement de noms d'URL (`tableau_de_bord_superviseur`) résolu silencieusement par l'ordre d'`include()` — à sécuriser en introduisant des namespaces.
6. **Cosmétique** — le `name=` de l'URL `dashboard_rot` (agents/urls.py:8) ne correspond pas au nom réel de la vue `tableau_de_bord_rot`.
