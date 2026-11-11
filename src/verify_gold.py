#!/usr/bin/env python3
"""
Chequea f_envios contra silver, las dimensiones y la historia del manifest.

Dry-run arma el gold en pandas desde los CSV. La corrida real lee meli_gold.
Imprime una tabla y RESULTADO: OK o FALLA.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bq_env import GOLD_DATASET, LOCATION, build_client, load_project_id
from csv_io import read_rows
from gold_rules import STORY, build_gold, chequeos
from silver_rules import SPECS

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _load_tables(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for spec in SPECS:
        path = raw_dir / f"{spec.name}.csv"
        if not path.is_file():
            raise SystemExit(f"Falta el CSV {path}. Corre `make data` primero.")
        tables[spec.name] = read_rows(path)
    return tables


def _query_one(client, sql: str) -> list[dict]:
    job = client.query(sql, location=LOCATION)
    return [dict(row) for row in job.result()]


def _count(client, project: str, table: str) -> int:
    return int(
        _query_one(client, f"SELECT COUNT(*) AS n FROM `{project}.{GOLD_DATASET}.{table}`")[0]["n"]
    )


def chequeos_bq(client, project: str) -> list[tuple[str, object, object, bool]]:
    silver_n = int(
        _query_one(client, f"SELECT COUNT(*) AS n FROM `{project}.meli_silver.envios`")[0]["n"]
    )
    distintos = _query_one(
        client,
        "SELECT COUNT(*) AS n, COUNT(DISTINCT envio_id) AS u "
        f"FROM `{project}.{GOLD_DATASET}.f_envios`",
    )[0]
    n_fact = int(distintos["n"])
    n_unique = int(distintos["u"])

    def orphans(sql: str) -> int:
        return int(_query_one(client, sql)[0]["n"])

    huerfanas = 0
    huerfanas += orphans(
        "SELECT COUNT(*) AS n FROM "
        f"`{project}.{GOLD_DATASET}.f_envios` f "
        f"LEFT JOIN `{project}.{GOLD_DATASET}.d_seller` d ON f.seller_id = d.seller_id "
        "WHERE d.seller_id IS NULL"
    )
    huerfanas += orphans(
        "SELECT COUNT(*) AS n FROM "
        f"`{project}.{GOLD_DATASET}.f_envios` f "
        f"LEFT JOIN `{project}.{GOLD_DATASET}.d_geografia` d ON f.comuna_id = d.comuna_id "
        "WHERE d.comuna_id IS NULL"
    )
    huerfanas += orphans(
        "SELECT COUNT(*) AS n FROM "
        f"`{project}.{GOLD_DATASET}.f_envios` f "
        f"LEFT JOIN `{project}.{GOLD_DATASET}.d_geografia` d ON f.region_id = d.region_id "
        "WHERE d.region_id IS NULL"
    )
    huerfanas += orphans(
        "SELECT COUNT(*) AS n FROM "
        f"`{project}.{GOLD_DATASET}.f_envios` f "
        f"LEFT JOIN `{project}.{GOLD_DATASET}.d_centro_fulfillment` d ON f.fc_id = d.fc_id "
        "WHERE f.fc_id IS NOT NULL AND d.fc_id IS NULL"
    )
    huerfanas += orphans(
        "SELECT COUNT(*) AS n FROM "
        f"`{project}.{GOLD_DATASET}.f_envios` f "
        f"LEFT JOIN `{project}.{GOLD_DATASET}.d_carrier` d ON f.carrier_id = d.carrier_id "
        "WHERE f.carrier_id IS NOT NULL AND d.carrier_id IS NULL"
    )
    for column in ("fecha_creacion", "fecha_promesa"):
        huerfanas += orphans(
            "SELECT COUNT(*) AS n FROM "
            f"`{project}.{GOLD_DATASET}.f_envios` f "
            f"LEFT JOIN `{project}.{GOLD_DATASET}.d_fecha` d ON f.{column} = d.fecha "
            "WHERE d.fecha IS NULL"
        )
    for column in ("fecha_despacho", "fecha_entrega"):
        huerfanas += orphans(
            "SELECT COUNT(*) AS n FROM "
            f"`{project}.{GOLD_DATASET}.f_envios` f "
            f"LEFT JOIN `{project}.{GOLD_DATASET}.d_fecha` d ON f.{column} = d.fecha "
            f"WHERE f.{column} IS NOT NULL AND d.fecha IS NULL"
        )
    flags = int(
        _query_one(
            client,
            "SELECT COUNT(*) AS n FROM "
            f"`{project}.{GOLD_DATASET}.f_envios` "
            "WHERE es_a_tiempo + es_atrasado != es_entregado",
        )[0]["n"]
    )

    def late(where: str) -> tuple[float, int]:
        row = _query_one(
            client,
            "SELECT SUM(es_atrasado) AS atraso, SUM(es_entregado) AS n FROM "
            f"`{project}.{GOLD_DATASET}.f_envios` WHERE {where}",
        )[0]
        n = int(row["n"] or 0)
        rate = (int(row["atraso"] or 0) / n) if n else 0.0
        return round(rate, 4), n

    rm_rate, rm_n = late("region_id = 'RM'")
    ext_rate, ext_n = late("region_id IN ('AP', 'AN', 'AI', 'MA')")
    andes, _ = late("carrier_id = 'CAR-ANDES'")
    sur, _ = late("carrier_id = 'CAR-SUR'")
    sin_stock = int(
        _query_one(
            client,
            "SELECT COUNT(*) AS n FROM "
            f"`{project}.{GOLD_DATASET}.f_envios` "
            "WHERE es_cancelado_logistica = 1 AND motivo_cancelacion_logistica = 'sin_stock_fc'",
        )[0]["n"]
    )
    rows = [
        ("f_envios = silver.envios", silver_n, n_fact, silver_n == n_fact),
        ("envio_id unicos", n_fact, n_unique, n_fact == n_unique),
        ("huerfanas", 0, huerfanas, huerfanas == 0),
        ("es_a_tiempo + es_atrasado = es_entregado", 0, flags, flags == 0),
        ("atrasados RM", STORY["rm_atrasados"], rm_rate, STORY["rm_atrasados"] == rm_rate),
        ("n entregados RM", STORY["rm_n"], rm_n, STORY["rm_n"] == rm_n),
        ("atrasados extremos", STORY["extremos_atrasados"], ext_rate, STORY["extremos_atrasados"] == ext_rate),
        ("n entregados extremos", STORY["extremos_n"], ext_n, STORY["extremos_n"] == ext_n),
        ("atrasados CAR-ANDES", STORY["andes_atrasados"], andes, STORY["andes_atrasados"] == andes),
        ("atrasados CAR-SUR", STORY["sur_atrasados"], sur, STORY["sur_atrasados"] == sur),
        ("sin_stock_fc", STORY["sin_stock_fc"], sin_stock, STORY["sin_stock_fc"] == sin_stock),
    ]
    return rows


def render_report(rows: list[tuple[str, object, object, bool]]) -> tuple[str, bool]:
    header = f"{'chequeo':<42} {'esperado':>12} {'observado':>12}  resultado"
    lines = [header, "-" * len(header)]
    ok = True
    for nombre, esperado, observado, good in rows:
        if not good:
            ok = False
        lines.append(f"{nombre:<42} {esperado!s:>12} {observado!s:>12}  {'OK' if good else 'FALLA'}")
    lines.append("RESULTADO: " + ("OK" if ok else "FALLA"))
    return "\n".join(lines), ok


def run(*, dry_run: bool = False, project_id: str | None = None, client=None, raw_dir: Path = RAW_DIR) -> int:
    print(f"location={LOCATION}")
    print(f"dataset={GOLD_DATASET}")
    if dry_run:
        print("dry_run=True")
        rows = chequeos(build_gold(_load_tables(raw_dir)))
    else:
        project = project_id or load_project_id()
        print(f"project={project}")
        bq = client if client is not None else build_client(project)
        rows = chequeos_bq(bq, project)
    report, ok = render_report(rows)
    print(report)
    if dry_run:
        print("(dry-run, sin BigQuery)")
    if not ok:
        print(
            "VERIFY GOLD FALLA. Si la historia no calza, no se ajusta el número: "
            "se explica la definición.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica meli_gold contra silver y la historia.")
    parser.add_argument("--dry-run", action="store_true", help="Arma el gold en pandas. No consulta BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
