# Sprint 5 — Refonte UI/UX exécutive (27–31 juillet 2026)

**Objectif** : implémenter dans les templates Django la direction visuelle validée le 24/07/2026,
sur les 5 dashboards réels de l'app `bi` — sans changer la logique des vues (`views.py` /
`models.py` / dbt restent inchangés, seule la présentation évolue).
**Jalon** : livre S-709 (passe de cohérence UI/UX, 🔴 MUST du backlog EPIC 7).
**Owner sprint** : BI Dev (exécution), Chef Projet (DoD), Direction (validation finale).

---

## Référence design

- **Maquette validée** : [bi/maquettes/DAMS_BI_maquette_v1.html](../bi/maquettes/DAMS_BI_maquette_v1.html)
  (Direction, 24/07/2026) — navigable, 5 onglets, contenu et libellés repris des dashboards réels.
- **Brief de direction artistique** (fourni par la Direction) : BI exécutif inspiré Power BI /
  Tableau / Sigma / Hex / Metabase / Bloomberg Terminal (minimalisme uniquement) — fond blanc,
  grands espaces blancs, bordures fines, quasi pas d'ombre, typographie professionnelle. Exclus
  explicitement : glassmorphism, dégradés, neumorphisme, animations surdimensionnées, dashboards
  colorés.
- La palette/typo/layout doivent être **extraits de la maquette** (tokens CSS), pas redevinés.

---

## Backlog du sprint

Détail complet dans [owner/02_Backlog.md](../owner/02_Backlog.md).

| # | Story | Priorité |
|---|-------|----------|
| S-709 | Passe de cohérence UI/UX sur les 5 dashboards (couleurs, titres, espacement, responsive, états vides/erreur) | 🔴 MUST |

---

## Décisions à prendre en tout début de sprint (pas en cours de route)

1. **Charts** — **Tranché (début de sprint)** : hybride. Passage en CSS/SVG natif (listes à
   barres horizontales `.bi-barlist`, split-bar `.bi-splitbar`) pour les classements simples —
   Produits (marge), Agents (kilo vendu par équipe, kg/jour vs objectif 50), Dépenses (répartition
   par catégorie). Chart.js conservé uniquement pour la courbe multi-séries de Santé Globale
   (CA/dépenses ROT/marge brute) : reproduire à la main un axe Y dynamique et le scaling pour une
   série temporelle à N points représentait le seul vrai risque d'ingénierie du lot, pour un gain
   surtout esthétique. 4 des 5 usages de Chart.js supprimés ; la dépendance CDN reste pour 1 seul
   graphique.
