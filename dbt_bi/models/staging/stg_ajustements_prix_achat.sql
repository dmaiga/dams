-- Source : bi_ajustementprixachat (app Django bi, saisie admin uniquement, cf. dbt-2).
-- fournisseur_id/annee/mois sont requis côté modèle Django (voir bi/models.py) : fct_ventes
-- n'expose pas lot_id (dérivé uniquement jusqu'à fournisseur_id, cf. fct_ventes.sql), donc
-- la clé de jointure effective pour vw_marge_fournisseur est fournisseur x année x mois,
-- pas le lot précis. reference_lot/produit_id restent des champs de traçabilité.
with source as (
    select * from {{ source('dams_bi_app', 'bi_ajustementprixachat') }}
)

select
    id as ajustement_id,
    nullif(reference_lot, '') as reference_lot,
    produit_id,
    fournisseur_id,
    annee,
    mois,
    quantite_concernee::numeric(10, 2) as quantite_concernee,
    prix_achat_corrige::numeric(10, 2) as prix_achat_corrige,
    date_saisie
from source
