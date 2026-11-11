#!/usr/bin/env python3
"""
Meli Fulfillment — Paso 2: load job CSV → meli_bronze (WRITE_TRUNCATE).

Uso (Mac, ADC):
  export GCP_PROJECT=meli-fulfillment-jp
  python src/load_bronze.py --dry-run
  python src/load_bronze.py

Sandbox:
  - load_table_from_file. No streaming inserts. No INSERT/UPDATE/DELETE/MERGE.
  - WRITE_TRUNCATE: re-run reemplaza filas. Junto con CREATE OR REPLACE,
    `make run` reconstruye desde cero.
  - Schema del job forzado a NULLABLE. REQUIRED rechazaba los nulos de las
    anomalías (lección KORA: 'Required column value is missing').
  - Location US. Proyecto solo desde GCP_PROJECT.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from bq_env import DATASET, LOCATION, ROOT, build_client, load_project_id
from contract import TABLE_ORDER, TABLES, columns
from csv_io import count_data_rows, csv_path, read_header

RAW_DIR = ROOT / "data" / "raw"


@dataclass(frozen=True)
class LoadResult:
    table_id: str
    action: str  # loaded | would_load | error | mismatch
    csv_rows: int = 0
    bq_rows: int | None = None
    detail: str = ""


def schema_as_nullable(fields: list) -> list:
    """Reconstruye el schema con mode NULLABLE en todos los campos."""
    from google.cloud import bigquery

    out = []
    for field in fields:
        out.append(
            bigquery.SchemaField(
                name=field.name,
                field_type=field.field_type,
                mode="NULLABLE",
                description=getattr(field, "description", None) or None,
            )
        )
    return out


def contract_schema(table_id: str) -> list:
    from google.cloud import bigquery

    return [
        bigquery.SchemaField(name, field_type, mode="NULLABLE")
        for name, field_type in TABLES[table_id]
    ]


def build_load_job_config(table_id: str):
    """
    LoadJobConfig: schema explícito NULLABLE, WRITE_TRUNCATE, skip header,
    sin autodetect. No ALLOW_FIELD_RELAXATION: el schema del job ya es NULLABLE
    y el DDL se recrea con CREATE OR REPLACE (no ALTER).
    """
    from google.cloud import bigquery

    return bigquery.LoadJobConfig(
        schema=schema_as_nullable(contract_schema(table_id)),
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=False,
    )


def validate_header(path: Path, table_id: str) -> tuple[list[str], int]:
    header = read_header(path)
    expected = columns(table_id)
    if header != expected:
        raise ValueError(
            f"Header mismatch en {path.name}:\n  csv={header}\n  contrato={expected}"
        )
    return header, count_data_rows(path)


def load_one_table(
    client,
    *,
    project_id: str,
    table_id: str,
    raw_dir: Path = RAW_DIR,
    dry_run: bool = False,
) -> LoadResult:
    path = csv_path(raw_dir, table_id)
    if not path.is_file():
        return LoadResult(table_id=table_id, action="error", detail=f"CSV missing: {path}")
    try:
        _header, csv_rows = validate_header(path, table_id)
    except ValueError as exc:
        return LoadResult(table_id=table_id, action="error", detail=str(exc))

    if dry_run:
        return LoadResult(
            table_id=table_id,
            action="would_load",
            csv_rows=csv_rows,
            detail="header_ok",
        )

    table_ref = f"{project_id}.{DATASET}.{table_id}"
    job_config = build_load_job_config(table_id)
    try:
        with path.open("rb") as fh:
            job = client.load_table_from_file(
                fh,
                table_ref,
                job_config=job_config,
                location=LOCATION,
            )
            job.result()
        bq_rows = int(client.get_table(table_ref).num_rows or 0)
        if bq_rows != csv_rows:
            return LoadResult(
                table_id=table_id,
                action="mismatch",
                csv_rows=csv_rows,
                bq_rows=bq_rows,
                detail=f"Row count mismatch {table_id}: csv={csv_rows} bq={bq_rows}",
            )
    except Exception as exc:  # noqa: BLE001
        return LoadResult(
            table_id=table_id,
            action="error",
            csv_rows=csv_rows,
            detail=str(exc),
        )
    return LoadResult(
        table_id=table_id,
        action="loaded",
        csv_rows=csv_rows,
        bq_rows=bq_rows,
        detail="ok",
    )


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    raw_dir: Path = RAW_DIR,
    tables: tuple[str, ...] = TABLE_ORDER,
) -> int:
    print(f"location={LOCATION}")
    print(f"dataset={DATASET}")
    print(f"dry_run={dry_run}")
    print(f"raw_dir={raw_dir}")
    project = ""
    bq = client
    if not dry_run:
        project = project_id or load_project_id()
        print(f"project={project}")
        bq = client if client is not None else build_client(project)

    failures = 0
    for table_id in tables:
        result = load_one_table(
            bq,
            project_id=project,
            table_id=table_id,
            raw_dir=raw_dir,
            dry_run=dry_run,
        )
        bq_part = "" if result.bq_rows is None else f" bq_rows={result.bq_rows}"
        print(
            f"  {result.action:12}  {DATASET}.{table_id}  "
            f"csv_rows={result.csv_rows}{bq_part}  {result.detail}"
        )
        if result.action in {"error", "mismatch"}:
            failures += 1
    if failures:
        print("LOAD FAILED.", file=sys.stderr)
        return 1
    if dry_run:
        print("dry-run: headers y filas validados; no se ejecutó load.")
        return 0
    print("OK: meli_bronze cargado (load jobs WRITE_TRUNCATE, schema NULLABLE).")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga data/raw/*.csv en meli_bronze con load jobs WRITE_TRUNCATE."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida headers contra el contrato y cuenta filas. No llama a BigQuery.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
