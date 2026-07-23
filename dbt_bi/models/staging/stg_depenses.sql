with depenses_source as (
    select * from {{ source('dams_prod', 'core_depense') }}
)

select
    id as depense_id,
    effectue_par_id as agent_id,
    montant::numeric(12, 2) as montant,
    -- 21 lignes NULL en base malgré le default non-NULL du modèle
    -- (architecte/REFERENCE_TECHNIQUE_BI.md §3) : fallback vers 'DIVERS', la valeur par défaut
    -- de core.models.Depense.categorie, plutôt qu'un pseudo-libellé 'INCONNU' hors choices.
    coalesce(categorie, 'DIVERS') as categorie,
    coalesce(source, 'INCONNU') as source_depense,
    date_depense
from depenses_source
