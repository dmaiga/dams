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

1. **Charts** : la maquette remplace les graphiques Chart.js par des composants CSS/SVG légers
   (listes à barres horizontales, split-bar pour les dépenses) — sauf la courbe multi-séries de
   Santé Globale, restée en SVG natif dans la maquette elle-même. Décision à prendre : réécrire
   tous les graphiques en SVG/CSS natif (supprime la dépendance CDN Chart.js) ou ne remplacer que
   les classements simples et garder Chart.js pour les courbes/combos. Trancher avant de coder.
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

- [ ] Les 5 dashboards utilisent le nouveau système visuel — plus aucun `.bi-kpi`/`.bi-panel` à
  ombre portée ou bordure gauche colorée de l'ancien style
- [ ] Aucun dégradé, glassmorphism, ombre > 1px, ni animation superflue (conforme au brief)
- [ ] `python -m pytest bi/` toujours vert
- [ ] Vérification manuelle des 5 pages en conditions réelles
- [ ] `bi/08_Dashboard_Catalog.md` mis à jour si un libellé ou une structure visuelle change de
  façon notable

## Gate de sortie

- [ ] Direction valide visuellement les 5 dashboards **réels** (pas seulement la maquette)
- [ ] Aucune régression fonctionnelle (filtres, tri, bascule semaine/mois, comparaisons de
  période toujours opérants)

**Décision** : à valider en fin de sprint.

---

## Rétrospective

*(à remplir en fin de sprint)*

- Qu'est-ce qui a bien marché ?
- Qu'est-ce qui s'est mal passé ?
- Écart entre la maquette et le rendu final, s'il y en a un ?
