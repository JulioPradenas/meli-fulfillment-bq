"""
Reglas de silver, en un solo lugar.

El SQL de sql/silver/ se renderiza desde aquí. El mismo spec clasifica los CSV
en pandas (tests y `verify_silver --dry-run`). Si las dos vías se separan, el
test que compara el archivo con `render_sql()` y el que compara pandas contra
el manifest lo van a notar.

Prioridad de motivo — una fila de bronze, un solo motivo, el primero que aplica:

1. cast_fallido        el texto no vacío no entra en el tipo
2. nulo_obligatorio    falta la PK o un campo requerido
3. duplicado           ROW_NUMBER > 1 de la llave natural, entre las filas que
                       pasaron los dos filtros de arriba
4. fk_huerfana         el valor no está en la dimensión silver (el vacío de una
                       FK opcional no es huérfano)
5. fecha_incoherente   ts_entrega < ts_despacho, o un evento entregado anterior
                       al despacho del envío

Bronze no se pierde: cada fila termina en silver o en q_<tabla>.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from bq_env import EXPIRATION_DAYS, NOTICE, SILVER_DATASET

PRIORIDAD: tuple[str, ...] = (
    "cast_fallido",
    "nulo_obligatorio",
    "duplicado",
    "fk_huerfana",
    "fecha_incoherente",
)

BRONZE_DATASET = "meli_bronze"
TS_FMT = "%Y-%m-%d %H:%M:%S%z"


@dataclass(frozen=True)
class Column:
    name: str
    bq_type: str  # STRING | DATE | TIMESTAMP | BOOL
    required: bool
    normalize: str = "trim"  # trim | lower | upper


@dataclass(frozen=True)
class ForeignKey:
    column: str
    parent: str
    parent_column: str
    required: bool


@dataclass(frozen=True)
class TableSpec:
    name: str
    pk: str
    columns: tuple[Column, ...]
    fks: tuple[ForeignKey, ...] = ()
    fecha_rule: str | None = None  # envio | evento


def _col(name: str, bq_type: str, required: bool, normalize: str = "trim") -> Column:
    return Column(name, bq_type, required, normalize)


SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        "regiones",
        "region",
        (
            _col("region", "STRING", True, "upper"),
            _col("region_nombre", "STRING", True),
            _col("zona", "STRING", True, "lower"),
        ),
    ),
    TableSpec(
        "comunas",
        "comuna_id",
        (
            _col("comuna_id", "STRING", True),
            _col("comuna_nombre", "STRING", True),
            _col("region", "STRING", True, "upper"),
        ),
        (ForeignKey("region", "regiones", "region", True),),
    ),
    TableSpec(
        "centros_fulfillment",
        "fc_id",
        (
            _col("fc_id", "STRING", True),
            _col("fc_nombre", "STRING", True),
            _col("tipo_fc", "STRING", True, "lower"),
            _col("comuna_id", "STRING", True),
            _col("activo", "BOOL", True, "lower"),
        ),
        (ForeignKey("comuna_id", "comunas", "comuna_id", True),),
    ),
    TableSpec(
        "carriers",
        "carrier_id",
        (
            _col("carrier_id", "STRING", True),
            _col("carrier_nombre", "STRING", True),
            _col("tipo_servicio", "STRING", True, "lower"),
            _col("activo", "BOOL", True, "lower"),
        ),
    ),
    TableSpec(
        "sellers",
        "seller_id",
        (
            _col("seller_id", "STRING", True),
            _col("seller_nombre", "STRING", True),
            _col("tipo_seller", "STRING", True, "lower"),
            _col("region_origen", "STRING", True, "upper"),
            _col("activo", "BOOL", True, "lower"),
        ),
        (ForeignKey("region_origen", "regiones", "region", True),),
    ),
    TableSpec(
        "ordenes",
        "orden_id",
        (
            _col("orden_id", "STRING", True),
            _col("seller_id", "STRING", True),
            _col("ts_creacion", "TIMESTAMP", True),
            _col("comuna_destino_id", "STRING", True),
            _col("estado_orden", "STRING", True, "lower"),
        ),
        (
            ForeignKey("seller_id", "sellers", "seller_id", True),
            ForeignKey("comuna_destino_id", "comunas", "comuna_id", True),
        ),
    ),
    TableSpec(
        "envios",
        "envio_id",
        (
            _col("envio_id", "STRING", True),
            _col("orden_id", "STRING", True),
            _col("seller_id", "STRING", True),
            _col("fc_id", "STRING", False),
            _col("carrier_id", "STRING", False),
            _col("comuna_destino_id", "STRING", True),
            _col("tipo_logistica", "STRING", True, "lower"),
            _col("ts_creacion", "TIMESTAMP", True),
            _col("ts_despacho", "TIMESTAMP", False),
            _col("ts_entrega", "TIMESTAMP", False),
            _col("fecha_promesa", "DATE", True),
            _col("estado", "STRING", True, "lower"),
            _col("motivo_cancelacion_logistica", "STRING", False, "lower"),
        ),
        (
            ForeignKey("orden_id", "ordenes", "orden_id", True),
            ForeignKey("seller_id", "sellers", "seller_id", True),
            ForeignKey("fc_id", "centros_fulfillment", "fc_id", False),
            ForeignKey("carrier_id", "carriers", "carrier_id", False),
            ForeignKey("comuna_destino_id", "comunas", "comuna_id", True),
        ),
        fecha_rule="envio",
    ),
    TableSpec(
        "eventos_tracking",
        "evento_id",
        (
            _col("evento_id", "STRING", True),
            _col("envio_id", "STRING", True),
            _col("ts_evento", "TIMESTAMP", True),
            _col("codigo_evento", "STRING", True, "lower"),
            _col("fc_id", "STRING", False),
            _col("carrier_id", "STRING", False),
            _col("comuna_id", "STRING", False),
        ),
        (
            ForeignKey("envio_id", "envios", "envio_id", True),
            ForeignKey("fc_id", "centros_fulfillment", "fc_id", False),
            ForeignKey("carrier_id", "carriers", "carrier_id", False),
            ForeignKey("comuna_id", "comunas", "comuna_id", False),
        ),
        fecha_rule="evento",
    ),
)

SPEC_BY_NAME = {spec.name: spec for spec in SPECS}


def motivos_desde_anomalias(anomalies: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Cada fila inyectada tiene un solo problema. El núcleo limpio no se cuarentena."""
    out: dict[str, dict[str, int]] = {}
    for spec in SPECS:
        kinds = anomalies[spec.name]
        out[spec.name] = {
            "cast_fallido": int(kinds.get("cast_fallido", 0)),
            "nulo_obligatorio": int(kinds.get("fecha_nula", 0)) + int(kinds.get("clave_nula", 0)),
            "duplicado": int(kinds.get("duplicado_exacto", 0)),
            "fk_huerfana": int(kinds.get("fk_huerfana", 0)),
            "fecha_incoherente": int(kinds.get("evento_fuera_de_orden", 0))
            + int(kinds.get("entrega_antes_despacho", 0)),
        }
    return out


