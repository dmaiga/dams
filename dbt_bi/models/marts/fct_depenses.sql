-- Pas de colonne "rot_id" sur core_depense : effectue_par_id référence n'importe quel
-- core_agent, sans contrainte de type (architecte/REFERENCE_TECHNIQUE_BI.md §1.23, R10).
-- On expose type_agent pour que le filtrage/validation se fasse explicitement en aval,
-- plutôt que de supposer que seul un ROT y écrit.
with depenses as (
    select * from {{ ref('stg_depenses') }}
),

agents as (
    select * from {{ ref('stg_agents') }}
)

select
    d.depense_id,
    d.agent_id,
    a.type_agent,
    d.categorie,
    d.source_depense,
    d.montant,
    d.date_depense
from depenses d
left join agents a on d.agent_id = a.agent_id
