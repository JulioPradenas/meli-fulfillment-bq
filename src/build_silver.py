#!/usr/bin/env python3
"""
Meli Fulfillment — Paso 3: bronze → silver + cuarentena.

Uso (Mac, ADC):
  export GCP_PROJECT=meli-fulfillment-jp
  python src/build_silver.py --dry-run
  python src/build_silver.py

Sandbox: solo CREATE OR REPLACE TABLE ... AS SELECT. Sin DML, sin streaming,
sin ALTER. Cada tabla expira a los 60 días. make run reemplaza todo.
"""

from __future__ import annotations

import sys
from pathlib import Path

from apply_ddl import ensure_dataset, split_statements
from bq_env import (
    EXPIRATION_DAYS,
    LOCATION,
    NOTICE,
    ROOT,
    SILVER_DATASET,
    build_client,
    load_project_id,
)
from silver_rules import SPECS, render_sql, sql_filename

SQL_DIR = ROOT / "sql" / "silver"


def sql_files() -> list[Path]:
    paths = []
    for index, spec in enumerate(SPECS, start=1):
        paths.append(SQL_DIR / sql_filename(spec, index))
    return paths


def run(*, dry_run: bool = False, project_id: str | None = None, client=None) -> int:
    files = sql_files()
    missing = [path for path in files if not path.is_file()]
    if missing:
        print("Faltan SQL de silver:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1
    print(f"location={LOCATION}")
    print(f"dataset={SILVER_DATASET}")
    print(f"expiration_days={EXPIRATION_DAYS}")
    print(f"dry_run={dry_run}")
    statements: list[tuple[Path, str]] = []
    for path in files:
        for stmt in split_statements(path.read_text(encoding="utf-8")):
            statements.append((path, stmt))
    print(f"statements={len(statements)}")
    if dry_run:
        for path, stmt in statements:
            print(f"  would_run  {path.name}  {stmt.splitlines()[0]}")
        print("dry-run: no se creó meli_silver ni se ejecutó SQL.")
        return 0

    project = project_id or load_project_id()
    print(f"project={project}")
    bq = client if client is not None else build_client(project)
    action = ensure_dataset(
        bq,
        project,
        SILVER_DATASET,
        description=(
            f"{NOTICE} Silver + cuarentena. Tablas y particiones expiran a los "
            f"{EXPIRATION_DAYS} días. make run reconstruye desde cero."
        ),
    )
    print(f"  dataset {action}  {project}.{SILVER_DATASET}")
    for path, stmt in statements:
        job = bq.query(stmt, location=LOCATION)
        job.result()
        print(f"  replaced  {path.name}  {stmt.splitlines()[0]}")
    print(f"OK: {SILVER_DATASET} reconstruido (CREATE OR REPLACE AS SELECT).")
    return 0


def write_sql_files() -> None:
    """Regenera sql/silver desde el spec. Lo usa el desarrollador, no make run."""
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    for index, spec in enumerate(SPECS, start=1):
        path = SQL_DIR / sql_filename(spec, index)
        path.write_text(render_sql(spec), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Construye meli_silver desde meli_bronze.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el SQL. No llama a BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
