{{ config(materialized='table') }}

-- Tabla de hechos: un valor de un indicador economico en un periodo dado.
-- Grano: 1 fila = 1 serie x 1 periodo (mes).
--
-- TODO SCD Tipo 2: el BCRP revisa cifras preliminares (ej. Reservas
-- Internacionales). Si en una nueva extraccion cambia el `value` para la
-- misma (series_code, period_date), hoy este modelo se queda solo con la
-- version mas reciente (ver dedup en silver). Para auditar el historial de
-- revisiones, convertir esto en un dbt snapshot con estrategia `check` sobre
-- la columna `value`.

select
    series_code,
    period_date,
    value,
    extracted_at
from {{ ref('int_bcrp_series_cleaned') }}
