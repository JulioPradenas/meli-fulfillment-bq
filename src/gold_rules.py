"""Espejo pandas del gold. Misma definición que sql/gold, para tests y DRY=1."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from silver_rules import classify

TZ = ZoneInfo("America/Santiago")
CALENDAR_START = date(2026, 5, 1)
CALENDAR_END = date(2026, 11, 30)
EXTREMOS = {"AP", "AN", "AI", "MA"}

# Historia impresa por el generador (seed 42), redondeada a 4 decimales.
STORY = {
    "rm_atrasados": 0.0722,
    "rm_n": 11234,
    "extremos_atrasados": 0.3801,
    "extremos_n": 2223,
    "andes_atrasados": 0.0757,
    "sur_atrasados": 0.3006,
    "sin_stock_fc": 853,
}


def grupo_zona(region_id: str, zona: str) -> str:
    if region_id == "RM":
        return "RM"
    if region_id in EXTREMOS:
        return "extremos"
    if zona == "centro":
        return "centro"
    return zona


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def _as_date(value: object) -> date | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(TZ).date()
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _hours(end: object, start: object) -> float | None:
    if _is_missing(end) or _is_missing(start):
        return None
    if not isinstance(end, datetime) or not isinstance(start, datetime):
        return None
    return (end - start).total_seconds() / 3600.0


def build_gold(tables: dict[str, list[dict[str, str]]]) -> dict[str, pd.DataFrame]:
    silver = classify(tables)
    envios = silver["envios"]["silver"]
    comunas = silver["comunas"]["silver"]
    regiones = silver["regiones"]["silver"]
    centros = silver["centros_fulfillment"]["silver"]
    carriers = silver["carriers"]["silver"]
    sellers = silver["sellers"]["silver"]

    fechas = []
    day = CALENDAR_START
    while day <= CALENDAR_END:
        iso = day.isocalendar()
        fechas.append(
            {
                "fecha": day,
                "anio": day.year,
                "mes": day.month,
                "semana_iso": iso.week,
                "anio_iso": iso.year,
                "lunes_semana": day - timedelta(days=day.weekday()),
                "es_fin_de_semana": 1 if day.weekday() >= 5 else 0,
            }
        )
        day += timedelta(days=1)
    d_fecha = pd.DataFrame(fechas)

    region_nombre = dict(zip(regiones["region"], regiones["region_nombre"]))
    region_zona = dict(zip(regiones["region"], regiones["zona"]))
    geo_rows = []
    for row in comunas.to_dict(orient="records"):
        region_id = row["region"]
        zona = region_zona[region_id]
        geo_rows.append(
            {
                "comuna_id": row["comuna_id"],
                "comuna_nombre": row["comuna_nombre"],
                "region_id": region_id,
                "region_nombre": region_nombre[region_id],
                "zona": zona,
                "grupo_zona": grupo_zona(region_id, zona),
                "es_extremo": 1 if region_id in EXTREMOS else 0,
                "es_rm": 1 if region_id == "RM" else 0,
            }
        )
    d_geografia = pd.DataFrame(geo_rows)
    geo_by_comuna = d_geografia.set_index("comuna_id")

    d_centro = centros.rename(columns={})[
        ["fc_id", "fc_nombre", "tipo_fc", "comuna_id", "activo"]
    ].copy()
    d_carrier = carriers[["carrier_id", "carrier_nombre", "tipo_servicio", "activo"]].copy()
    d_seller = sellers[
        ["seller_id", "seller_nombre", "tipo_seller", "region_origen", "activo"]
    ].copy()

    fact_rows = []
    for row in envios.to_dict(orient="records"):
        geo = geo_by_comuna.loc[row["comuna_destino_id"]]
        fecha_creacion = _as_date(row["ts_creacion"])
        fecha_despacho = _as_date(row["ts_despacho"])
        fecha_promesa = _as_date(row["fecha_promesa"])
        fecha_entrega = _as_date(row["ts_entrega"])
        entregado = int(row["estado"] == "entregado" and fecha_entrega is not None)
        a_tiempo = int(entregado == 1 and fecha_entrega <= fecha_promesa)
        atrasado = int(entregado == 1 and fecha_entrega > fecha_promesa)
        fact_rows.append(
            {
                "envio_id": row["envio_id"],
                "orden_id": row["orden_id"],
                "seller_id": row["seller_id"],
                "fc_id": None if _is_missing(row["fc_id"]) else row["fc_id"],
                "carrier_id": None if _is_missing(row["carrier_id"]) else row["carrier_id"],
                "comuna_id": row["comuna_destino_id"],
                "region_id": geo["region_id"],
                "grupo_zona": geo["grupo_zona"],
                "estado": row["estado"],
                "motivo_cancelacion_logistica": (
                    None
                    if _is_missing(row["motivo_cancelacion_logistica"])
                    else row["motivo_cancelacion_logistica"]
                ),
                "ts_creacion": row["ts_creacion"],
                "ts_despacho": None if _is_missing(row["ts_despacho"]) else row["ts_despacho"],
                "ts_entrega": None if _is_missing(row["ts_entrega"]) else row["ts_entrega"],
                "fecha_creacion": fecha_creacion,
                "fecha_despacho": fecha_despacho,
                "fecha_promesa": fecha_promesa,
                "fecha_entrega": fecha_entrega,
                "es_entregado": entregado,
                "es_a_tiempo": a_tiempo,
                "es_atrasado": atrasado,
                "es_cancelado_logistica": int(row["estado"] == "cancelado_logistica"),
                "lead_time_orden_horas": (
                    _hours(row["ts_entrega"], row["ts_creacion"]) if entregado else None
                ),
                "lead_time_despacho_horas": (
                    _hours(row["ts_entrega"], row["ts_despacho"]) if entregado else None
                ),
            }
        )
    f_envios = pd.DataFrame(fact_rows)
    return {
        "d_fecha": d_fecha,
        "d_geografia": d_geografia,
        "d_centro_fulfillment": d_centro,
        "d_carrier": d_carrier,
        "d_seller": d_seller,
        "f_envios": f_envios,
        "n_silver_envios": int(len(envios)),
    }


def _rate(fact: pd.DataFrame, mask: pd.Series) -> tuple[float, int]:
    sub = fact.loc[mask]
    n = int(sub["es_entregado"].sum())
    late = int(sub["es_atrasado"].sum())
    return (late / n if n else 0.0), n


def story_observada(fact: pd.DataFrame) -> dict[str, float | int]:
    rm, n_rm = _rate(fact, fact["region_id"] == "RM")
    ext, n_ext = _rate(fact, fact["region_id"].isin(EXTREMOS))
    andes, _n_andes = _rate(fact, fact["carrier_id"] == "CAR-ANDES")
    sur, _n_sur = _rate(fact, fact["carrier_id"] == "CAR-SUR")
    sin_stock = int(
        (
            (fact["es_cancelado_logistica"] == 1)
            & (fact["motivo_cancelacion_logistica"] == "sin_stock_fc")
        ).sum()
    )
    return {
        "rm_atrasados": round(rm, 4),
        "rm_n": n_rm,
        "extremos_atrasados": round(ext, 4),
        "extremos_n": n_ext,
        "andes_atrasados": round(andes, 4),
        "sur_atrasados": round(sur, 4),
        "sin_stock_fc": sin_stock,
    }


def huerfanas(gold: dict[str, pd.DataFrame]) -> int:
    fact = gold["f_envios"]
    fechas = set(gold["d_fecha"]["fecha"])
    sellers = set(gold["d_seller"]["seller_id"])
    comunas = set(gold["d_geografia"]["comuna_id"])
    regiones = set(gold["d_geografia"]["region_id"])
    centros = set(gold["d_centro_fulfillment"]["fc_id"])
    carriers = set(gold["d_carrier"]["carrier_id"])
    n = 0
    n += int((~fact["seller_id"].isin(sellers)).sum())
    n += int((~fact["comuna_id"].isin(comunas)).sum())
    n += int((~fact["region_id"].isin(regiones)).sum())
    fc = fact["fc_id"]
    n += int((fc.notna() & ~fc.isin(centros)).sum())
    carrier = fact["carrier_id"]
    n += int((carrier.notna() & ~carrier.isin(carriers)).sum())
    for column in ("fecha_creacion", "fecha_promesa"):
        n += int((~fact[column].isin(fechas)).sum())
    for column in ("fecha_despacho", "fecha_entrega"):
        present = fact[column].notna()
        n += int((present & ~fact[column].isin(fechas)).sum())
    return n


def chequeos(gold: dict[str, pd.DataFrame]) -> list[tuple[str, object, object, bool]]:
    fact = gold["f_envios"]
    story = story_observada(fact)
    rows: list[tuple[str, object, object, bool]] = []

    def add(nombre: str, esperado: object, observado: object) -> None:
        rows.append((nombre, esperado, observado, esperado == observado))

    add("f_envios = silver.envios", gold["n_silver_envios"], int(len(fact)))
    add("envio_id unicos", int(len(fact)), int(fact["envio_id"].nunique()))
    add("huerfanas", 0, huerfanas(gold))
    add("es_a_tiempo + es_atrasado = es_entregado", 0, int(
        ((fact["es_a_tiempo"] + fact["es_atrasado"]) != fact["es_entregado"]).sum()
    ))
    add("atrasados RM", STORY["rm_atrasados"], story["rm_atrasados"])
    add("n entregados RM", STORY["rm_n"], story["rm_n"])
    add("atrasados extremos", STORY["extremos_atrasados"], story["extremos_atrasados"])
    add("n entregados extremos", STORY["extremos_n"], story["extremos_n"])
    add("atrasados CAR-ANDES", STORY["andes_atrasados"], story["andes_atrasados"])
    add("atrasados CAR-SUR", STORY["sur_atrasados"], story["sur_atrasados"])
    add("sin_stock_fc", STORY["sin_stock_fc"], story["sin_stock_fc"])
    return rows
