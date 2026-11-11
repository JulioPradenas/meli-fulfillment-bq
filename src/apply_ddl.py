#!/usr/bin/env python3
"""
Meli Fulfillment — Paso 2: crear dataset meli_bronze y reemplazar tablas.

Uso (Mac, ADC, sin JSON de service account):
  export GCP_PROJECT=meli-fulfillment-jp
  python src/apply_ddl.py --dry-run
  python src/apply_ddl.py

Sandbox sin facturación:
  - Solo DDL. CREATE OR REPLACE TABLE (schema vacío). Cero ALTER, cero DML.
  - Expiración de tabla 60 días. default_partition_expiration_ms = 60 días
    para cuando silver/gold partizione.
  - Location US.
  - Idempotente en el sentido de `make run`: reemplaza el shape y la carga
    posterior vuelve a llenar. No conserva filas entre corridas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bq_env import (
    DATASET,
    EXPIRATION_DAYS,
    EXPIRATION_MS,
    LOCATION,
    NOTICE,
    ROOT,
    build_client,
    load_project_id,
)

SQL_PATH = ROOT / "sql" / "ddl_bronze.sql"


def split_statements(sql: str) -> list[str]:
    """Corta el archivo en statements. Ignora líneas de comentario `--`."""
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
    trailing = "\n".join(buf).strip()
    if trailing:
        raise ValueError("DDL con statement sin ';' final")
    return statements


def ensure_dataset(
    client,
    project_id: str,
    dataset_id: str = DATASET,
    description: str | None = None,
) -> str:
    """
    Crea el dataset en US si no existe. Si existe en otra location, aborta.
    Fija expiración de tablas y de particiones en 60 días (API, no DML).
    """
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    ref = f"{project_id}.{dataset_id}"
    if description is None and dataset_id == DATASET:
        description = (
            f"{NOTICE} Bronze sandbox. Tablas y particiones expiran a los "
            f"{EXPIRATION_DAYS} días. make run reconstruye desde cero."
        )
    elif description is None:
        description = (
            f"{NOTICE} {dataset_id}. Tablas y particiones expiran a los "
            f"{EXPIRATION_DAYS} días. make run reconstruye desde cero."
        )
    try:
        existing = client.get_dataset(ref)
    except NotFound:
        dataset = bigquery.Dataset(ref)
        dataset.location = LOCATION
        dataset.default_table_expiration_ms = EXPIRATION_MS
        dataset.default_partition_expiration_ms = EXPIRATION_MS
        dataset.description = description
        client.create_dataset(dataset)
        return "created"

    location = str(existing.location or "").upper()
    if location != LOCATION:
        raise SystemExit(
            f"El dataset {ref} ya existe en location {existing.location}, no en {LOCATION}. "
            "BigQuery no cambia la location de un dataset. Bórralo a mano o usa otro nombre."
        )
    existing.default_table_expiration_ms = EXPIRATION_MS
    existing.default_partition_expiration_ms = EXPIRATION_MS
    client.update_dataset(
        existing,
        ["default_table_expiration_ms", "default_partition_expiration_ms"],
    )
    return "updated"


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    sql_path: Path = SQL_PATH,
) -> int:
    if not sql_path.is_file():
        print(f"No está el DDL: {sql_path}", file=sys.stderr)
        return 1
    sql = sql_path.read_text(encoding="utf-8")
    statements = split_statements(sql)
    print(f"ddl={sql_path}")
    print(f"location={LOCATION}")
    print(f"dataset={DATASET}")
    print(f"expiration_days={EXPIRATION_DAYS}")
    print(f"statements={len(statements)}")
    print(f"dry_run={dry_run}")
    if dry_run:
        for stmt in statements:
            first = stmt.splitlines()[0]
            print(f"  would_run  {first}")
        print("dry-run: no se creó dataset ni se ejecutó DDL.")
        return 0

    project = project_id or load_project_id()
    print(f"project={project}")
    bq = client if client is not None else build_client(project)
    action = ensure_dataset(bq, project)
    print(f"  dataset {action}  {project}.{DATASET}")
    for stmt in statements:
        job = bq.query(stmt, location=LOCATION)
        job.result()
        first = stmt.splitlines()[0]
        print(f"  replaced  {first}")
    print(
        f"OK: {DATASET} listo (CREATE OR REPLACE, NULLABLE, expira a los {EXPIRATION_DAYS} días)."
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea meli_bronze y reemplaza las tablas con sql/ddl_bronze.sql."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el DDL. No llama a BigQuery.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
