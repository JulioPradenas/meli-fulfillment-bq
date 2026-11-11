#!/usr/bin/env python3
"""
Reconcilia bronze = silver + cuarentena, motivos contra el manifest y 0 huérfanas.

Dry-run usa pandas sobre los CSV (sin BigQuery). La corrida real cuenta en
meli_bronze y meli_silver. Imprime una tabla y RESULTADO: OK o FALLA.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bq_env import LOCATION, ROOT, SILVER_DATASET, build_client, load_project_id
from csv_io import read_rows
from silver_rules import PRIORIDAD, SPECS, classify, resumen
from verify_bronze import RAW_DIR, load_manifest

BRONZE = "meli_bronze"


def _load_tables(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for spec in SPECS:
        path = raw_dir / f"{spec.name}.csv"
        if not path.is_file():
            raise SystemExit(f"Falta el CSV {path}. Corre `make data` primero.")
        tables[spec.name] = read_rows(path)
    return tables


def _observed_from_frames(tables: dict[str, list[dict[str, str]]]) -> dict:
    clasificado = classify(tables)
    summary = resumen(clasificado)
    bronze = {spec.name: len(tables[spec.name]) for spec in SPECS}
    huerfanas = sum(int(clasificado[spec.name]["huerfanas"]) for spec in SPECS)
    return {"bronze": bronze, "silver": summary, "huerfanas": huerfanas}


def _query_one(client, sql: str) -> list[dict]:
    job = client.query(sql, location=LOCATION)
    return [dict(row) for row in job.result()]


def _observed_from_bq(client, project: str) -> dict:
    bronze = {}
    tablas = {}
    huerfanas = 0
    for spec in SPECS:
        bq_n = int(
            _query_one(
                client,
                f"SELECT COUNT(*) AS n FROM `{project}.{BRONZE}.{spec.name}`",
            )[0]["n"]
        )
        silver_n = int(
            _query_one(
                client,
                f"SELECT COUNT(*) AS n FROM `{project}.{SILVER_DATASET}.{spec.name}`",
            )[0]["n"]
        )
        q_n = int(
            _query_one(
                client,
                f"SELECT COUNT(*) AS n FROM `{project}.{SILVER_DATASET}.q_{spec.name}`",
            )[0]["n"]
        )
        bronze[spec.name] = bq_n
        motivos = {motivo: 0 for motivo in PRIORIDAD}
        rows = _query_one(
            client,
            "SELECT motivo, COUNT(*) AS n "
            f"FROM `{project}.{SILVER_DATASET}.q_{spec.name}` "
            "GROUP BY motivo",
        )
        for row in rows:
            motivos[str(row["motivo"])] = int(row["n"])
        tablas[spec.name] = {
            "silver": silver_n,
            "cuarentena": q_n,
            "huerfanas": 0,
            "motivos": motivos,
        }
        for fk in spec.fks:
            where = (
                f"e.{fk.column} IS NOT NULL AND p.{fk.parent_column} IS NULL"
            )
            n = int(
                _query_one(
                    client,
                    "SELECT COUNT(*) AS n "
                    f"FROM `{project}.{SILVER_DATASET}.{spec.name}` e "
                    f"LEFT JOIN `{project}.{SILVER_DATASET}.{fk.parent}` p "
                    f"ON e.{fk.column} = p.{fk.parent_column} "
                    f"WHERE {where}",
                )[0]["n"]
            )
            huerfanas += n
    return {
        "bronze": bronze,
        "silver": {"prioridad": list(PRIORIDAD), "tablas": tablas},
        "huerfanas": huerfanas,
    }


def render_report(manifest: dict, observed: dict) -> tuple[str, bool]:
    esperado = manifest["silver"]["tablas"]
    lineas = [
        f"{'tabla':<22} {'bronze':>8} {'silver':>8} {'cuarentena':>12}  resultado"
    ]
    lineas.append("-" * len(lineas[0]))
    ok = True
    for spec in SPECS:
        name = spec.name
        bronze_n = int(observed["bronze"][name])
        silver_n = int(observed["silver"]["tablas"][name]["silver"])
        q_n = int(observed["silver"]["tablas"][name]["cuarentena"])
        manifest_bronze = int(manifest["row_counts"][name])
        manifest_silver = int(esperado[name]["silver"])
        manifest_q = int(esperado[name]["cuarentena"])
        good = (
            bronze_n == silver_n + q_n
            and bronze_n == manifest_bronze
            and silver_n == manifest_silver
            and q_n == manifest_q
        )
        if not good:
            ok = False
        lineas.append(
            f"{name:<22} {bronze_n:8d} {silver_n:8d} {q_n:12d}  {'OK' if good else 'FALLA'}"
        )
    lineas.append("")
    lineas.append(f"{'tabla':<22} {'motivo':<22} {'manifest':>8} {'observado':>10}  resultado")
    for spec in SPECS:
        name = spec.name
        for motivo in PRIORIDAD:
            want = int(esperado[name]["motivos"][motivo])
            got = int(observed["silver"]["tablas"][name]["motivos"].get(motivo, 0))
            if want == 0 and got == 0:
                continue
            good = want == got
            if not good:
                ok = False
            lineas.append(
                f"{name:<22} {motivo:<22} {want:8d} {got:10d}  {'OK' if good else 'FALLA'}"
            )
    huerfanas = int(observed["huerfanas"])
    if huerfanas != 0:
        ok = False
    lineas.append("")
    lineas.append(
        f"huerfanas_en_silver {huerfanas}  {'OK' if huerfanas == 0 else 'FALLA'}"
    )
    lineas.append("RESULTADO: " + ("OK" if ok else "FALLA"))
    return "\n".join(lineas), ok


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    manifest_path: Path | None = None,
    raw_dir: Path = RAW_DIR,
) -> int:
    manifest = load_manifest(manifest_path) if manifest_path else load_manifest()
    if "silver" not in manifest:
        raise SystemExit("El manifest no trae el bloque silver. Regenera con `make data`.")
    print(f"location={LOCATION}")
    print(f"dataset={SILVER_DATASET}")
    if dry_run:
        print("dry_run=True")
        observed = _observed_from_frames(_load_tables(raw_dir))
    else:
        project = project_id or load_project_id()
        print(f"project={project}")
        bq = client if client is not None else build_client(project)
        observed = _observed_from_bq(bq, project)
    report, ok = render_report(manifest, observed)
    print(report)
    if dry_run:
        print("(dry-run, sin BigQuery)")
    if not ok:
        print("VERIFY SILVER FALLA.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcilia bronze, silver y cuarentena contra el manifest."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Clasifica los CSV con pandas. No consulta BigQuery.",
    )
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
