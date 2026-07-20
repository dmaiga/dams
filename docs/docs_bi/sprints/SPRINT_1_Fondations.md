# Sprint 1 — Fondations (05–11 juillet 2026)

> ✅ **Statut : réalisé (17/07/2026), en écart positif sur le plan initial.** Le schéma cible a été confronté au schéma réel de production (`input/dams_2026-07-12.dump`, restauré en local dans PostgreSQL 17) avant tout code — écarts corrigés dans [architecte/05_Architecture.md](../architecte/05_Architecture.md#note-de-traçabilité), [architecte/FLUX_PAIEMENT.md](../architecte/FLUX_PAIEMENT.md) et [architecte/REFERENCE_TECHNIQUE_BI.md](../architecte/REFERENCE_TECHNIQUE_BI.md) (voir R9–R14 dans [chef_projet/RISQUES.md](../chef_projet/RISQUES.md)). Livré : 12 modèles staging (plus que les 4 planifiés — le schéma réel exige plus de sources que prévu), 4 dimensions, **5 fact tables**, **71 tests dbt** (90 PASS, 1 WARN documenté, 0 ERROR). Détail dans `dbt/README.md`.

**Objectif** : projet dbt opérationnel + 5 fact tables chargées et testées dans le schéma `bi_`.
**Jalon Roadmap** : G1 — *Facts OK*
**Owner sprint** : Architecte (exécution) / Chef Projet (gate)

---

## Backlog du sprint

Voir détail complet dans [owner/02_Backlog.md](../owner/02_Backlog.md).

| # | Story | Priorité |
|---|-------|----------|
| S-001 | Projet dbt + schéma `bi_` isolé | 🔴 MUST |
| S-002 | 5 fact tables (ventes, salaires, dépenses, stocks, agrégats) | 🔴 MUST |
| S-003 | 5+ dimensions *(amorcé, finalisé Sprint 2)* | 🔴 MUST |
| S-004 | 15+ tests dbt (nullité, unicité, logique métier) | 🔴 MUST |

---

## Plan jour par jour (réalisé en une session le 17/07/2026)

| Jour (cible) | Livrable | Réalisé |
|------|----------|---------|
| Lun 5 | Structure dossiers, `dbt init`, schéma `bi_` créé, `.env.example` + `packages.yml` + `require-dbt-version` figée (ADR-007) | ✅ dbt Core 1.12.0 + dbt-postgres 1.11.0 dans venv dédié, base locale `dams_dev` restaurée depuis le dump, schéma `bi_`, `.env`/`.env.example`, profil `dams_bi` via `env_var()` |
| Mar 6 | 4 staging models | ✅ **12** modèles staging (le schéma réel — multi-hop `core_vente → detail_distribution → distribution_agent/lot_entrepot` — nécessite plus de sources que prévu par le plan initial) |
| Mer 7 | `fct_ventes` testée (~50k lignes attendu) | ✅ 3013 lignes (= exactement `core_vente` source), 0% de NULL sur les colonnes dérivées (superviseur/produit/fournisseur/prix_achat), `quantite_en_kg` implémentée |
| Jeu 8 | `fct_salaires` + `fct_depenses` testées | ✅ + 1 écart de donnée réel détecté (2 lignes salaire superviseur, cf. rétrospective) traité en test `warn` documenté, pas caché |
| Ven 9 | `fct_stocks` + 15 tests dbt (`dbt test` vert) | ✅ + `fct_paiements_fournisseur` (5ᵉ fact) ajoutée. **71 tests** (largement au-dessus de la cible 15+), `dbt build` : 90 PASS / 1 WARN / 0 ERROR |

---

## Definition of Done du sprint

Sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable — *pour un dbt Model (Fact ou Dimension)* :

- [x] Code SQL écrit et testé
- [x] Schéma défini avec types corrects
- [x] Au moins 2 tests dbt par fact : nullité + unicité (PK)
- [x] Commentaires documentés sur chaque colonne (annotations des écarts REFERENCE_TECHNIQUE_BI.md dans les modèles)
- [x] Pas de valeurs hardcodées (variables/macros)
- [x] Aucun secret/credential/host en dur — config via env ([architecte/04_ADR.md — ADR-007](../architecte/04_ADR.md)) ; `.env` gitignoré, profil dbt via `env_var()`
- [x] Nombre de lignes ≈ attendu (comparé à DAMS prod) — exact sur tous les facts/dims
- [x] `dbt parse`/`dbt build` réussit sans erreur
- [ ] Git push (en attente de confirmation utilisateur, cf. commit)

## Gate de sortie (G1)

- [x] 5 fact tables chargées (`fct_ventes`, `fct_salaires`, `fct_depenses`, `fct_stocks`, `fct_paiements_fournisseur`)
- [x] 15+ tests dbt passent (71 tests, 90 PASS / 1 WARN / 0 ERROR)
- [x] Données cohérentes avec DAMS production (comptages exacts : Vente 3013, Salaire 21, Depense 499, LotEntrepot 241, PaiementFournisseur 246)

**Décision** : ✅ **GO Sprint 2**

---

## Rétrospective

- **Ce qui a bien marché** : l'investigation préalable (dump + audit code REFERENCE_TECHNIQUE_BI.md) a évité toute surprise pendant le codage — le join critique `fct_ventes` (multi-hop vente→detail_distribution→distribution_agent/lot_entrepot) a fonctionné du premier coup, 0% de NULL, aucun fan-out. PostgreSQL local déjà disponible (pas eu besoin de Docker).
- **Ce qui a bloqué** : deux corrections mineures en cours de route — `extract(day from integer)` invalide en PostgreSQL (Postgres retourne déjà un entier pour `date - date`), et un test d'égalité `salaire_total = salaire_base + incentive` qui a révélé un vrai écart de données (2 lignes, agents `entrepot`/superviseur, +15 000 FCFA chacune — cohérent avec R14, dotation de fonction mal appliquée côté DAMS) : traité en test `warn` documenté plutôt que masqué.
- **Statut** : 🟢
- **Ajustements pour Sprint 2** : finaliser les 5 dimensions restantes du plan initial (déjà 4/5 faites), déployer Metabase, connecter au schéma `bi_` de `dams_dev` (ou de la vraie base prod une fois l'accès confirmé).