def _normalize_text(value: object, mode: str) -> str | None:
    text = "" if value is None else str(value)
    text = text.strip()
    if mode == "lower":
        text = text.lower()
    elif mode == "upper":
        text = text.upper()
    return text or None


def _parse_typed(text: str, bq_type: str):
    # El CSV puede traer true/True/1. SAFE_CAST de BigQuery acepta true/false;
    # el 1 y el 0 se normalizan antes, igual que en el SQL.
    if bq_type == "BOOL":
        token = text.lower()
        if token in {"1", "true"}:
            return True
        if token in {"0", "false"}:
            return False
        return None
    if bq_type == "DATE":
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    if bq_type == "TIMESTAMP":
        try:
            return datetime.strptime(text, TS_FMT)
        except ValueError:
            return None
    return text


def classify(tables: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, object]]:
    """Devuelve silver (DataFrame), quarantine (DataFrame) y huerfanas por tabla."""
    silver_keys: dict[str, set] = {}
    envio_despacho: dict[str, datetime] = {}
    result: dict[str, dict[str, object]] = {}

    for spec in SPECS:
        frame = pd.DataFrame(tables.get(spec.name, []))
        if frame.empty:
            frame = pd.DataFrame(columns=[col.name for col in spec.columns])
        for col in spec.columns:
            if col.name not in frame.columns:
                frame[col.name] = ""
        frame = frame[[col.name for col in spec.columns]].fillna("")
        frame["_idx"] = range(len(frame))

        norm: dict[str, list] = {}
        parsed: dict[str, list] = {}
        cast_fail = pd.Series(False, index=frame.index)
        cast_regla = pd.Series(pd.NA, index=frame.index, dtype="object")
        for col in spec.columns:
            texts = [_normalize_text(value, col.normalize) for value in frame[col.name]]
            norm[col.name] = texts
            values: list = []
            for pos, text in enumerate(texts):
                if text is None or col.bq_type == "STRING":
                    values.append(text)
                    continue
                typed = _parse_typed(text, col.bq_type)
                if typed is None:
                    cast_fail.iat[pos] = True
                    if pd.isna(cast_regla.iat[pos]):
                        cast_regla.iat[pos] = f"SAFE_CAST falló en {col.name}"
                    values.append(None)
                else:
                    values.append(typed)
            parsed[col.name] = values

        motivo = pd.Series(pd.NA, index=frame.index, dtype="object")
        regla = pd.Series(pd.NA, index=frame.index, dtype="object")
        motivo = motivo.mask(cast_fail, "cast_fallido")
        regla = regla.mask(cast_fail, cast_regla)

        for col in spec.columns:
            if not col.required:
                continue
            missing = pd.Series([value is None for value in parsed[col.name]], index=frame.index)
            take = motivo.isna() & missing
            motivo = motivo.mask(take, "nulo_obligatorio")
            regla = regla.mask(take, f"{col.name} vacío")

        pk_values = pd.Series(parsed[spec.pk], index=frame.index, dtype="object")
        good = motivo.isna()
        if bool(good.any()):
            order = frame.loc[good].sort_values("_idx", kind="mergesort")
            keys = pk_values.loc[order.index]
            rn = keys.groupby(keys.astype(str), sort=False).cumcount() + 1
            dup = rn > 1
            dup_idx = rn.index[dup]
            motivo.loc[dup_idx] = "duplicado"
            regla.loc[dup_idx] = f"ROW_NUMBER > 1 por {spec.pk}"

        for fk in spec.fks:
            parent = silver_keys.get(fk.parent, set())
            values = parsed[fk.column]
            missing_fk = []
            for value, already in zip(values, motivo.isna()):
                if not already or value is None:
                    missing_fk.append(False)
                else:
                    missing_fk.append(value not in parent)
            take = pd.Series(missing_fk, index=frame.index)
            motivo = motivo.mask(take, "fk_huerfana")
            regla = regla.mask(take, f"{fk.column} no está en silver.{fk.parent}")

        if spec.fecha_rule == "envio":
            incoherente = []
            for entrega, despacho, already in zip(
                parsed["ts_entrega"], parsed["ts_despacho"], motivo.isna()
            ):
                incoherente.append(
                    bool(already and entrega is not None and despacho is not None and entrega < despacho)
                )
            take = pd.Series(incoherente, index=frame.index)
            motivo = motivo.mask(take, "fecha_incoherente")
            regla = regla.mask(take, "ts_entrega anterior a ts_despacho")
        elif spec.fecha_rule == "evento":
            incoherente = []
            for codigo, ts_evento, envio_id, already in zip(
                parsed["codigo_evento"],
                parsed["ts_evento"],
                parsed["envio_id"],
                motivo.isna(),
            ):
                despacho = envio_despacho.get(envio_id) if envio_id is not None else None
                incoherente.append(
                    bool(
                        already
                        and codigo == "entregado"
                        and ts_evento is not None
                        and despacho is not None
                        and ts_evento < despacho
                    )
                )
            take = pd.Series(incoherente, index=frame.index)
            motivo = motivo.mask(take, "fecha_incoherente")
            regla = regla.mask(take, "evento entregado anterior al despacho del envío")

        keep = motivo.isna()
        silver_rows = []
        for pos in frame.index[keep]:
            silver_rows.append({col.name: parsed[col.name][pos] for col in spec.columns})
        q_rows = []
        for pos in frame.index[~keep]:
            raw = {col.name: frame.at[pos, col.name] for col in spec.columns}
            raw["motivo"] = motivo.at[pos]
            raw["regla"] = regla.at[pos]
            q_rows.append(raw)

        silver = pd.DataFrame(silver_rows, columns=[col.name for col in spec.columns])
        quarantine = pd.DataFrame(
            q_rows, columns=[col.name for col in spec.columns] + ["motivo", "regla"]
        )
        keys = set()
        orphans = 0
        for row in silver_rows:
            keys.add(row[spec.pk])
            for fk in spec.fks:
                value = row[fk.column]
                if value is None:
                    continue
                if value not in silver_keys.get(fk.parent, set()):
                    orphans += 1
        if spec.name == "envios":
            for row in silver_rows:
                if row["ts_despacho"] is not None and row["envio_id"] is not None:
                    envio_despacho[row["envio_id"]] = row["ts_despacho"]
        silver_keys[spec.name] = keys
        result[spec.name] = {
            "silver": silver,
            "quarantine": quarantine,
            "huerfanas": orphans,
        }
    return result


