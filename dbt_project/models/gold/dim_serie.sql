{{ config(materialized='table') }}

-- Dimension de series economicas: catalogo de indicadores presentes en el
-- pipeline, con su nombre oficial tal como lo reporta el API del BCRP.

select distinct
    series_code,
    series_name
from {{ ref('int_bcrp_series_cleaned') }}
