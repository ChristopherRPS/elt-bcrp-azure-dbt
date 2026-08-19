"""
Extrae series estadisticas del API publico del BCRP (Banco Central de Reserva del Peru)
y las aterriza en la capa bronze del data lake, en formato JSON Lines (una fila =
un valor de una serie en un periodo), listo para ser leido como tabla externa
en Synapse/ADLS o directamente por DuckDB en desarrollo local.

Uso:
    python extract_bcrp.py --series PN01246PM,PN00027MM,PN01364PM --fecha-ini 2015-1 --fecha-fin 2026-8

Documentacion del API: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api

Codigos de serie usados por defecto en este proyecto (catalogo BCRP verificado):
    PN01246PM -> Tipo de Cambio Nominal Promedio (S/ por US$)
    PN00027MM -> Reservas Internacionales Netas (millones US$)
    PN01364PM -> Indice de Precios al Consumidor - Lima Metropolitana (variacion % mensual)
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv(
    "BCRP_API_BASE_URL",
    "https://estadisticas.bcrp.gob.pe/estadisticas/series/api",
)

# Catalogo de series usadas en este proyecto. Se usa solo como referencia/fallback;
# el nombre "oficial" de cada serie siempre se toma de config.series en la respuesta
# del API, que es la fuente de verdad.
SERIES_BCRP = {
    "PN01246PM": {
        "nombre": "Tipo de Cambio Nominal Promedio (S/ por US$)",
        "unidad": "soles por dolar",
    },
    "PN00027MM": {
        "nombre": "Reservas Internacionales Netas (millones US$)",
        "unidad": "millones de US$",
    },
    "PN01364PM": {
        "nombre": "Indice de Precios al Consumidor (variacion % mensual)",
        "unidad": "% variacion mensual",
    },
}

LOCAL_BRONZE_PATH = Path(__file__).resolve().parents[1] / "data" / "bronze"


def build_url(series_codes: list[str], fecha_ini: str, fecha_fin: str) -> str:
    codigos = "-".join(series_codes)
    return f"{BASE_URL}/{codigos}/json/{fecha_ini}/{fecha_fin}/"


def extract(series_codes: list[str], fecha_ini: str, fecha_fin: str) -> dict:
    """Llama al API del BCRP y devuelve el payload crudo (dict)."""
    url = build_url(series_codes, fecha_ini, fecha_fin)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten(payload: dict, series_codes: list[str]) -> list[dict]:
    """
    Convierte la respuesta anidada del API del BCRP (una fila por periodo, con
    un array de valores paralelo a las series solicitadas) en filas "largas":
    una fila por (serie, periodo). Esto es lo que se escribe en bronze -- ya
    no es el JSON tal cual del API, pero sigue siendo dato crudo sin ninguna
    regla de negocio aplicada (sin tipar, sin parsear fechas).
    """
    extracted_at = datetime.now(timezone.utc).isoformat()
    series_meta = payload.get("config", {}).get("series", [])

    rows = []
    for period in payload.get("periods", []):
        period_name = period.get("name")
        values = period.get("values", [])
        for idx, series_code in enumerate(series_codes):
            if idx >= len(values):
                continue
            series_name = (
                series_meta[idx]["name"] if idx < len(series_meta) else series_code
            )
            rows.append(
                {
                    "series_code": series_code,
                    "series_name": series_name,
                    "period_name": period_name,
                    "value_raw": values[idx],
                    "extracted_at": extracted_at,
                }
            )
    return rows


def save_bronze(rows: list[dict], series_codes: list[str]) -> Path:
    """Guarda las filas planas como JSON Lines (un objeto JSON por linea)."""
    LOCAL_BRONZE_PATH.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"bcrp_{'_'.join(series_codes)}_{ts}.jsonl"
    out_path = LOCAL_BRONZE_PATH / filename
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out_path


def upload_to_adls(local_path: Path) -> str | None:
    """
    Sube una copia del archivo bronze a Azure Data Lake Storage Gen2, como
    landing zone versionada del dato crudo -- ademas de la copia local en
    data/bronze/, que sigue siendo la que usan dbt en dev/DuckDB y
    load_bronze_postgres.py para la carga a Postgres.

    Solo se ejecuta si estan configuradas las credenciales de Storage
    (AZURE_STORAGE_ACCOUNT_NAME / AZURE_STORAGE_ACCOUNT_KEY, ver
    .env.example, valores desde `terraform output`). En desarrollo local
    (Fase 1) estas variables no existen y esta funcion no hace nada -- asi
    el flujo local con DuckDB sigue sin depender de Azure para nada.
    """
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    container = os.getenv("AZURE_STORAGE_CONTAINER_BRONZE", "bronze")

    if not account_name or not account_key:
        return None

    # Import diferido: azure-storage-file-datalake solo esta en
    # requirements-azure.txt (Fase 2), no en requirements-dev.txt (Fase 1),
    # para no forzar esa dependencia en el flujo 100% local.
    from azure.storage.filedatalake import DataLakeServiceClient

    service_client = DataLakeServiceClient(
        account_url=f"https://{account_name}.dfs.core.windows.net",
        credential=account_key,
    )
    file_system_client = service_client.get_file_system_client(file_system=container)
    file_client = file_system_client.get_file_client(local_path.name)

    with open(local_path, "rb") as f:
        data = f.read()
    file_client.upload_data(data, overwrite=True)

    return f"abfss://{container}@{account_name}.dfs.core.windows.net/{local_path.name}"


def main():
    parser = argparse.ArgumentParser(description="Extrae series del API del BCRP")
    parser.add_argument(
        "--series",
        default=",".join(SERIES_BCRP.keys()),
        help="Codigos de series separados por coma, ej: PN01246PM,PN00027MM,PN01364PM",
    )
    parser.add_argument("--fecha-ini", required=True, help="Formato AAAA-M, ej: 2015-1")
    parser.add_argument("--fecha-fin", required=True, help="Formato AAAA-M, ej: 2026-8")
    args = parser.parse_args()

    series_codes = [s.strip() for s in args.series.split(",")]
    payload = extract(series_codes, args.fecha_ini, args.fecha_fin)
    rows = flatten(payload, series_codes)
    out_path = save_bronze(rows, series_codes)

    print(f"OK: {len(rows)} filas (series x periodos) extraidas")
    print(f"Guardado en: {out_path}")

    adls_uri = upload_to_adls(out_path)
    if adls_uri:
        print(f"Tambien subido a ADLS Gen2 (landing zone): {adls_uri}")


if __name__ == "__main__":
    main()
