#!/usr/bin/env python3
"""
Compara conteos: manifest vs CSV vs (si no es dry-run) num_rows de meli_bronze.

`make run` termina aquí. Imprime una tabla y OK o FAIL.
Dry-run no consulta BigQuery: exige manifest == csv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bq_env import DATASET, LOCATION, ROOT, build_client, load_project_id
from contract import TABLE_ORDER
from csv_io import count_data_rows, csv_path

MANIFEST_PATH = ROOT / "data" / "manifest.json"
RAW_DIR = ROOT / "data" / "raw"


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    if not path.is_file():
        raise SystemExit(f"No está el manifest: {path}. Corre `make data` primero.")
    return json.loads(path.read_text(encoding="utf-8"))


def csv_counts(raw_dir: Path = RAW_DIR) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        path = csv_path(raw_dir, table)
        if not path.is_file():
            raise SystemExit(f"Falta el CSV {path}. Corre `make data` primero.")
        counts[table] = count_data_rows(path)
    return counts


def bq_counts(client, project_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        ref = f"{project_id}.{DATASET}.{table}"
        counts[table] = int(client.get_table(ref).num_rows or 0)
    return counts


def render_report(
    manifest_counts: dict[str, int],
    csv: dict[str, int],
    bq: dict[str, int] | None,
) -> tuple[str, bool]:
    header = f"{'tabla':<22} {'manifest':>10} {'csv':>10} {'bq':>10}  resultado"
    lines = [header, "-" * len(header)]
    ok = True
    for table in TABLE_ORDER:
        manifest_n = int(manifest_counts[table])
        csv_n = int(csv[table])
        if bq is None:
            good = manifest_n == csv_n
            bq_cell = "—"
        else:
            bq_n = int(bq[table])
            good = manifest_n == csv_n == bq_n
            bq_cell = f"{bq_n:d}"
        if not good:
            ok = False
        lines.append(
            f"{table:<22} {manifest_n:10d} {csv_n:10d} {bq_cell:>10}  {'OK' if good else 'FAIL'}"
        )
    if bq is None:
        lines.append("RESULTADO: " + ("OK" if ok else "FAIL") + " (dry-run, sin BigQuery)")
    else:
        lines.append("RESULTADO: " + ("OK" if ok else "FAIL"))
    return "\n".join(lines), ok


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    manifest_path: Path = MANIFEST_PATH,
    raw_dir: Path = RAW_DIR,
) -> int:
    manifest = load_manifest(manifest_path)
    manifest_counts = manifest["row_counts"]
    csv = csv_counts(raw_dir)
    bq = None
    if not dry_run:
        project = project_id or load_project_id()
        print(f"project={project}")
        print(f"location={LOCATION}")
        bq_client = client if client is not None else build_client(project)
        bq = bq_counts(bq_client, project)
    else:
        print(f"location={LOCATION}")
        print("dry_run=True")
    report, ok = render_report(manifest_counts, csv, bq)
    print(report)
    if not ok:
        print("VERIFY FAILED: conteos distintos.", file=sys.stderr)
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara row_counts del manifest con los CSV y con meli_bronze."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo manifest vs CSV. No consulta BigQuery.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