def resumen(clasificado: dict[str, dict[str, object]]) -> dict[str, dict]:
    tablas = {}
    for spec in SPECS:
        part = clasificado[spec.name]
        q = part["quarantine"]
        motivos = {motivo: 0 for motivo in PRIORIDAD}
        if len(q):
            for motivo, n in q["motivo"].value_counts().items():
                motivos[str(motivo)] = int(n)
        tablas[spec.name] = {
            "silver": int(len(part["silver"])),
            "cuarentena": int(len(q)),
            "huerfanas": int(part["huerfanas"]),
            "motivos": motivos,
        }
    return {
        "prioridad": list(PRIORIDAD),
        "tablas": tablas,
    }


def _expr(col: Column) -> str:
    # Bronze es STRING. CAST AS STRING no asume el tipo de llegada: TRIM exige STRING.
    as_string = f"CAST(src.{col.name} AS STRING)"
    trimmed = f"TRIM({as_string})"
    if col.normalize == "lower":
        body = f"LOWER({trimmed})"
    elif col.normalize == "upper":
        body = f"UPPER({trimmed})"
    else:
        body = trimmed
    text = f"NULLIF({body}, '')"
    if col.bq_type == "STRING":
        return f"{text} AS {col.name}"
    if col.bq_type == "BOOL":
        # true/True/TRUE y 1 entran; false/False/0 también. NO-CAST no.
        mapped = (
            "CASE LOWER(" + trimmed + ")\n"
            "      WHEN '1' THEN 'true'\n"
            "      WHEN '0' THEN 'false'\n"
            "      ELSE " + text + "\n"
            "    END"
        )
        return (
            f"{text} AS {col.name}_txt,\n"
            f"    SAFE_CAST({mapped} AS BOOL) AS {col.name}"
        )
    return (
        f"{text} AS {col.name}_txt,\n"
        f"    SAFE_CAST({text} AS {col.bq_type}) AS {col.name}"
    )


