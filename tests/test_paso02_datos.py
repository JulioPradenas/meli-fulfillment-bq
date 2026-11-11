"""Paso 2 — semilla estable, columnas y manifest = anomalías inyectadas. Sin GCP."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

import contract
import generate_data
from csv_io import csv_path, read_rows, write_table

ROOT = Path(__file__).resolve().parents[1]
TS_FMT = "%Y-%m-%d %H:%M:%S%z"

# El test repite las reglas. No llama al contador del generador.
SENTINELS = {
    "SEL-HUERFANO",
    "99999",
    "FC-HUERFANO",
    "CAR-HUERFANO",
    "ORD-HUERFANA",
    "ENV-HUERFANO",
    "REG-HUERFANA",
}
FK_COLS = {
    "comunas": ("region",),
    "centros_fulfillment": ("comuna_id",),
    "sellers": ("region_origen",),
    "ordenes": ("seller_id", "comuna_destino_id"),
    "envios": (
        "orden_id",
        "seller_id",
        "fc_id",
        "carrier_id",
        "comuna_destino_id",
    ),
    "eventos_tracking": ("envio_id", "fc_id", "carrier_id", "comuna_id"),
}
MOTIVOS = {
    "sin_stock_fc",
    "capacidad_fc",
    "dano_en_preparacion",
    "carrier_no_retira",
    "direccion_invalida",
    "extravio",
}


@pytest.fixture(scope="module")
def generated():
    return generate_data.generate(42)


def _scan(tables: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {}
    for table, rows in tables.items():
        cols = contract.columns(table)
        as_tuples = [tuple(row[col] for col in cols) for row in rows]
        dupes = sum(n - 1 for n in Counter(as_tuples).values() if n > 1)
        pk = contract.PRIMARY_KEY[table]
        clave = sum(1 for row in rows if row[pk] == "")
        fecha_col = contract.FECHA_NULA_COL.get(table)
        fecha = (
            sum(1 for row in rows if row[fecha_col] == "") if fecha_col else 0
        )
        fk = sum(
            1
            for row in rows
            if any(row.get(col, "") in SENTINELS for col in FK_COLS.get(table, ()))
        )
        found[table] = {
            "fk_huerfana": fk,
            "fecha_nula": fecha,
            "clave_nula": clave,
            "duplicado_exacto": dupes,
            "evento_fuera_de_orden": 0,
            "cast_fallido": sum(
                1 for row in rows if any(str(value).strip() == "NO-CAST" for value in row.values())
            ),
            "entrega_antes_despacho": 0,
        }

    if "envios" in tables:
        invertidas = 0
        for row in tables["envios"]:
            if not row["ts_entrega"] or not row["ts_despacho"]:
                continue
            try:
                entrega = datetime.strptime(row["ts_entrega"], TS_FMT)
                despacho_ts = datetime.strptime(row["ts_despacho"], TS_FMT)
            except ValueError:
                continue
            if entrega < despacho_ts:
                invertidas += 1
        found["envios"]["entrega_antes_despacho"] = invertidas

    despacho: dict[str, datetime] = {}
    for ev in tables["eventos_tracking"]:
        if ev["codigo_evento"] != "despachado" or not ev["ts_evento"]:
            continue
        try:
            ts = datetime.strptime(ev["ts_evento"], TS_FMT)
        except ValueError:
            continue
        prev = despacho.get(ev["envio_id"])
        if prev is None or ts < prev:
            despacho[ev["envio_id"]] = ts
    ooo = 0
    for ev in tables["eventos_tracking"]:
        if ev["codigo_evento"] != "entregado" or not ev["ts_evento"]:
            continue
        limite = despacho.get(ev["envio_id"])
        if limite is None:
            continue
        try:
            ts_evento = datetime.strptime(ev["ts_evento"], TS_FMT)
        except ValueError:
            continue
        if ts_evento < limite:
            ooo += 1
    found["eventos_tracking"]["evento_fuera_de_orden"] = ooo
    return found


def _clean_envios(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        eid = row["envio_id"]
        if re.fullmatch(r"ENV-\d{6}", eid) and eid not in seen:
            seen.add(eid)
            out.append(row)
    return out


def test_semilla_estable_dos_corridas():
    first = generate_data.generate(42)
    second = generate_data.generate(42)
    assert first.manifest == second.manifest
    for table in contract.TABLE_ORDER:
        cols = contract.columns(table)
        rows_a = [tuple(r[c] for c in cols) for r in first.tables[table]]
        rows_b = [tuple(r[c] for c in cols) for r in second.tables[table]]
        assert rows_a == rows_b


def test_csv_dos_escrituras_identicas(tmp_path: Path):
    gen_a = generate_data.generate(42)
    gen_b = generate_data.generate(42)
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    for folder, gen in ((dir_a, gen_a), (dir_b, gen_b)):
        folder.mkdir()
        for table in contract.TABLE_ORDER:
            write_table(csv_path(folder, table), table, gen.tables[table])
    for table in contract.TABLE_ORDER:
        assert csv_path(dir_a, table).read_bytes() == csv_path(dir_b, table).read_bytes()


def test_columnas_de_cada_csv(generated, tmp_path: Path):
    for table in contract.TABLE_ORDER:
        write_table(csv_path(tmp_path, table), table, generated.tables[table])
        rows = read_rows(csv_path(tmp_path, table))
        assert list(rows[0]) == contract.columns(table)
        assert len(rows) == generated.manifest["row_counts"][table]


def test_manifest_coincide_con_lo_inyectado(generated):
    scanned = _scan(generated.tables)
    assert scanned == generated.manifest["anomalies"]
    for table in contract.TABLE_ORDER:
        extra = sum(generated.manifest["anomalies"][table].values())
        assert generated.manifest["row_counts"][table] == (
            generated.manifest["clean_counts"][table] + extra
        )
    assert generated.manifest["clean_counts"]["envios"] == 32_000
    assert generated.manifest["row_counts"]["envios"] == 32_064
    assert generated.manifest["clean_counts"]["regiones"] == 16
    assert generated.manifest["horizon_start"] == "2026-05-01"
    assert generated.manifest["horizon_end"] == "2026-10-31"
    assert generated.manifest["seed"] == 42
    committed = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert committed == generated.manifest


def test_volumen_y_eventos_siguen_siendo_chicos(generated):
    events = generated.manifest["row_counts"]["eventos_tracking"]
    assert 100_000 <= events <= 250_000
    assert generated.manifest["row_counts"]["envios"] < 40_000


def test_historia_atrasos_y_causas(generated):
    region_of = {
        row["comuna_id"]: row["region"]
        for row in generated.tables["comunas"]
        if row["comuna_id"].isdigit()
    }
    envios = _clean_envios(generated.tables["envios"])
    assert len(envios) == 32_000

    def rate(pred):
        rows = []
        for envio in envios:
            if envio["estado"] != "entregado":
                continue
            if not envio["ts_entrega"] or not envio["fecha_promesa"]:
                continue
            if not pred(envio):
                continue
            rows.append(envio["ts_entrega"][:10] > envio["fecha_promesa"])
        assert rows, pred
        return sum(rows) / len(rows), len(rows)

    rm, n_rm = rate(lambda e: region_of[e["comuna_destino_id"]] == "RM")
    extremos, n_ext = rate(
        lambda e: region_of[e["comuna_destino_id"]] in {"AP", "AN", "AI", "MA"}
    )
    andes, n_andes = rate(lambda e: e["carrier_id"] == "CAR-ANDES")
    sur, n_sur = rate(lambda e: e["carrier_id"] == "CAR-SUR")
    assert n_rm > 5_000 and n_ext > 500
    assert n_andes > 1_000 and n_sur > 1_000
    assert extremos > rm + 0.15
    assert sur > andes + 0.12

    motivos = Counter(
        e["motivo_cancelacion_logistica"]
        for e in envios
        if e["estado"] == "cancelado_logistica"
    )
    assert set(motivos) == MOTIVOS
    assert motivos["sin_stock_fc"] == max(motivos.values())
    for envio in envios:
        if envio["estado"] == "cancelado_logistica":
            assert envio["motivo_cancelacion_logistica"] in MOTIVOS
        else:
            assert envio["motivo_cancelacion_logistica"] == ""


def test_fk_limpias_en_el_nucleo(generated):
    sellers = {r["seller_id"] for r in generated.tables["sellers"] if r["seller_id"]}
    comunas = {r["comuna_id"] for r in generated.tables["comunas"] if r["comuna_id"].isdigit()}
    fcs = {r["fc_id"] for r in generated.tables["centros_fulfillment"] if r["fc_id"]}
    carriers = {r["carrier_id"] for r in generated.tables["carriers"] if r["carrier_id"]}
    ordenes = {r["orden_id"] for r in generated.tables["ordenes"] if re.fullmatch(r"ORD-\d{6}", r["orden_id"])}
    for envio in _clean_envios(generated.tables["envios"]):
        assert envio["orden_id"] in ordenes
        assert envio["seller_id"] in sellers
        assert envio["comuna_destino_id"] in comunas
        assert envio["fc_id"] == "" or envio["fc_id"] in fcs
        assert envio["carrier_id"] == "" or envio["carrier_id"] in carriers
        if envio["tipo_logistica"] == "flex":
            assert envio["fc_id"] == ""
