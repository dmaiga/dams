with source as (
    select * from {{ source('dams_prod', 'core_produit') }}
)

select
    id as produit_id,
    nom,
    -- renseigné = produit conditionné (carton/sac) ; vide = vendu au kg (vrac).
    -- Pivot de quantite_en_kg dans fct_ventes (architecte/REFERENCE_TECHNIQUE_BI.md §2.5)
    poids_unitaire_kg::numeric(6, 2) as poids_unitaire_kg,
    -- FCFA par unité vendue, indépendant du poids (décision réunion produits, 21/08/2026) ;
    -- renseigné = incentive terrain à taux dédié, remplace l'incentive au kg pour ce produit
    -- (voir fct_salaires.sql et paie/services/salaire_calculator.py::calcul_salaire_mamy).
    taux_incentive::numeric(10, 2) as taux_incentive
from source
