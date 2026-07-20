with source as (
    select * from {{ source('dams_prod', 'core_produit') }}
)

select
    id as produit_id,
    nom,
    -- renseigné = produit conditionné (carton/sac) ; vide = vendu au kg (vrac).
    -- Pivot de quantite_en_kg dans fct_ventes (architecte/REFERENCE_TECHNIQUE_BI.md §2.5)
    poids_unitaire_kg::numeric(6, 2) as poids_unitaire_kg
from source
