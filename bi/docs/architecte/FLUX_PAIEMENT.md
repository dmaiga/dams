# Flux de Paiement & Salaires – DAMS BI

Document visuel du flux financier complet pour clarifier les sources et transformations de données.

---

## 1. FLUX VENTE (Agent → Superviseur → ROT)

```
┌─────────────────────────────────────────────────────────────────────┐
│ JOUR J : Agent Terrain Vend                                          │
│                                                                      │
│ Exemple : Agent A vend 100 kg de riz à 5,000 FCFA/kg               │
│ ├─ Quantité : 100 kg                                               │
│ ├─ Prix de vente : 5,000 FCFA/kg                                   │
│ ├─ CA généré : 100 × 5,000 = 500,000 FCFA                          │
│ ├─ Prix achat : 2,500 FCFA/kg                                      │
│ ├─ Coût achat : 100 × 2,500 = 250,000 FCFA                         │
│ └─ Marge : 500,000 − 250,000 = 250,000 FCFA                        │
│                                                                      │
│ Table DAMS : core_vente (schéma public, PAS un schéma "core")       │
│ ├─ vente.id = 1234                                                  │
│ ├─ vente.agent_id = Agent_A (terrain)                               │
│ ├─ vente.detail_distribution_id = 789                               │
│ ├─ vente.quantite = 100                                             │
│ ├─ vente.prix_vente_unitaire = 5,000                                │
│ ├─ vente.date_vente = 2026-01-15                                    │
│ └─ vente.mode_paiement = 'comptant'                                 │
│                                                                      │
│ ⚠ vente.superviseur_id et vente.prix_achat_unitaire n'existent PAS  │
│   sur core_vente. Obtenus par jointure :                            │
│   detail_distribution → distribution_agent.superviseur_id           │
│   detail_distribution → lot_entrepot.prix_achat_unitaire            │
└─────────────────────────────────────────────────────────────────────┘

         Agent A "reçoit" l'argent : ligne Recouvrement générée automatiquement
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ IMMÉDIAT (même transaction que la vente) : Recouvrement Agent →      │
│ Superviseur                                                          │
│                                                                      │
│ ⚠ Corrigé : ce n'est PAS une remise physique différée de J+2.       │
│ La ligne Recouvrement est créée automatiquement, dans la même       │
│ transaction que la Vente (100% des ventes sont comptant en base) —  │
│ montant_recouvre = vente.total_vente. Confirmé sur au moins 3       │
│ chemins de code différents (REFERENCE_TECHNIQUE_BI.md §4.3).        │
│                                                                      │
│ Table DAMS : core_recouvrement                                      │
│ ├─ recouvrement.id = 5001                                           │
│ ├─ recouvrement.agent_id = Agent_A                                  │
│ ├─ recouvrement.superviseur_id = Superviseur_X                      │
│ ├─ recouvrement.montant_recouvre = 500,000                          │
│ ├─ recouvrement.date_recouvrement = date_vente (identique)          │
│ └─ recouvrement.bonus_accorde = False (CA < seuil)                  │
└─────────────────────────────────────────────────────────────────────┘

         Superviseur X détient : 500,000 FCFA (+ autres agents)
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ JOUR J+5 : Cumul Superviseur (ses 5 agents)                          │
│                                                                      │
│ Superviseur X a recouvré de ses 5 agents :                          │
│ ├─ Agent A : 500,000 FCFA                                           │
│ ├─ Agent B : 450,000 FCFA                                           │
│ ├─ Agent C : 350,000 FCFA                                           │
│ ├─ Agent D : 100,000 FCFA                                           │
│ ├─ Agent E : 80,000 FCFA                                            │
│ └─ TOTAL : 1,480,000 FCFA                                           │
│                                                                      │
│ Superviseur détient : 1,480,000 FCFA (cash physique)                │
└─────────────────────────────────────────────────────────────────────┘

         Superviseur X → ROT (action manuelle, cadence variable)
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ CADENCE MANUELLE (pas de rythme fixe imposé par le code) : Remise    │
│ Superviseur → ROT                                                    │
│                                                                      │
│ ⚠ Corrigé : contrairement au recouvrement agent→superviseur (auto-  │
│ matique), cette remise est une action manuelle et différée, jamais  │
│ déclenchée automatiquement par une vente ou un recouvrement. Le     │
│ garde-fou de non-dépassement du cash disponible existe dans le code │
│ mais ne lève jamais d'erreur en pratique (voir R13, chef_projet/    │
│ RISQUES.md).                                                        │
│                                                                      │
│ Superviseur X remet son cash à ROT :                                │
│ 1,480,000 FCFA                                                      │
│                                                                      │
│ Table DAMS : core_recouvrementsuperviseur                           │
│ ├─ reco_sup.id = 9001                                               │
│ ├─ reco_sup.superviseur_id = Superviseur_X                          │
│ ├─ reco_sup.rot_id = ROT_1                                          │
│ ├─ reco_sup.montant = 1,480,000                                     │
│ └─ reco_sup.date_recouvrement = 2026-01-22                          │
│                                                                      │
│ ROT détient maintenant : 1,480,000 FCFA (de Sup X)                  │
│ + autres superviseurs (Sup Y, Z, etc.)                              │
└─────────────────────────────────────────────────────────────────────┘

         ROT décide : Dépenses vs Banque
                ↙                    ↘
    Dépenses ROT            Versement Bancaire
```

