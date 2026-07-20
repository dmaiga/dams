with source as (
    select * from {{ source('dams_prod', 'core_agent') }}
)

select
    id as agent_id,
    user_id,
    -- valeurs réelles : direction, rot, entrepot (= "superviseur" métier), terrain,
    -- agent_gros, agent_polivalent, stagiaire, gestionnaire_stock
    -- (architecte/REFERENCE_TECHNIQUE_BI.md §3 / shared/GLOSSAIRE.md)
    type_agent,
    superviseur_id,
    est_actif,
    salaire_base_personnel::numeric(10, 2) as salaire_base_personnel,
    type_contrat,
    date_debut_fonction,
    date_fin_contrat
from source
