"""Proyecto, location y expiración del lab. Sin default de GCP_PROJECT."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Sandbox sin facturación. US es la location de este proyecto (datos sintéticos,
# sin requisito de residencia). No hay motivo para fijar southamerica-west1.
LOCATION = "US"
DATASET = "meli_bronze"
SILVER_DATASET = "meli_silver"
GOLD_DATASET = "meli_gold"
EXPIRATION_DAYS = 60
EXPIRATION_MS = EXPIRATION_DAYS * 24 * 60 * 60 * 1000

NOTICE = "Lab de portafolio. Marca con fines ilustrativos."


def _load_dotenv_file(path: Path) -> None:
    """Carga KEY=VALUE de un .env local. No pisa variables ya exportadas. No loguea valores."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_project_id() -> str:
    """
    Lee GCP_PROJECT. No hay proyecto por defecto: si falta, termina con un mensaje claro.

    Acepta un `.env` en la raíz del repo (no se commitea). No lee `.env.example`
    para no convertir un ejemplo en default silencioso.
    """
    _load_dotenv_file(ROOT / ".env")
    project = os.environ.get("GCP_PROJECT", "").strip()
    if not project:
        raise SystemExit(
            "Falta GCP_PROJECT. Este script no tiene proyecto por defecto.\n"
            "En la Mac, con Application Default Credentials:\n"
            "  gcloud auth application-default login\n"
            "  export GCP_PROJECT=meli-fulfillment-jp\n"
            "  make run"
        )
    return project


def build_client(project_id: str):
    """Cliente BigQuery con ADC. Nunca lee un JSON de service account."""
    from google.cloud import bigquery

    return bigquery.Client(project=project_id, location=LOCATION)