---

## 2. FLUX DÉPENSES (ROT)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ROT Reçoit Cash de Superviseurs (cadence manuelle, cf. §1)           │
│                                                                      │
│ Cash disponible :                                                   │
│ ├─ Superviseur X : 1,480,000 FCFA                                   │
│ ├─ Superviseur Y : 1,200,000 FCFA                                   │
│ ├─ Superviseur Z : 800,000 FCFA                                     │
│ └─ TOTAL CASH : 3,480,000 FCFA                                      │
└─────────────────────────────────────────────────────────────────────┘

         ROT utilise l'argent pour dépenses opérationnelles
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Dépenses Opérationnelles (pas de fenêtre temporelle imposée) —       │
│ ⚠ effectue_par référence n'importe quel core_agent, pas restreint   │
│ au type 'rot' au niveau du modèle — confirmer empiriquement la      │
│ répartition réelle (REFERENCE_TECHNIQUE_BI.md, risque R10)          │
│                                                                      │
│ ROT effectue des dépenses :                                         │
│                                                                      │
│ Table DAMS : core_depense                                           │
│                                                                      │
│ 1. Transport Marchandise                                            │
│    ├─ depense.id = 1                                               │
│    ├─ depense.effectue_par = ROT_1                                  │
│    ├─ depense.categorie = 'TRANSPORT_MARCHANDISE'                   │
│    ├─ depense.montant = 200,000 FCFA                                │
│    ├─ depense.note = "Transport Bamako → Ségou"                     │
│    └─ depense.date_depense = 2026-01-25                             │
│                                                                      │
│ 2. Carburant                                                        │
│    ├─ depense.id = 2                                               │
│    ├─ depense.categorie = 'CARBURANT'                               │
│    ├─ depense.montant = 150,000 FCFA                                │
│    └─ depense.date_depense = 2026-01-26                             │
│                                                                      │
│ 3. Maintenance Véhicule                                             │
│    ├─ depense.id = 3                                               │
│    ├─ depense.categorie = 'MAINTENANCE_VEHICULE'                    │
│    ├─ depense.montant = 100,000 FCFA                                │
│    └─ depense.date_depense = 2026-01-27                             │
│                                                                      │
│ TOTAL DÉPENSES : 450,000 FCFA                                       │
└─────────────────────────────────────────────────────────────────────┘

         Cash Restant : 3,480,000 − 450,000 = 3,030,000 FCFA
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Versement Bancaire (cadence manuelle) — champ actif : effectue_par   │
│ ⚠ le champ versement.superviseur existe mais est déprécié, jamais   │
│ écrit par les flux actuels                                          │
│                                                                      │
│ ROT verse à la banque : 3,030,000 FCFA                              │
│                                                                      │
│ Table DAMS : core_versementbancaire                                 │
│ ├─ versement.id = 7001                                              │
│ ├─ versement.effectue_par = ROT_1                                   │
│ ├─ versement.montant_vente = 3,030,000 FCFA                         │
│ ├─ versement.montant_hors_vente = 0 FCFA                            │
│ ├─ versement.date_versement_reelle = 2026-01-31                     │
│ └─ versement.description = "Versement ventes Janvier"               │
└─────────────────────────────────────────────────────────────────────┘

         Banque reçoit : 3,030,000 FCFA
         Trésorier peut vérifier la comptabilité
