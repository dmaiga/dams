-- Dashboard 5, volet fournisseur (dbt-2, 2026-07-20 — KPI-403/404/405, absents jusqu'ici,
-- prévus côté Metabase avant l'abandon de Metabase, cf. ADR Metabase abandonné). Grain =
-- fournisseur x mois. Calibration : les prix d'achat système peuvent différer de la réalité
-- négociée (renégociation post-réception, cf. AMELIORATIONS_DAMS.md DM). La correction
-- saisie via bi.AjustementPrixAchat (admin Django) est agrégée en moyenne pondérée par
-- quantité, à la clé fournisseur x mois (fct_ventes n'expose pas lot_id, voir
-- stg_ajustements_prix_achat.sql). marge_systeme = prix d'achat système (fct_ventes tel
-- quel) ; marge_calibree = corrigée si un ajustement existe pour ce fournisseur x mois,
-- sinon identique à marge_systeme (COALESCE).
with ventes_fournisseur as (
    select
        fournisseur_id,
        date_trunc('month', date_vente)::date as mois,
        sum(quantite) as quantite_vendue,
        sum(total_vente) as ca,
        sum(total_cout_achat) as cout_achat_systeme,
        sum(total_vente - total_cout_achat) as marge_systeme
    from {{ ref('fct_ventes') }}
    where fournisseur_id is not null
    group by fournisseur_id, date_trunc('month', date_vente)::date
),

prix_corrige as (
    select
        fournisseur_id,
        make_date(annee, mois, 1) as mois,
        sum(quantite_concernee * prix_achat_corrige)
            / nullif(sum(quantite_concernee), 0) as prix_achat_corrige_pondere
    from {{ ref('stg_ajustements_prix_achat') }}
    group by fournisseur_id, make_date(annee, mois, 1)
)

select
    row_number() over (order by vf.fournisseur_id, vf.mois) as fournisseur_mois_id,
    vf.fournisseur_id,
    f.nom as fournisseur_nom,
    vf.mois,
    vf.ca,
    vf.cout_achat_systeme,
    vf.marge_systeme,
    case
        when vf.ca = 0 then null
        else round(100.0 * vf.marge_systeme / vf.ca, 2)
    end as marge_pct_systeme,
    pc.prix_achat_corrige_pondere,
    (pc.prix_achat_corrige_pondere is not null) as calibre,
    coalesce(vf.quantite_vendue * pc.prix_achat_corrige_pondere, vf.cout_achat_systeme) as cout_achat_calibre,
    vf.ca - coalesce(vf.quantite_vendue * pc.prix_achat_corrige_pondere, vf.cout_achat_systeme) as marge_calibree,
    case
        when vf.ca = 0 then null
        else round(
            100.0 * (vf.ca - coalesce(vf.quantite_vendue * pc.prix_achat_corrige_pondere, vf.cout_achat_systeme)) / vf.ca,
            2
        )
    end as marge_calibree_pct
from ventes_fournisseur vf
left join {{ ref('dim_fournisseur') }} f on vf.fournisseur_id = f.fournisseur_id
left join prix_corrige pc on vf.fournisseur_id = pc.fournisseur_id and vf.mois = pc.mois
order by vf.mois, marge_calibree desc nulls last
