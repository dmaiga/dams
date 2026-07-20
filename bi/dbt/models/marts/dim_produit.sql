-- Pas de categorie ni fournisseur_id sur core_produit (le fournisseur est porté par le lot,
-- un produit peut avoir plusieurs fournisseurs selon les lots) — décision différée au PO,
-- voir architecte/05_Architecture.md.
select
    produit_id,
    nom,
    poids_unitaire_kg,
    (poids_unitaire_kg is not null) as est_conditionne
from {{ ref('stg_produits') }}
