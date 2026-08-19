{{ config(materialized='table') }}

-- Dimension de fecha a nivel mes, derivada de los periodos realmente
-- observados en los datos (no un calendario generado aparte, para
-- mantener el proyecto simple). Si se necesita un calendario completo
-- sin huecos, ver TODO en docs/architecture.md.

select distinct
    period_date,
    extract(year from period_date) as year,
    extract(month from period_date) as month,
    extract(quarter from period_date) as quarter
from {{ ref('int_bcrp_series_cleaned') }}
order by period_date