def _cte(spec: TableSpec) -> str:
    raw_cols = ",\n    ".join(f"src.{col.name} AS raw_{col.name}" for col in spec.columns)
    typed = ",\n    ".join(_expr(col) for col in spec.columns)
    cast_whens = []
    cast_reglas = []
    nulo_whens = []
    nulo_reglas = []
    for col in spec.columns:
        if col.bq_type != "STRING":
            cond = f"({col.name}_txt IS NOT NULL AND {col.name} IS NULL)"
            cast_whens.append(cond)
            cast_reglas.append(f"WHEN {cond} THEN 'SAFE_CAST falló en {col.name}'")
        if col.required:
            nulo_whens.append(f"{col.name} IS NULL")
            nulo_reglas.append(f"WHEN {col.name} IS NULL THEN '{col.name} vacío'")
    cast_sql = " OR ".join(cast_whens) if cast_whens else "FALSE"
    nulo_sql = " OR ".join(nulo_whens)
    order_cols = ", ".join(col.name for col in spec.columns if col.name != spec.pk)
    joins = []
    fk_whens = []
    fk_reglas = []
    for fk in spec.fks:
        alias = f"fk_{fk.parent}_{fk.column}"
        joins.append(
            f"LEFT JOIN `{SILVER_DATASET}.{fk.parent}` AS {alias}\n"
            f"    ON ranked.{fk.column} = {alias}.{fk.parent_column}"
        )
        cond = f"ranked.{fk.column} IS NOT NULL AND {alias}.{fk.parent_column} IS NULL"
        fk_whens.append(f"WHEN {cond} THEN 'fk_huerfana'")
        fk_reglas.append(
            f"WHEN {cond} THEN '{fk.column} no está en silver.{fk.parent}'"
        )
    fecha_when = ""
    fecha_regla = ""
    if spec.fecha_rule == "envio":
        fecha_when = (
            "WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL "
            "AND ranked.ts_entrega < ranked.ts_despacho THEN 'fecha_incoherente'"
        )
        fecha_regla = (
            "WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL "
            "AND ranked.ts_entrega < ranked.ts_despacho "
            "THEN 'ts_entrega anterior a ts_despacho'"
        )
    elif spec.fecha_rule == "evento":
        joins.append(
            f"LEFT JOIN `{SILVER_DATASET}.envios` AS env_desp\n"
            "    ON ranked.envio_id = env_desp.envio_id"
        )
        fecha_when = (
            "WHEN ranked.codigo_evento = 'entregado' "
            "AND env_desp.ts_despacho IS NOT NULL "
            "AND ranked.ts_evento < env_desp.ts_despacho THEN 'fecha_incoherente'"
        )
        fecha_regla = (
            "WHEN ranked.codigo_evento = 'entregado' "
            "AND env_desp.ts_despacho IS NOT NULL "
            "AND ranked.ts_evento < env_desp.ts_despacho "
            "THEN 'evento entregado anterior al despacho del envío'"
        )
    join_sql = "\n  ".join(joins)
    fk_when_sql = "\n      ".join(fk_whens)
    fk_regla_sql = "\n      ".join(fk_reglas)
    extra_when = "\n      ".join(part for part in (fk_when_sql, fecha_when) if part)
    extra_regla = "\n      ".join(part for part in (fk_regla_sql, fecha_regla) if part)
    nulo_regla_sql = "\n      ".join(nulo_reglas)
    cast_regla_sql = "\n      ".join(cast_reglas) if cast_reglas else "WHEN FALSE THEN ''"
    return f"""WITH src AS (
  SELECT * FROM `{BRONZE_DATASET}.{spec.name}`
),
raw AS (
  SELECT
    {raw_cols},
    {typed}
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN {cast_sql} THEN 'cast_fallido'
      WHEN {nulo_sql} THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      {cast_regla_sql}
      {nulo_regla_sql}
      ELSE NULL
    END AS regla_base
  FROM raw
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY IF(motivo_base IS NULL, {spec.pk}, CAST(NULL AS STRING))
        ORDER BY {order_cols}
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      {extra_when}
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por {spec.pk}'
      {extra_regla}
      ELSE NULL
    END AS regla
  FROM ranked
  {join_sql}
)"""


