{{
    config(
        materialized='view'
    )
}}

-- Capa bronze: lee tal cual los archivos JSON Lines generados por
-- ingestion/extract_bcrp.py (una fila por serie x periodo, sin tipar,
-- sin parsear fechas). No se aplica ninguna regla de negocio aquí.
--
-- DESARROLLO LOCAL (target=dev/duckdb):
--   lee directo los .jsonl locales con read_json_auto().
--
-- PRODUCCION (target=azure/PostgreSQL):
--   lee de una tabla real (esquema "bronze") cargada previamente por
--   ingestion/load_bronze_postgres.py -- ver sources.yml y README sección 5.

{% if target.type == 'duckdb' %}

select
    series_code,
    series_name,
    period_name,
    value_raw,
    extracted_at
from read_json_auto('{{ var("bronze_path", "../data/bronze/*.jsonl") }}')

{% else %}

select
    series_code,
    series_name,
    period_name,
    value_raw,
    extracted_at
from {{ source('bronze_bcrp', 'raw_series_bcrp') }}

{% endif %}