2. **Thème sombre** : l'app DAMS tourne sur DaisyUI `data-theme="corporate"` figé, sans bascule
   clair/sombre existante. Décision actée : scope limité au thème clair de la maquette ; le mode
   sombre présent dans la maquette (exigé par l'outil de prévisualisation) **n'est pas à porter**
   dans l'app réelle — à documenter comme décision, pas comme oubli.
3. **Portée** : uniquement `bi/templates/bi/*.html` + une nouvelle feuille `bi/static/bi/*.css`.
   Aucune modification de `views.py`, `models.py`, `constants.py` (statuts) ou des modèles dbt —
   le contenu affiché ne change pas, seule sa présentation.

---

## Plan (ordre d'exécution — pas de dates calendaires figées par tâche)

1. Extraire les tokens de la maquette (couleurs, typo, espacements, rayons de bordure) dans une
   feuille dédiée `bi/static/bi/dashboard.css`, chargée après DaisyUI dans `base_dashboard.html`
   — surcharge ciblée, pas de réécriture globale de DaisyUI.
2. Réécrire `base_dashboard.html` : topbar/breadcrumb, tabnav soulignée (remplace les onglets
   pilule actuels `.bi-onglet`), ligne de filtres, sections à filets fins (remplace les
   `.bi-panel` actuels à ombre portée).
3. Reconstruire les tuiles KPI (`.bi-kpis`/`.bi-kpi`) selon le modèle grille à filets de la
   maquette (actuellement : bordure gauche colorée + ombre — à retirer).
4. Harmoniser les badges de statut (`.bi-badge`) sur la nouvelle palette (accent ink-blue,
   good/warning/critical redéfinis) — `constants.py` reste la seule source de vérité des statuts
   (vert/jaune/rouge/neutre), seul le rendu CSS de ces classes change.
5. Reprendre chaque template un par un, du plus simple au plus riche : Dépense → Vente →
   Fournisseur → Santé Globale → Agent.
6. Réimplémenter les graphiques selon la décision du point 1 ci-dessus.
7. Harmoniser les états vides (`.bi-vide`) et messages d'erreur sur la nouvelle palette.
8. Vérification manuelle des 5 dashboards en conditions réelles (même méthode que
   `chef_projet/BILAN_LIVRAISON_VS_VISION.md` §9) + `python -m pytest bi/` (les tests ne
   couvrent pas le rendu HTML en détail, mais doivent rester verts — aucune vue ne change).

---

## Definition of Done du sprint

Sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable :

- [x] Les 5 dashboards utilisent le nouveau système visuel — plus aucun `.bi-kpi`/`.bi-panel` à
  ombre portée ou bordure gauche colorée de l'ancien style
- [x] Aucun dégradé, glassmorphism, ombre > 1px, ni animation superflue (conforme au brief)
- [x] `python -m pytest bi/` toujours vert (19 passed)
- [x] Rendu programmatique des 5 pages réelles vérifié (Django test client, utilisateur
  `mdmaiga`, `?toutes_periodes=1`) : 5/5 en HTTP 200, pas d'erreur de template. Un bug
  bloquant trouvé et corrigé au passage — `d.montant_pct` localisé en `fr-fr` (virgule
  décimale) cassait l'attribut CSS `width:100,00%` de la split-bar Dépenses (`{% load l10n %}`
  + `|unlocalize`, cf. `dashboard_depenses.html`).
  **Reste à faire** : vérification visuelle dans un vrai navigateur (mise en page, responsive,
  interaction avec DaisyUI/Tailwind) — pas d'outil de rendu navigateur disponible dans cette
  session, donc non couvert par cette passe.
- [x] `bi/08_Dashboard_Catalog.md` mis à jour (note "Sprint 5 appliqué")

## Gate de sortie

- [ ] Direction valide visuellement les 5 dashboards **réels** (pas seulement la maquette)
- [ ] Aucune régression fonctionnelle (filtres, tri, bascule semaine/mois, comparaisons de
  période toujours opérants) — à confirmer en navigateur ; non régressée côté logique serveur
  (tests verts, mêmes noms de champs GET conservés dans tous les formulaires de filtre)

**Décision** : à valider en fin de sprint.

---

## Rétrospective

*(volet Direction — validation visuelle — à compléter en fin de sprint)*

Notes dev (implémentation) :

- Ce qui a bien marché : les tags natifs Django (`{% widthratio %}`, `{% cycle %}`) ont suffi à
  calculer les largeurs des `.bi-barlist`/`.bi-splitbar` sans toucher à `views.py` — la contrainte
  de périmètre (templates + CSS uniquement) a tenu sans compromis.
- Ce qui s'est mal passé : bug de localisation FR (virgule décimale) qui cassait un `width:` CSS
  sur le split-bar Dépenses — repéré uniquement en rendant réellement la page (pas visible à la
  seule lecture du template). Corrigé via `|unlocalize`.
- Écart avec la maquette : la courbe Santé Globale reste en Chart.js (décision actée, cf. section
  Décisions) — seul écart volontaire. Le shell topbar/brand de la maquette n'a pas été reproduit :
  `base_admin.html` fournit déjà sa propre chrome (sidebar + en-tête), un second bandeau de marque
  aurait dupliqué l'information.
- Non couvert : validation visuelle navigateur réelle (pas d'outil de rendu/screenshot dans cette
  session) — à faire manuellement avant la Gate de sortie.
