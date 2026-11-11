"""Paso 3 — reglas de silver y reconciliación, sin GCP."""

from __future__ import annotations

from pathlib import Path

import pytest

import generate_data
from build_silver import sql_files
from silver_rules import PRIORIDAD, SPECS, classify, motivos_desde_anomalias, render_sql, resumen
import verify_silver

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def generated():
    return generate_data.generate(42)


def test_sql_renderizado_coincide_con_los_archivos():
    files = sql_files()
    assert [path.name for path in files] == [
        "01_regiones.sql",
        "02_comunas.sql",
        "03_centros_fulfillment.sql",
        "04_carriers.sql",
        "05_sellers.sql",
        "06_ordenes.sql",
        "07_envios.sql",
        "08_eventos_tracking.sql",
    ]
    for path, spec in zip(files, SPECS):
        text = path.read_text(encoding="utf-8")
        assert text == render_sql(spec)
        assert "CREATE OR REPLACE TABLE" in text
        assert "SAFE_CAST" in text
        assert "TRIM(" in text
        assert "QUALIFY ROW_NUMBER()" in text
        assert f"q_{spec.name}" in text
        assert "INTERVAL 60 DAY" in text
        code = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("--")
        ).upper()
        sin_is_not = code.replace("IS NOT NULL", "")
        for token in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER"):
            assert token not in sin_is_not
        assert "NOT NULL" not in sin_is_not
        for motivo in PRIORIDAD:
            assert motivo in text


def test_prioridad_un_motivo_por_fila():
    tablas = {
        "regiones": [
            {"region": "RM", "region_nombre": "Metropolitana", "zona": "centro"},
        ],
        "sellers": [
            # Cast gana al nulo de la PK.
            {
                "seller_id": "",
                "seller_nombre": "Rota",
                "tipo_seller": "pyme",
                "region_origen": "RM",
                "activo": "NO-CAST",
            },
            {
                "seller_id": "SEL-01",
                "seller_nombre": "Casa",
                "tipo_seller": "pyme",
                "region_origen": "  rm  ",
                "activo": "true",
            },
            {
                "seller_id": "SEL-01",
                "seller_nombre": "Casa",
                "tipo_seller": "pyme",
                "region_origen": "RM",
                "activo": "TRUE",
            },
            {
                "seller_id": "SEL-02",
                "seller_nombre": "Huérfana",
                "tipo_seller": "pyme",
                "region_origen": "ZZ",
                "activo": "false",
            },
            {
                "seller_id": "SEL-03",
                "seller_nombre": "Uno",
                "tipo_seller": "pyme",
                "region_origen": "RM",
                "activo": "1",
            },
            {
                "seller_id": "",
                "seller_nombre": "Sin clave",
                "tipo_seller": "pyme",
                "region_origen": "RM",
                "activo": "true",
            },
        ],
    }
    out = classify(tablas)
    sellers_q = out["sellers"]["quarantine"]
    assert list(sellers_q["motivo"]) == [
        "cast_fallido",
        "duplicado",
        "fk_huerfana",
        "nulo_obligatorio",
    ]
    assert out["sellers"]["huerfanas"] == 0
    assert list(out["sellers"]["silver"]["seller_id"]) == ["SEL-01", "SEL-03"]
    assert list(out["sellers"]["silver"]["activo"]) == [True, True]


def test_reconciliacion_contra_el_manifest(generated):
    esperado = motivos_desde_anomalias(generated.manifest["anomalies"])
    clasificado = classify(generated.tables)
    summary = resumen(clasificado)
    assert summary == generated.manifest["silver"]
    for spec in SPECS:
        name = spec.name
        parte = summary["tablas"][name]
        assert parte["huerfanas"] == 0
        assert parte["motivos"] == esperado[name]
        assert parte["silver"] == generated.manifest["clean_counts"][name]
        assert parte["silver"] + parte["cuarentena"] == generated.manifest["row_counts"][name]
        assert sum(parte["motivos"].values()) == parte["cuarentena"]
    assert generated.manifest["bronze_changed_in"] == "paso-3"
    committed = (ROOT / "data" / "manifest.json").read_text(encoding="utf-8")
    import json
    assert json.loads(committed)["silver"]["tablas"]["envios"]["motivos"]["fecha_incoherente"] == 8
    assert json.loads(committed)["row_counts"]["envios"] == 32_064


def test_verify_silver_reporta_falla():
    manifest = {
        "row_counts": {spec.name: 1 for spec in SPECS},
        "silver": {
            "tablas": {
                spec.name: {
                    "silver": 1,
                    "cuarentena": 0,
                    "motivos": {motivo: 0 for motivo in PRIORIDAD},
                }
                for spec in SPECS
            }
        },
    }
    observed = {
        "bronze": {spec.name: 1 for spec in SPECS},
        "huerfanas": 0,
        "silver": manifest["silver"],
    }
    text, ok = verify_silver.render_report(manifest, observed)
    assert ok
    assert "RESULTADO: OK" in text
    observed["huerfanas"] = 3
    observed["bronze"] = dict(observed["bronze"])
    observed["bronze"]["envios"] = 9
    text, ok = verify_silver.render_report(manifest, observed)
    assert not ok
    assert "RESULTADO: FALLA" in text
    assert "huerfanas_en_silver 3" in text


def test_makefile_incluye_silver():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "silver:" in text
    assert "build_silver.py" in text
    assert "verify_silver.py" in text
    assert "run: data bronze silver" in text
