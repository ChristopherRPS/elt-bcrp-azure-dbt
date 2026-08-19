{{
    config(
        materialized='view'
    )
}}

-- Capa silver: parsea el periodo textual del BCRP ("Ene.2023") a una fecha
-- real, castea el valor a numerico, y deduplica quedandome con la extraccion
-- mas reciente por (serie, periodo) -- importante porque el pipeline puede
-- correr mas de una vez sobre el mismo rango de fechas (idempotencia).
--
-- Nota de portabilidad a Synapse/SQL Server: reemplazar make_date(y, m, 1)
-- por DATEFROMPARTS(y, m, 1); el resto del SQL es estandar y no requiere cambios.

with source as (

    select * from {{ ref('stg_bcrp_raw') }}

),

parsed as (

    select
        series_code,
        series_name,
        period_name,
        cast(split_part(period_name, '.', 2) as integer) as period_year,
        case split_part(period_name, '.', 1)
            when 'Ene' then 1
            when 'Feb' then 2
            when 'Mar' then 3
            when 'Abr' then 4
            when 'May' then 5
            when 'Jun' then 6
            when 'Jul' then 7
            when 'Ago' then 8
            when 'Sep' then 9
            when 'Oct' then 10
            when 'Nov' then 11
            when 'Dic' then 12
        end as period_month,
        {{ safe_cast_double('value_raw') }} as value,
        extracted_at
    from source
    where value_raw is not null

),

valid_only as (

    select *
    from parsed
    where period_month is not null  -- descarta periodos con mes no reconocido

),

with_date as (

    select
        series_code,
        series_name,
        make_date(period_year, period_month, 1) as period_date,
        value,
        extracted_at
    from valid_only

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by series_code, period_date
            order by extracted_at desc
        ) as rn
    from with_date

)

select
    series_code,
    series_name,
    period_date,
    value,
    extracted_at
from deduplicated
where rn = 1
