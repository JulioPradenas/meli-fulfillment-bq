"""Contrato de columnas bronze. El DDL se renderiza desde aquí."""

from __future__ import annotations

from bq_env import DATASET, EXPIRATION_DAYS, NOTICE

# Orden = maestros primero, luego hechos. CSV stem == table_id.
TABLE_ORDER: tuple[str, ...] = (
    "regiones",
    "comunas",
    "centros_fulfillment",
    "carriers",
    "sellers",
    "ordenes",
    "envios",
    "eventos_tracking",
)

# (nombre, tipo BigQuery). Sin NOT NULL: el modo es NULLABLE.
TABLES: dict[str, list[tuple[str, str]]] = {
    "regiones": [
        ("region", "STRING"),
        ("region_nombre", "STRING"),
        ("zona", "STRING"),
    ],
    "comunas": [
        ("comuna_id", "STRING"),
        ("comuna_nombre", "STRING"),
        ("region", "STRING"),
    ],
    "centros_fulfillment": [
        ("fc_id", "STRING"),
        ("fc_nombre", "STRING"),
        ("tipo_fc", "STRING"),
        ("comuna_id", "STRING"),
        ("activo", "BOOL"),
    ],
    "carriers": [
        ("carrier_id", "STRING"),
        ("carrier_nombre", "STRING"),
        ("tipo_servicio", "STRING"),
        ("activo", "BOOL"),
    ],
    "sellers": [
        ("seller_id", "STRING"),
        ("seller_nombre", "STRING"),
        ("tipo_seller", "STRING"),
        ("region_origen", "STRING"),
        ("activo", "BOOL"),
    ],
    "ordenes": [
        ("orden_id", "STRING"),
        ("seller_id", "STRING"),
        ("ts_creacion", "TIMESTAMP"),
        ("comuna_destino_id", "STRING"),
        ("estado_orden", "STRING"),
    ],
    "envios": [
        ("envio_id", "STRING"),
        ("orden_id", "STRING"),
        ("seller_id", "STRING"),
        ("fc_id", "STRING"),
        ("carrier_id", "STRING"),
        ("comuna_destino_id", "STRING"),
        ("tipo_logistica", "STRING"),
        ("ts_creacion", "TIMESTAMP"),
        ("ts_despacho", "TIMESTAMP"),
        ("ts_entrega", "TIMESTAMP"),
        ("fecha_promesa", "DATE"),
        ("estado", "STRING"),
        ("motivo_cancelacion_logistica", "STRING"),
    ],
    "eventos_tracking": [
        ("evento_id", "STRING"),
        ("envio_id", "STRING"),
        ("ts_evento", "TIMESTAMP"),
        ("codigo_evento", "STRING"),
        ("fc_id", "STRING"),
        ("carrier_id", "STRING"),
        ("comuna_id", "STRING"),
    ],
}

# Columna que el generador vacía en la anomalía clave_nula.
PRIMARY_KEY: dict[str, str] = {
    "regiones": "region",
    "comunas": "comuna_id",
    "centros_fulfillment": "fc_id",
    "carriers": "carrier_id",
    "sellers": "seller_id",
    "ordenes": "orden_id",
    "envios": "envio_id",
    "eventos_tracking": "evento_id",
}

# Columna de fecha que el núcleo limpio siempre llena y la anomalía fecha_nula vacía.
FECHA_NULA_COL: dict[str, str] = {
    "ordenes": "ts_creacion",
    "envios": "fecha_promesa",
    "eventos_tracking": "ts_evento",
}


def columns(table: str) -> list[str]:
    return [name for name, _typ in TABLES[table]]


def render_ddl() -> str:
    """CREATE OR REPLACE, todas las columnas NULLABLE, expiración 60 días."""
    header = f"""-- Meli Fulfillment — Paso 2: DDL bronze (landing NULLABLE).
-- Dataset: {DATASET} · location: US · expiración: {EXPIRATION_DAYS} días.
-- Sandbox sin facturación: sin DML y sin streaming. Este archivo solo tiene
-- CREATE OR REPLACE TABLE (schema vacío). Los CSV entran por load job
-- WRITE_TRUNCATE. No hay ALTER: si hay que recrear el shape, se reemplaza
-- la tabla y `make run` vuelve a cargar desde cero.
-- Silver/gold (pasos siguientes): CREATE OR REPLACE TABLE/VIEW AS SELECT,
-- partition_expiration_days = {EXPIRATION_DAYS}. Tampoco DML.
--
-- {NOTICE}
"""
    blocks: list[str] = [header.rstrip(), ""]
    for table in TABLE_ORDER:
        col_sql = ",\n".join(f"  {name} {typ}" for name, typ in TABLES[table])
        desc = (
            f"Bronze {table}. {NOTICE} "
            "Landing NULLABLE; la tabla expira a los 60 días."
        )
        blocks.append(
            f"CREATE OR REPLACE TABLE `{DATASET}.{table}` (\n"
            f"{col_sql}\n"
            ")\n"
            "OPTIONS (\n"
            f'  description="{desc}",\n'
            "  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)\n"
            ");\n"
        )
    return "\n".join(blocks).rstrip() + "\n"