```

---

## 3. FLUX SALAIRES & INCENTIVES (Parallèle)

⚠ La cadence mensuelle est une **convention d'usage** (bornes calculées via le calendrier), pas une règle imposée par le code — génération et validation de la paie sont deux actions manuelles distinctes déclenchées depuis l'interface direction, sans planification automatique (cf. REFERENCE_TECHNIQUE_BI.md §4.5). Idem pour la clôture mensuelle du solde superviseur (`ClotureMensuelle`) : commande/vue manuelle, jamais exécutée automatiquement par un cron.

```
┌─────────────────────────────────────────────────────────────────────┐
│ CHAQUE MOIS (par convention) : Calcul Salaires & Incentives          │
│                                                                      │
│ === AGENTS TERRAIN (Mamies) ===                                     │
│                                                                      │
│ Agent A (Terrain) :                                                 │
│ ├─ Salaire de base : 100,000 FCFA                                   │
│ ├─ Kg vendus (mois) : 500 kg                                        │
│ ├─ Incentive : 500 kg × 25 FCFA/kg = 12,500 FCFA                    │
│ └─ Salaire total : 100,000 + 12,500 = 112,500 FCFA                  │
│                                                                      │
│ Agent B (Terrain) :                                                 │
│ ├─ Salaire de base : 100,000 FCFA                                   │
│ ├─ Kg vendus (mois) : 450 kg                                        │
│ ├─ Incentive : 450 × 25 = 11,250 FCFA                               │
│ └─ Salaire total : 111,250 FCFA                                     │
│                                                                      │
│ Agent C, D, E : [idem]                                              │
│                                                                      │
│ === AGENTS GROS ===                                                 │
│                                                                      │
│ Agent Gros A :                                                      │
│ ├─ Salaire de base : 0 FCFA (à la commission)                       │
│ ├─ Cartons vendus : 200 cartons                                     │
│ ├─ Calcul : ≥ 200 cartons → salaire fixe de 90,000 FCFA            │
│ └─ Salaire total : 90,000 FCFA                                      │
│                                                                      │
│ === SUPERVISEURS ===                                                │
│                                                                      │
│ Superviseur X :                                                     │
│ ├─ Salaire de base : 200,000 FCFA                                   │
│ ├─ Dotation de fonction : 50,000 FCFA                               │
│ ├─ Kg supervisés (agents) : 2,000 kg                                │
│ ├─ Bonus : Palier 2,000 kg → 4% × (hypothétique CA) = 100,000      │
│ └─ Salaire total : 200,000 + 50,000 + 100,000 = 350,000 FCFA       │
│                                                                      │
│ TOTAL PAIE MOIS : ~1,200,000 FCFA (ex. pour tous agents + sup)     │
│                                                                      │
│ Table DAMS : core_salaire                                           │
│ ├─ salaire.agent_id = Agent_A                                       │
│ ├─ salaire.date_debut = 2026-01-01                                  │
│ ├─ salaire.date_fin = 2026-01-31                                    │
│ ├─ salaire.salaire_base = 100,000                                   │
│ ├─ salaire.incentive = 12,500                                       │
│ └─ salaire.salaire_total = 112,500                                  │
└─────────────────────────────────────────────────────────────────────┘

         Paie versée par ROT (ou directement bancaire)
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│ FIN DE MOIS : Versement Salaires                                     │
│                                                                      │
│ ROT verse la paie :                                                 │
│ ├─ Agents terrain + gros + superviseurs                             │
│ ├─ Total : 1,200,000 FCFA                                           │
│ └─ Compte bancaire ou cash distribution                             │
│                                                                      │
│ [Normalement depuis un compte entreprise, pas du cash des ventes]   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. CALCUL RENTABILITÉ NETTE (Synthèse)

```
╔═════════════════════════════════════════════════════════════════════╗
║           RENTABILITÉ NETTE – JANVIER 2026 (Exemple)               ║
╚═════════════════════════════════════════════════════════════════════╝

1. CHIFFRE D'AFFAIRES (CA)
   ∑ Toutes les ventes × prix_vente = 10,000,000 FCFA
   (Source : core_vente)

2. COÛT D'ACHAT
   ∑ Toutes les ventes × prix_achat = 5,000,000 FCFA
   (Source : core_lotentrepot.prix_achat_unitaire, via jointure — pas une colonne de core_vente)

3. MARGE BRUTE = CA − Coût Achat
   10,000,000 − 5,000,000 = 5,000,000 FCFA

4. SALAIRES & INCENTIVES
   Agents terrain + gros + superviseurs = 1,200,000 FCFA
   (Source : core_salaire — ⚠ dotation de fonction superviseur non appliquée en pratique, voir R14)

5. DÉPENSES ROT
   Transport, carburant, maintenance, etc. = 400,000 FCFA
   (Source : core_depense)

6. RENTABILITÉ NETTE
   Marge Brute − Salaires − Dépenses
   = 5,000,000 − 1,200,000 − 400,000
   = 3,400,000 FCFA ✅ RENTABLE
   
   Ratio :
   ├─ Rentabilité / CA = 3,400,000 / 10,000,000 = 34%
   ├─ Salaires / CA = 1,200,000 / 10,000,000 = 12%
   └─ Dépenses / CA = 400,000 / 10,000,000 = 4%
```

