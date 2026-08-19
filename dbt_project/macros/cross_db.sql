{#
  Pequeña macro para mantener los mismos archivos .sql funcionando tanto en
  DuckDB (target=dev) como en PostgreSQL (target=azure). DuckDB soporta
  try_cast() de forma nativa; PostgreSQL no lo tiene en el core, así que ahí
  se usa un CAST normal (los datos del BCRP ya vienen filtrados/limpios en
  este punto del pipeline, así que es seguro).
#}
{% macro safe_cast_double(column_name) %}
  {%- if target.type == 'duckdb' -%}
    try_cast({{ column_name }} as double)
  {%- else -%}
    cast({{ column_name }} as double precision)
  {%- endif -%}
{% endmacro %}