def render_sql(spec: TableSpec) -> str:
    cols = ",\n  ".join(col.name for col in spec.columns)
    raw_cols = ",\n  ".join(f"raw_{col.name} AS {col.name}" for col in spec.columns)
    order_cols = ", ".join(col.name for col in spec.columns if col.name != spec.pk)
    desc = (
        f"Silver {spec.name}. {NOTICE} "
        f"Tipado, deduplicado, FK contra silver. Expira a los {EXPIRATION_DAYS} días."
    )
    qdesc = (
        f"Cuarentena de {spec.name}. {NOTICE} "
        "Una fila, un motivo, el de mayor prioridad. Expira a los "
        f"{EXPIRATION_DAYS} días."
    )
    options = (
        "OPTIONS (\n"
        f'  description="{desc}",\n'
        "  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)\n"
        ")"
    )
    qoptions = (
        "OPTIONS (\n"
        f'  description="{qdesc}",\n'
        "  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)\n"
        ")"
    )
    cte = _cte(spec)
    header = (
        f"-- {SILVER_DATASET}.{spec.name} y {SILVER_DATASET}.q_{spec.name}\n"
        "-- Prioridad (una fila, un motivo): "
        + ", ".join(PRIORIDAD)
        + ".\n"
        "-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.\n"
        f"-- {NOTICE}\n"
    )
    silver = (
        f"CREATE OR REPLACE TABLE `{SILVER_DATASET}.{spec.name}`\n"
        f"{options}\n"
        "AS\n"
        f"{cte}\n"
        "SELECT\n"
        f"  {cols}\n"
        "FROM resolved\n"
        "WHERE motivo IS NULL\n"
        "QUALIFY ROW_NUMBER() OVER (\n"
        f"  PARTITION BY {spec.pk}\n"
        f"  ORDER BY {order_cols}\n"
        ") = 1;\n"
    )
    quarantine = (
        f"CREATE OR REPLACE TABLE `{SILVER_DATASET}.q_{spec.name}`\n"
        f"{qoptions}\n"
        "AS\n"
        f"{cte}\n"
        "SELECT\n"
        f"  {raw_cols},\n"
        "  motivo,\n"
        "  regla\n"
        "FROM resolved\n"
        "WHERE motivo IS NOT NULL;\n"
    )
    return header + "\n" + silver + "\n" + quarantine


def sql_filename(spec: TableSpec, index: int) -> str:
    return f"{index:02d}_{spec.name}.sql"
