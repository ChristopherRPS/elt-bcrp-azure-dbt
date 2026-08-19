"""
DAG de Airflow para orquestar el pipeline ELT de indicadores BCRP.

Alternativa a usar Azure Data Factory como orquestador nativo -- este DAG
existe para quien prefiera mantener Airflow como orquestador comun entre
todos los proyectos del portafolio (mismo patron que churn-telecom).

Flujo: extraccion + flatten (bronze local) -> upload a ADLS Gen2 -> dbt run (silver+gold) -> dbt test
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Permite importar ingestion/extract_bcrp.py cuando el DAG corre dentro del
# contenedor de Airflow (ver volumenes montados en docker-compose.yml).
sys.path.insert(0, "/opt/airflow")

default_args = {
    "owner": "christopher",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

SERIES_A_EXTRAER = ["PN01246PM", "PN00027MM", "PN01364PM"]  # tipo de cambio, RIN, IPC


def extraer_bcrp(**context):
    from ingestion.extract_bcrp import extract, flatten, save_bronze

    fecha_ini = context.get("params", {}).get("fecha_ini", "2015-1")
    fecha_fin = datetime.now().strftime("%Y-%-m")

    payload = extract(SERIES_A_EXTRAER, fecha_ini, fecha_fin)
    rows = flatten(payload, SERIES_A_EXTRAER)
    out_path = save_bronze(rows, SERIES_A_EXTRAER)

    context["ti"].xcom_push(key="bronze_file", value=str(out_path))
    print(f"OK: {len(rows)} filas extraidas -> {out_path}")


def subir_a_adls(**context):
    from ingestion.extract_bcrp import upload_to_adls

    bronze_file = context["ti"].xcom_pull(key="bronze_file")
    adls_uri = upload_to_adls(Path(bronze_file))
    if adls_uri:
        print(f"OK: subido a {adls_uri}")
    else:
        print(
            "AVISO: AZURE_STORAGE_ACCOUNT_NAME/AZURE_STORAGE_ACCOUNT_KEY no estan "
            "configurados en el entorno de Airflow (ver .env.example) -- se omite "
            "la subida a ADLS Gen2. dbt sigue funcionando igual, ya que lee el "
            "bronze desde el archivo local o desde Postgres, no desde ADLS."
        )


with DAG(
    dag_id="bcrp_elt_pipeline",
    description="ELT de indicadores economicos del BCRP hacia Azure Data Lake + dbt",
    default_args=default_args,
    schedule="@monthly",  # el BCRP publica la mayoria de series con frecuencia mensual
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bcrp", "azure", "elt", "portafolio"],
) as dag:

    extraer = PythonOperator(
        task_id="extraer_series_bcrp",
        python_callable=extraer_bcrp,
    )

    subir = PythonOperator(
        task_id="subir_bronze_a_adls",
        python_callable=subir_a_adls,
    )

    dbt_run = BashOperator(
        task_id="dbt_run_silver_gold",
        bash_command="cd /opt/airflow/dbt_project && DBT_PROFILES_DIR=. dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt_project && DBT_PROFILES_DIR=. dbt test",
    )

    extraer >> subir >> dbt_run >> dbt_test
