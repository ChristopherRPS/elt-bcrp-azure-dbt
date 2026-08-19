"""
Carga los archivos .jsonl de data/bronze/ (generados por extract_bcrp.py) a
una tabla real en Azure Database for PostgreSQL: bronze.raw_series_bcrp.

Es el paso equivalente a "subir a ADLS Gen2" que se documentó originalmente
para el flujo con Data Factory/Synapse -- con PostgreSQL como warehouse, el
equivalente más simple es cargar directo a una tabla de staging en el mismo
Postgres, en su propio esquema "bronze" (separado de los esquemas gold_* que
genera dbt).

Uso:
    python ingestion/load_bronze_postgres.py

Requiere las mismas variables de entorno que dbt (ver .env.example):
    DBT_PG_HOST, DBT_PG_USER, DBT_PG_PASSWORD, DBT_PG_DATABASE
"""
import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

BRONZE_DIR = Path(__file__).resolve().parents[1] / "data" / "bronze"

DDL = """
create schema if not exists bronze;

create table if not exists bronze.raw_series_bcrp (
    series_code   text,
    series_name   text,
    period_name   text,
    value_raw     text,
    extracted_at  timestamptz
);
"""

INSERT = """
insert into bronze.raw_series_bcrp (series_code, series_name, period_name, value_raw, extracted_at)
values (%s, %s, %s, %s, %s)
"""


def load_rows():
    rows = []
    for path in sorted(BRONZE_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                rows.append(
                    (
                        r["series_code"],
                        r["series_name"],
                        r["period_name"],
                        r["value_raw"],
                        r["extracted_at"],
                    )
                )
    return rows


def main():
    conn_kwargs = dict(
        host=os.environ["DBT_PG_HOST"],
        port=5432,
        user=os.environ["DBT_PG_USER"],
        password=os.environ["DBT_PG_PASSWORD"],
        dbname=os.environ["DBT_PG_DATABASE"],
        sslmode="require",
    )

    rows = load_rows()
    if not rows:
        print(f"No se encontraron archivos .jsonl en {BRONZE_DIR}")
        return

    with psycopg2.connect(**conn_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            # Se trunca antes de cargar: cada corrida de este script sube el
            # estado completo de data/bronze/ tal cual esta en local. La
            # deduplicacion por extraccion mas reciente sigue pasando en el
            # modelo silver (int_bcrp_series_cleaned), igual que en local.
            cur.execute("truncate table bronze.raw_series_bcrp")
            cur.executemany(INSERT, rows)
        conn.commit()

    print(f"OK: {len(rows)} filas cargadas en bronze.raw_series_bcrp")


if __name__ == "__main__":
    main()
