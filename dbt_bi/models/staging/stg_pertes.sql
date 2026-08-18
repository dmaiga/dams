with source as (
    select * from {{ source('dams_prod', 'core_perte') }}
)

select
    id as perte_id,
    lot_id,
    vente_id,
    detail_distribution_id,
    quantite_perdue::numeric(10, 2) as quantite_perdue,
    -- Kg perdus utilisés uniquement pour l'incentive de l'agent (sprint-10, 2026-08-18) —
    -- distinct de quantite_perdue, qui reste un concept de décompte de stock (kg pour un
    -- produit vrac, nombre de sacs/cartons pour un produit conditionné). Toujours en kg.
    -- Peut être nul pour les pertes créées avant ce sprint (colonne ajoutée après coup).
    coalesce(kilo_perdu_incentive::numeric(10, 2), 0) as kilo_perdu_incentive,
    date_perte::date as date_perte
from source