---

## 5. Mapping Data Source → BI

| Flux | Table DAMS | Colonne | → | Table BI | Formule |
|------|-----------|---------|---|----------|---------|
| **Vente** | core_vente | quantite | → | fct_ventes | quantité |
| | core_vente | prix_vente_unitaire | → | fct_ventes | prix_vente_unitaire |
| | core_lotentrepot ⚠ *(via detail_distribution → lot_entrepot, pas colonne directe de Vente)* | prix_achat_unitaire | → | fct_ventes | prix_achat_unitaire |
| | core_distributionagent ⚠ *(via detail_distribution → distribution_agent, pas colonne directe de Vente)* | superviseur_id | → | fct_ventes | superviseur_id |
| **Marge** | core_vente + core_lotentrepot (jointure) | — | → | fct_ventes.marge_unitaire | prix_vente − prix_achat |
| **Recouvrement** | core_recouvrement | montant_recouvre | → | fct_ventes (agrégé) | ∑ recouvrement |
| **Salaire** | core_salaire | salaire_base | → | fct_salaires | salaire_base |
| | core_salaire | incentive | → | fct_salaires | incentive |
| **Dépense** | core_depense | montant | → | fct_depenses | montant |
| | core_depense | categorie | → | fct_depenses | categorie |
| | core_depense.effectue_par_id → core_agent ⚠ *(pas de colonne "rot_id")* | — | → | fct_depenses.agent_id | à filtrer par type_agent |
| **Stock** | core_lotentrepot | quantite_restante | → | fct_stocks | quantite_restante |
| | core_lotentrepot | prix_achat_unitaire | → | fct_stocks | prix_achat_moyen |

⚠ **Gap non résolu** : `core_recouvrement`, `core_recouvrementsuperviseur` et `core_versementbancaire` existent bien en production mais ne sont mappés vers **aucun** `fct_*` cible dédié — seulement agrégés informellement dans "fct_ventes". La traçabilité cash intermédiaire (agent → superviseur → ROT → banque) n'est donc pas modélisée en BI pour l'instant. Sans impact sur le calcul de la rentabilité nette (qui ne dépend que de Vente/Salaire/Depense), mais à trancher si un dashboard de rapprochement bancaire est demandé plus tard (voir [chef_projet/RISQUES.md](../chef_projet/RISQUES.md)).

---

## 6. Validations Clés

```
✅ Coché = Vérifier chaque mois dans BI

□ CA = ∑ Ventes (montant total vendu par agent)
□ Marge = ∑(Prix_vente − Prix_achat) × Quantité
□ Recouvrements = Montant versé superviseur → ROT
□ Salaires = ∑ Salaire_base + ∑ Incentive
□ Dépenses = ∑ Depense (par catégorie)
□ Rentabilité Nette = Marge − Salaires − Dépenses
   ∟ Doit être > 0 pour être profitable
□ Stock = ∑ Quantité restante × Prix achat moyen
   ∟ Valeur immobilisée (idéalement < 20% CA)
```

---

## 7. Cas d'Anomalie (Red Flags)

```
🚨 Si Rentabilité Nette < 0
   → Investiguer : CA trop faible ? Salaires trop élevés ? Dépenses trop hautes ?
   
🚨 Si Dépenses > 50% Marge Brute
   → Crise opérationnelle, audit ROT requis
   
🚨 Si Salaires > 40% CA
   → Structure de coûts non viable
   
🚨 Si Stock > 30% CA
   → Capital immobilisé excessive, risque liquidité
   
🚨 Si Superviseur Marge < Coût Équipe
   → Superviseur déficitaire, restructuration envisager
```

---

## Notes Finales

- **Toutes les données** proviennent de tables DAMS production
- **BI synthétise & agrège** selon schéma en étoile (facts + dims)
- **Refresh nuitée** : dbt run chaque 23h00 Mali → schéma `bi_` mise à jour
- **Dashboards** lisent uniquement schéma `bi_` (zéro impact DAMS)
- **Traçabilité complète** : chaque KPI remonte à une transaction DAMS
- **Schéma confirmé le 16/07/2026** via lecture de `input/dams_2026-07-12.dump` — voir [05_Architecture.md](05_Architecture.md#note-de-traçabilité) pour le détail des écarts corrigés entre le modèle initialement documenté et le schéma réel de production
