#!/usr/bin/env python3
"""
Meli Fulfillment — Paso 4: silver → gold (estrella, sin partición).

Uso (Mac, ADC):
  export GCP_PROJECT=meli-fulfillment-jp
  python src/build_gold.py --dry-run
  python src/build_gold.py

Sandbox: solo CREATE OR REPLACE. Sin DML. f_envios va CLUSTER BY
region_id, carrier_id y sin PARTITION BY: una partición por fecha vencería
a los 60 días según esa fecha y borraría el horizonte 2026-05 a 2026-10.
"""

from __future__ import annotations

import sys
from pathlib import Path

from apply_ddl import ensure_dataset, split_statements
from bq_env import (
    EXPIRATION_DAYS,
    GOLD_DATASET,
    LOCATION,
    NOTICE,
    ROOT,
    build_client,
    load_project_id,
)

SQL_DIR = ROOT / "sql" / "gold"


def sql_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"))


def run(*, dry_run: bool = False, project_id: str | None = None, client=None) -> int:
    files = sql_files()
    if not files:
        print(f"No hay SQL en {SQL_DIR}", file=sys.stderr)
        return 1
    print(f"location={LOCATION}")
    print(f"dataset={GOLD_DATASET}")
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
        print("dry-run: no se creó meli_gold ni se ejecutó SQL.")
        return 0

    project = project_id or load_project_id()
    print(f"project={project}")
    bq = client if client is not None else build_client(project)
    action = ensure_dataset(
        bq,
        project,
        GOLD_DATASET,
        description=(
            f"{NOTICE} Gold estrella. Sin partición por fecha. "
            f"Tablas expiran a los {EXPIRATION_DAYS} días. make run reconstruye desde cero."
        ),
    )
    print(f"  dataset {action}  {project}.{GOLD_DATASET}")
    for path, stmt in statements:
        job = bq.query(stmt, location=LOCATION)
        job.result()
        print(f"  replaced  {path.name}  {stmt.splitlines()[0]}")
    print(f"OK: {GOLD_DATASET} reconstruido (CREATE OR REPLACE, cluster sin partición).")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Construye meli_gold desde meli_silver.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el SQL. No llama a BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
