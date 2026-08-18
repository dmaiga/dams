-- Sprint-11 (2026-08-18) : stock actuellement en main chez l'agent (kg non encore vendus ni
-- déclarés perdus), grain = 1 ligne par DetailDistribution encore active. Réplique en SQL
-- DetailDistribution.quantite_restante_calculee (core/models.py:1539-1557) : quantité distribuée
-- moins ventes déjà faites sur cette ligne moins pertes déclarées sur cette ligne — utilise
-- quantite_perdue (le champ qui décrémente réellement le stock, cf. sprint-10) et PAS
-- kilo_perdu_incentive (champ dédié à l'incentive, qui ne doit jamais toucher au stock — une
-- perte partielle dans un sac déjà vendu ne rend pas le sac disponible en stock).
-- Batch, pas temps réel (décision mdmaiga, 18/08/2026) : ce dashboard n'est consulté
-- qu'hebdomadairement, un décalage d'un cycle de refresh dbt est acceptable — voir
-- docs/sprints/sprint-11.md § Décisions actées, point 2. Ne conserve que les lignes avec un
-- reste strictement positif (une ligne totalement vendue/perdue n'a rien à afficher).
with detail as (
    select * from {{ ref('stg_detail_distribution') }}
),

distribution as (
    select * from {{ ref('stg_distribution_agent') }}
),

lots as (
    select * from {{ ref('stg_lots') }}
),

produits as (
    select * from {{ ref('dim_produit') }}
),

vendu_par_detail as (
    select detail_distribution_id, sum(quantite) as quantite_vendue
    from {{ ref('stg_ventes') }}
    group by detail_distribution_id
),

perdu_par_detail as (
    select detail_distribution_id, sum(quantite_perdue) as quantite_perdue
    from {{ ref('stg_pertes') }}
    where detail_distribution_id is not null
    group by detail_distribution_id
),

stock as (
    select
        dt.detail_distribution_id,
        d.agent_terrain_id as agent_id,
        d.superviseur_id,
        l.lot_id,
        l.produit_id,
        p.nom as produit_nom,
        p.poids_unitaire_kg,
        l.date_reception,
        dt.quantite
            - coalesce(vd.quantite_vendue, 0)
            - coalesce(pd.quantite_perdue, 0) as stock_restant
    from detail dt
    join distribution d on dt.distribution_id = d.distribution_id
    join lots l on dt.lot_id = l.lot_id
    join produits p on p.produit_id = l.produit_id
    left join vendu_par_detail vd on vd.detail_distribution_id = dt.detail_distribution_id
    left join perdu_par_detail pd on pd.detail_distribution_id = dt.detail_distribution_id
)

select
    row_number() over (order by detail_distribution_id) as stock_agent_id,
    detail_distribution_id,
    agent_id,
    superviseur_id,
    lot_id,
    produit_id,
    produit_nom,
    date_reception,
    stock_restant,
    case
        when poids_unitaire_kg is not null then stock_restant * poids_unitaire_kg
        else stock_restant
    end as stock_restant_kg
from stock
where stock_restant > 0
