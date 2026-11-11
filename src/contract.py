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

# Bronze es landing crudo: todas las columnas son STRING NULLABLE.
# El load de BigQuery rechaza 'NO-CAST' si la columna ya es BOOL, DATE o
# TIMESTAMP (max_bad_records=0). El tipo real se aplica en silver con SAFE_CAST.
TABLES: dict[str, list[tuple[str, str]]] = {
    table: [(name, "STRING") for name, _typ in cols]
    for table, cols in {
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
            ("activo", "STRING"),
        ],
        "carriers": [
            ("carrier_id", "STRING"),
            ("carrier_nombre", "STRING"),
            ("tipo_servicio", "STRING"),
            ("activo", "STRING"),
        ],
        "sellers": [
            ("seller_id", "STRING"),
            ("seller_nombre", "STRING"),
            ("tipo_seller", "STRING"),
            ("region_origen", "STRING"),
            ("activo", "STRING"),
        ],
        "ordenes": [
            ("orden_id", "STRING"),
            ("seller_id", "STRING"),
            ("ts_creacion", "STRING"),
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
            ("ts_creacion", "STRING"),
            ("ts_despacho", "STRING"),
            ("ts_entrega", "STRING"),
            ("fecha_promesa", "STRING"),
            ("estado", "STRING"),
            ("motivo_cancelacion_logistica", "STRING"),
        ],
        "eventos_tracking": [
            ("evento_id", "STRING"),
            ("envio_id", "STRING"),
            ("ts_evento", "STRING"),
            ("codigo_evento", "STRING"),
            ("fc_id", "STRING"),
            ("carrier_id", "STRING"),
            ("comuna_id", "STRING"),
        ],
    }.items()
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
    """CREATE OR REPLACE. Bronze es todo STRING NULLABLE. El tipo vive en silver."""
    header = f"""-- Meli Fulfillment — DDL bronze (landing crudo, todo STRING NULLABLE).
-- Dataset: {DATASET} · location: US · expiración: {EXPIRATION_DAYS} días.
-- Sandbox sin facturación: sin DML y sin streaming. Este archivo solo tiene
-- CREATE OR REPLACE TABLE. Los CSV entran por load job WRITE_TRUNCATE
-- con max_bad_records=0. No hay ALTER.
--
-- Todas las columnas son STRING. Un BOOL/DATE/TIMESTAMP en el load rechaza
-- el token 'NO-CAST' y el job falla entero (incidente PR #3: regiones y
-- comunas cargaron; el resto no). Silver castea con SAFE_CAST.
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
