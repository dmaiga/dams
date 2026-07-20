-- Fenêtre : marge autour de la période MVP figée 01/01-30/06/2026 (ADR-004)
with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2025-12-01' as date)",
        end_date="cast('2026-08-01' as date)"
    ) }}
)

select
    cast(to_char(date_day, 'YYYYMMDD') as int) as date_id,
    cast(date_day as date) as date,
    extract(isodow from date_day) as jour_semaine,
    extract(week from date_day) as semaine,
    extract(month from date_day) as mois,
    extract(year from date_day) as annee
from spine
