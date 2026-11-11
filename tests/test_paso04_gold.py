"""Paso 4 — estrella gold, historia del manifest y SQL sin partición. Sin GCP."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import generate_data
from build_gold import run as build_run
from build_gold import sql_files
from gold_rules import CALENDAR_END, CALENDAR_START, build_gold, chequeos

ROOT = Path(__file__).resolve().parents[1]


def test_sql_gold_cluster_sin_particion_y_sin_dml():
    files = sql_files()
    assert [path.name for path in files][:6] == [
        "01_d_fecha.sql",
        "02_d_geografia.sql",
        "03_d_centro_fulfillment.sql",
        "04_d_carrier.sql",
        "05_d_seller.sql",
        "06_f_envios.sql",
    ]
    blob = "\n".join(path.read_text(encoding="utf-8") for path in files)
    code = "\n".join(
        line for line in blob.splitlines() if not line.strip().startswith("--")
    ).upper()
    assert "PARTITION BY" not in code
    assert "CLUSTER BY REGION_ID, CARRIER_ID" in code
    assert "CREATE OR REPLACE TABLE" in code
    assert "CREATE OR REPLACE VIEW" in code
    assert "SUM(F.ES_A_TIEMPO) AS N_A_TIEMPO" in code
    assert "SUM(F.ES_ENTREGADO) AS N_ENTREGADOS" in code
    assert "INTERVAL 60 DAY" in code
    sin_is_not = code.replace("IS NOT NULL", "")
    for token in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER"):
        assert token not in sin_is_not
    assert build_run(dry_run=True) == 0


def test_hecho_historia_y_calendario():
    gold = build_gold(generate_data.generate(42).tables)
    assert all(good for *_rest, good in chequeos(gold))
    fechas = gold["d_fecha"]
    assert fechas["fecha"].min() == CALENDAR_START
    assert fechas["fecha"].max() == CALENDAR_END
    assert len(fechas) == 214
    lunes = fechas.loc[fechas["lunes_semana"] == date(2026, 5, 4)].iloc[0]
    assert lunes["semana_iso"] == date(2026, 5, 4).isocalendar().week
    assert int(fechas.loc[fechas["fecha"] == date(2026, 5, 2), "es_fin_de_semana"].iloc[0]) == 1
    assert int(fechas.loc[fechas["fecha"] == date(2026, 5, 4), "es_fin_de_semana"].iloc[0]) == 0
    assert set(gold["f_envios"]["grupo_zona"]) >= {"RM", "extremos", "centro"}
    assert len(gold["d_geografia"]) == 43
    assert len(gold["d_seller"]) == 24
    assert len(gold["d_carrier"]) == 5
    assert len(gold["d_centro_fulfillment"]) == 6


def test_makefile_incluye_gold():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "gold:" in text
    assert "build_gold.py" in text
    assert "verify_gold.py" in text
    assert "run: data bronze silver gold" in text
