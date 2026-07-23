-- Source : bi_ajustementprixachat (app Django bi, saisie admin uniquement, cf. dbt-2 ; refonte
-- 23/07/2026 dbt-7). Le modèle Django ne stocke plus que lot_id — fournisseur_id, produit_id,
-- année et mois sont dérivés ici via jointure sur stg_lots (core_lotentrepot.date_reception),
-- pas resaisis à la main. La clé de jointure effective pour vw_marge_fournisseur est donc
-- fournisseur x produit x mois (via ce lot), le lot lui-même reste la référence de saisie.
with source as (
    select * from {{ source('dams_bi_app', 'bi_ajustementprixachat') }}
),

lots as (
    select * from {{ ref('stg_lots') }}
)

select
    s.id as ajustement_id,
    s.lot_id,
    l.fournisseur_id,
    l.produit_id,
    extract(year from l.date_reception)::int as annee,
    extract(month from l.date_reception)::int as mois,
    s.quantite_concernee::numeric(10, 2) as quantite_concernee,
    s.prix_achat_corrige::numeric(10, 2) as prix_achat_corrige,
    s.date_saisie
from source s
left join lots l on s.lot_id = l.lot_id
