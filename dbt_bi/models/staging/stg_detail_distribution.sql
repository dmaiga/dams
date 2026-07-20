with source as (
    select * from {{ source('dams_prod', 'core_detaildistribution') }}
)

select
    id as detail_distribution_id,
    distribution_id,
    lot_id,
    quantite::numeric(10, 2) as quantite,
    -- champ stocké, désynchronisation possible selon le chemin de vente emprunté
    -- (architecte/REFERENCE_TECHNIQUE_BI.md §4.1) : ne pas utiliser seul pour le stock restant,
    -- voir fct_stocks qui recalcule depuis stg_ventes.
    quantite_vendue::numeric(10, 2) as quantite_vendue_champ_stocke,
    specification
from source
