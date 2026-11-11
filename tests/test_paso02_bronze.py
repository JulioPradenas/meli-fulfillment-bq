"""Paso 2 — DDL y load job respetan el sandbox. Sin credenciales y sin llamadas a GCP."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

import apply_ddl
import bq_env
import contract
import load_bronze
import verify_bronze
from csv_io import write_table

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "ddl_bronze.sql"


def _sql_code(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        kept.append(line)
    return "\n".join(kept).upper()


def test_ddl_bronze_todas_las_columnas_son_string():
    """El load tipado rechazó NO-CAST (PR #3). Bronze no declara BOOL/DATE/TIMESTAMP."""
    import re

    text = SQL.read_text(encoding="utf-8")
    types = re.findall(r"(?m)^  [a-z0-9_]+ ([A-Z0-9_]+),?$", text)
    assert types, "no se leyeron columnas del DDL"
    assert set(types) == {"STRING"}
    for table in contract.TABLE_ORDER:
        assert {typ for _name, typ in contract.TABLES[table]} == {"STRING"}
        assert {field.field_type for field in load_bronze.contract_schema(table)} == {"STRING"}


def test_csv_crudo_entra_en_schema_string_y_no_cast_revienta_un_tipo():
    """DRY=1 solo miraba el header. Este test mira el valor contra el tipo del job."""
    import generate_data

    gen = generate_data.generate(42)
    saw_no_cast = False
    for table, rows in gen.tables.items():
        schema = {field.name: field.field_type for field in load_bronze.contract_schema(table)}
        for row in rows:
            for column, value in row.items():
                assert load_bronze.bronze_load_accepts(value, schema[column]), (
                    f"{table}.{column}={value!r} no entra en {schema[column]}"
                )
                if str(value).strip() == "NO-CAST":
                    saw_no_cast = True
                    assert not load_bronze.bronze_load_accepts(value, "BOOL")
                    assert not load_bronze.bronze_load_accepts(value, "DATE")
                    assert not load_bronze.bronze_load_accepts(value, "TIMESTAMP")
    assert saw_no_cast, "el generador ya no inyecta NO-CAST; el incidente deja de estar cubierto"
    assert load_bronze.bronze_load_accepts("true", "BOOL")
    assert load_bronze.bronze_load_accepts("True", "BOOL")
    assert load_bronze.bronze_load_accepts("1", "BOOL")
    assert load_bronze.bronze_load_accepts("", "BOOL")
    rendered = contract.render_ddl()
    assert SQL.read_text(encoding="utf-8") == rendered
    code = _sql_code(rendered)
    assert code.count("CREATE OR REPLACE TABLE") == len(contract.TABLE_ORDER)
    assert "NOT NULL" not in code
    for forbidden in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER", "STREAMING"):
        assert forbidden not in code
    assert "INTERVAL 60 DAY" in code
    assert "MELI_BRONZE" in code
    for table in contract.TABLE_ORDER:
        assert f"`MELI_BRONZE.{table.upper()}`" in code or f"`meli_bronze.{table}`".upper() in code


def test_sources_no_dml_ni_service_account():
    for name in ("apply_ddl.py", "load_bronze.py", "verify_bronze.py", "bq_env.py"):
        text = (ROOT / "src" / name).read_text(encoding="utf-8")
        assert "insert_rows" not in text
        assert "from_service_account" not in text
        assert "service-account" not in text.lower() or "service account" in text.lower()
    load_text = (ROOT / "src" / "load_bronze.py").read_text(encoding="utf-8")
    assert "WRITE_TRUNCATE" in load_text
    assert "load_table_from_file" in load_text
    apply_text = (ROOT / "src" / "apply_ddl.py").read_text(encoding="utf-8")
    assert "ALTER TABLE" not in apply_text
    assert "CREATE OR REPLACE" in (ROOT / "sql" / "ddl_bronze.sql").read_text(encoding="utf-8")


def test_falta_gcp_project_mensaje_claro(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    # Un .env local no debe existir en CI; si existiera, no lo leemos como default
    # porque el test apunta el lector a un archivo ausente vía el entorno limpio.
    monkeypatch.setattr(bq_env, "_load_dotenv_file", lambda _path: None)
    with pytest.raises(SystemExit, match="GCP_PROJECT"):
        bq_env.load_project_id()


def test_gcp_project_no_tiene_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GCP_PROJECT", "otro-proyecto")
    monkeypatch.setattr(bq_env, "_load_dotenv_file", lambda _path: None)
    assert bq_env.load_project_id() == "otro-proyecto"


def test_ensure_dataset_crea_en_us_con_expiracion_60():
    client = MagicMock()
    client.get_dataset.side_effect = NotFound("missing")
    action = apply_ddl.ensure_dataset(client, "meli-fulfillment-jp")
    assert action == "created"
    dataset = client.create_dataset.call_args[0][0]
    assert dataset.dataset_id == "meli_bronze"
    assert dataset.location == "US"
    assert dataset.default_table_expiration_ms == 60 * 24 * 60 * 60 * 1000
    assert dataset.default_partition_expiration_ms == dataset.default_table_expiration_ms
    client.update_dataset.assert_not_called()


def test_ensure_dataset_rechaza_otra_location():
    client = MagicMock()
    existing = MagicMock()
    existing.location = "southamerica-west1"
    client.get_dataset.return_value = existing
    with pytest.raises(SystemExit, match="location"):
        apply_ddl.ensure_dataset(client, "meli-fulfillment-jp")
    client.create_dataset.assert_not_called()


def test_apply_dry_run_no_crea_cliente(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        apply_ddl,
        "build_client",
        lambda _project: (_ for _ in ()).throw(AssertionError("no debe conectar")),
    )
    assert apply_ddl.run(dry_run=True) == 0


def test_load_config_write_truncate_y_nullable():
    required = [
        bigquery.SchemaField("envio_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("fecha_promesa", "DATE", mode="REQUIRED"),
    ]
    nullable = load_bronze.schema_as_nullable(required)
    assert all(field.mode == "NULLABLE" for field in nullable)

    cfg = load_bronze.build_load_job_config("envios")
    assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert cfg.skip_leading_rows == 1
    assert cfg.autodetect is False
    assert cfg.source_format == bigquery.SourceFormat.CSV
    assert [field.name for field in cfg.schema] == contract.columns("envios")
    assert all(field.mode == "NULLABLE" for field in cfg.schema)
    assert not any(str(field.mode).upper() == "REQUIRED" for field in cfg.schema)
    assert {field.field_type for field in cfg.schema} == {"STRING"}
    assert cfg.max_bad_records == 0


def test_load_dry_run_no_escribe(tmp_path: Path):
    table = "carriers"
    cols = contract.columns(table)
    path_dir = tmp_path
    write_table(
        path_dir / f"{table}.csv",
        table,
        [{col: "x" for col in cols}, {col: "y" for col in cols}],
    )
    client = MagicMock()
    result = load_bronze.load_one_table(
        client,
        project_id="no-se-usa",
        table_id=table,
        raw_dir=path_dir,
        dry_run=True,
    )
    assert result.action == "would_load"
    assert result.csv_rows == 2
    client.load_table_from_file.assert_not_called()
    client.get_table.assert_not_called()


def test_load_real_usa_load_job_y_verifica(tmp_path: Path):
    table = "carriers"
    cols = contract.columns(table)
    write_table(tmp_path / f"{table}.csv", table, [{col: "x" for col in cols}])
    client = MagicMock()
    job = MagicMock()
    client.load_table_from_file.return_value = job
    refreshed = MagicMock()
    refreshed.num_rows = 1
    client.get_table.return_value = refreshed
    result = load_bronze.load_one_table(
        client,
        project_id="meli-fulfillment-jp",
        table_id=table,
        raw_dir=tmp_path,
        dry_run=False,
    )
    assert result.action == "loaded"
    assert result.bq_rows == 1
    client.load_table_from_file.assert_called_once()
    assert client.load_table_from_file.call_args.kwargs["location"] == "US"
    job.result.assert_called_once()


def test_verify_report_ok_y_fail():
    manifest = {table: 3 for table in contract.TABLE_ORDER}
    csv_counts = dict(manifest)
    text, ok = verify_bronze.render_report(manifest, csv_counts, csv_counts)
    assert ok
    assert "RESULTADO: OK" in text
    assert "FAIL" not in text.split("RESULTADO:")[-1]
    csv_counts = dict(manifest)
    csv_counts["envios"] = 2
    text, ok = verify_bronze.render_report(manifest, csv_counts, manifest)
    assert not ok
    assert "FAIL" in text
    dry_text, dry_ok = verify_bronze.render_report(manifest, manifest, None)
    assert dry_ok
    assert "dry-run" in dry_text


def test_makefile_tiene_data_bronze_run_y_test():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("data:", "bronze:", "run:", "test:"):
        assert target in text
    assert "pytest" in text
    assert "generate_data.py" in text
    assert "apply_ddl.py" in text
    assert "load_bronze.py" in text
    assert "verify_bronze.py" in text
