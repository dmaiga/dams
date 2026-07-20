-- Dashboard 3, partie 2 (KPI-701/702, 20/07/2026). Grain = catégorie x mois. montant_pct =
-- part de la catégorie dans le total des dépenses du mois (pas du CA — KPI-008/depenses_pct
-- sur vw_rentabilite_globale couvre déjà le ratio dépenses/CA).
with depenses_mensuel_categorie as (
    select
        date_trunc('month', date_depense)::date as mois,
        categorie,
        sum(montant) as montant
    from {{ ref('fct_depenses') }}
    group by 1, 2
),

total_mensuel as (
    select
        mois,
        sum(montant) as total_mois
    from depenses_mensuel_categorie
    group by mois
)

select
    row_number() over (order by d.mois, d.categorie) as depense_categorie_id,
    d.mois,
    d.categorie,
    d.montant,
    case
        when t.total_mois = 0 then null
        else round(100.0 * d.montant / t.total_mois, 2)
    end as montant_pct
from depenses_mensuel_categorie d
left join total_mensuel t on d.mois = t.mois
order by d.mois, d.montant desc
