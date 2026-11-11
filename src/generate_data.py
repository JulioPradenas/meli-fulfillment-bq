#!/usr/bin/env python3
"""
Meli Fulfillment — Paso 2: CSV sintéticos reproducibles + manifest de anomalías.

Uso:
  python src/generate_data.py
  python src/generate_data.py --dry-run

Semilla 42 y horizonte fijo (2026-05-01 → 2026-10-31). No usa date.today().
El núcleo limpio sale de un Random(seed). Las anomalías salen de otro
Random(seed), después, para no mover la historia de atrasos.

Anomalías (filas extra, el núcleo no se muta):
  fk_huerfana, fecha_nula, clave_nula, duplicado_exacto, evento_fuera_de_orden.

Escribe data/raw/*.csv (gitignored) y data/manifest.json.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bq_env import DATASET, LOCATION, NOTICE, ROOT
from contract import (
    FECHA_NULA_COL,
    PRIMARY_KEY,
    TABLE_ORDER,
    columns,
)
from csv_io import csv_path, write_table

SEED = 42
HORIZON_START = date(2026, 5, 1)
HORIZON_END = date(2026, 10, 31)
TARGET_ENVIOS = 32_000
TZ = ZoneInfo("America/Santiago")

ANOMALY_KINDS: tuple[str, ...] = (
    "fk_huerfana",
    "fecha_nula",
    "clave_nula",
    "duplicado_exacto",
    "evento_fuera_de_orden",
)

# Presupuesto fijo. Cada una suma una fila (no hay mutación in-place).
ANOMALY_BUDGET: dict[str, dict[str, int]] = {
    "regiones": {"clave_nula": 1, "duplicado_exacto": 1},
    "comunas": {"fk_huerfana": 2, "clave_nula": 1, "duplicado_exacto": 1},
    "centros_fulfillment": {"fk_huerfana": 1, "clave_nula": 1, "duplicado_exacto": 1},
    "carriers": {"clave_nula": 1, "duplicado_exacto": 1},
    "sellers": {"fk_huerfana": 2, "clave_nula": 1, "duplicado_exacto": 2},
    "ordenes": {
        "fk_huerfana": 12,
        "fecha_nula": 8,
        "clave_nula": 6,
        "duplicado_exacto": 10,
    },
    "envios": {
        "fk_huerfana": 20,
        "fecha_nula": 10,
        "clave_nula": 8,
        "duplicado_exacto": 12,
    },
    "eventos_tracking": {
        "fk_huerfana": 15,
        "fecha_nula": 10,
        "clave_nula": 8,
        "duplicado_exacto": 12,
        "evento_fuera_de_orden": 20,
    },
}

SENTINELS = {
    "seller": "SEL-HUERFANO",
    "comuna": "99999",
    "fc": "FC-HUERFANO",
    "carrier": "CAR-HUERFANO",
    "orden": "ORD-HUERFANA",
    "envio": "ENV-HUERFANO",
    "region": "REG-HUERFANA",
}

REGIONES: tuple[tuple[str, str, str], ...] = (
    ("AP", "Arica y Parinacota", "norte"),
    ("TA", "Tarapacá", "norte"),
    ("AN", "Antofagasta", "norte"),
    ("AT", "Atacama", "norte"),
    ("CO", "Coquimbo", "norte"),
    ("VS", "Valparaíso", "centro"),
    ("RM", "Metropolitana de Santiago", "centro"),
    ("LI", "O'Higgins", "centro"),
    ("ML", "Maule", "centro"),
    ("NB", "Ñuble", "sur"),
    ("BI", "Biobío", "sur"),
    ("AR", "La Araucanía", "sur"),
    ("LR", "Los Ríos", "sur"),
    ("LL", "Los Lagos", "sur"),
    ("AI", "Aysén", "austral"),
    ("MA", "Magallanes", "austral"),
)

# comuna_id CUT, nombre, region, peso de destino. Códigos públicos.
COMUNAS: tuple[tuple[str, str, str, int], ...] = (
    ("15101", "Arica", "AP", 4),
    ("01101", "Iquique", "TA", 4),
    ("01107", "Alto Hospicio", "TA", 2),
    ("02101", "Antofagasta", "AN", 6),
    ("02201", "Calama", "AN", 3),
    ("03101", "Copiapó", "AT", 3),
    ("03301", "Vallenar", "AT", 2),
    ("04101", "La Serena", "CO", 5),
    ("04102", "Coquimbo", "CO", 4),
    ("04301", "Ovalle", "CO", 2),
    ("05101", "Valparaíso", "VS", 8),
    ("05109", "Viña del Mar", "VS", 7),
    ("05801", "Quilpué", "VS", 3),
    ("05601", "San Antonio", "VS", 3),
    ("13101", "Santiago", "RM", 22),
    ("13114", "Las Condes", "RM", 8),
    ("13110", "La Florida", "RM", 10),
    ("13119", "Maipú", "RM", 12),
    ("13120", "Ñuñoa", "RM", 6),
    ("13123", "Providencia", "RM", 7),
    ("13132", "Vitacura", "RM", 4),
    ("13124", "Pudahuel", "RM", 6),
    ("13201", "Puente Alto", "RM", 11),
    ("13401", "San Bernardo", "RM", 8),
    ("13301", "Colina", "RM", 3),
    ("06101", "Rancagua", "LI", 5),
    ("06301", "San Fernando", "LI", 2),
    ("07101", "Talca", "ML", 4),
    ("07301", "Curicó", "ML", 3),
    ("07401", "Linares", "ML", 2),
    ("16101", "Chillán", "NB", 3),
    ("08101", "Concepción", "BI", 7),
    ("08110", "Talcahuano", "BI", 4),
    ("08301", "Los Ángeles", "BI", 3),
    ("09101", "Temuco", "AR", 5),
    ("14101", "Valdivia", "LR", 4),
    ("10101", "Puerto Montt", "LL", 5),
    ("10301", "Osorno", "LL", 3),
    ("10201", "Castro", "LL", 2),
    ("11101", "Coyhaique", "AI", 2),
    ("11201", "Aysén", "AI", 1),
    ("12101", "Punta Arenas", "MA", 2),
    ("12401", "Puerto Natales", "MA", 1),
)

FCS: tuple[tuple[str, str, str, str], ...] = (
    ("FC-SCL-NOR", "FC Santiago Norte", "mega", "13101"),
    ("FC-SCL-SUR", "FC Santiago Sur", "regional", "13201"),
    ("FC-VAP", "FC Valparaíso", "regional", "05101"),
    ("FC-CON", "FC Concepción", "regional", "08101"),
    ("FC-ANF", "FC Antofagasta", "regional", "02101"),
    ("FC-PMT", "FC Puerto Montt", "cross_dock", "10101"),
)

CARRIERS: tuple[tuple[str, str, str], ...] = (
    ("CAR-ANDES", "Andes Express", "paqueteria"),
    ("CAR-SUR", "Ruta Austral", "paqueteria"),
    ("CAR-MOTO", "Moto Centro", "moto"),
    ("CAR-NORTE", "Norte Cargo", "paqueteria"),
    ("CAR-DIA", "Día Cero", "same_day"),
)

# seller_id, nombre, tipo, region_origen, activo
SELLERS: tuple[tuple[str, str, str, str, str], ...] = (
    ("SEL-01", "Casa Arrayán", "pyme", "RM", "true"),
    ("SEL-02", "Taller Lo Ovalle", "pyme", "RM", "true"),
    ("SEL-03", "Marca Pacífico", "marca", "RM", "true"),
    ("SEL-04", "Botas del Mapocho", "pyme", "RM", "true"),
    ("SEL-05", "Primera Ruta", "primera_parte", "RM", "true"),
    ("SEL-06", "Hilo y Punto", "pyme", "RM", "true"),
    ("SEL-07", "Cerro Alegre", "pyme", "VS", "true"),
    ("SEL-08", "Puerto Deporte", "marca", "VS", "true"),
    ("SEL-09", "Valle Cachapoal", "pyme", "LI", "true"),
    ("SEL-10", "Talca Hogar", "pyme", "ML", "true"),
    ("SEL-11", "Biobío Outdoor", "marca", "BI", "true"),
    ("SEL-12", "Temuco Wool", "pyme", "AR", "true"),
    ("SEL-13", "Valdivia Austral", "pyme", "LR", "true"),
    ("SEL-14", "Reloncaví", "pyme", "LL", "true"),
    ("SEL-15", "Casa del Estrecho", "pyme", "MA", "true"),
    ("SEL-16", "Aysén Campo", "pyme", "AI", "true"),
    ("SEL-17", "Norte Seco", "pyme", "AN", "true"),
    ("SEL-18", "Arica Sol", "pyme", "AP", "true"),
    ("SEL-19", "Iquique Libre", "marca", "TA", "true"),
    ("SEL-20", "Atacama Kit", "pyme", "AT", "true"),
    ("SEL-21", "Serena Surf", "pyme", "CO", "true"),
    ("SEL-22", "Chillán Mesa", "pyme", "NB", "true"),
    ("SEL-23", "Operador Propio", "primera_parte", "RM", "true"),
    ("SEL-24", "Bodega Pausada", "pyme", "RM", "false"),
)

EXTREME = {"AP", "AN", "AI", "MA"}
PROMISE_DAYS = {
    "RM": 2,
    "VS": 3,
    "LI": 3,
    "ML": 3,
    "CO": 3,
    "NB": 4,
    "BI": 4,
    "AR": 4,
    "AT": 5,
    "TA": 5,
    "LR": 5,
    "LL": 5,
    "AN": 6,
    "AP": 7,
    "AI": 7,
    "MA": 8,
}
LATE_BASE = {
    "RM": 0.055,
    "VS": 0.09,
    "LI": 0.10,
    "ML": 0.11,
    "CO": 0.10,
    "NB": 0.13,
    "BI": 0.14,
    "AR": 0.16,
    "AT": 0.18,
    "TA": 0.17,
    "LR": 0.20,
    "LL": 0.22,
    "AN": 0.30,
    "AP": 0.34,
    "AI": 0.36,
    "MA": 0.40,
}
LATE_CARRIER = {
    "CAR-ANDES": -0.025,
    "CAR-SUR": 0.14,
    "CAR-MOTO": 0.05,
    "CAR-NORTE": 0.02,
    "CAR-DIA": 0.04,
}
STATUS_WEIGHTS = (
    ("creado", 2),
    ("en_preparacion", 3),
    ("despachado", 3),
    ("en_transito", 5),
    ("entregado", 76),
    ("cancelado_logistica", 7),
    ("cancelado_no_logistica", 2),
    ("devuelto", 2),
)
AFTER_SHIP_MOTIVOS = {"carrier_no_retira", "direccion_invalida", "extravio"}
FK_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "comunas": (("region", SENTINELS["region"]),),
    "centros_fulfillment": (("comuna_id", SENTINELS["comuna"]),),
    "sellers": (("region_origen", SENTINELS["region"]),),
    "ordenes": (
        ("seller_id", SENTINELS["seller"]),
        ("comuna_destino_id", SENTINELS["comuna"]),
    ),
    "envios": (
        ("orden_id", SENTINELS["orden"]),
        ("seller_id", SENTINELS["seller"]),
        ("fc_id", SENTINELS["fc"]),
        ("carrier_id", SENTINELS["carrier"]),
        ("comuna_destino_id", SENTINELS["comuna"]),
    ),
    "eventos_tracking": (("envio_id", SENTINELS["envio"]),),
}
PK_PREFIX = {
    "regiones": "RG",
    "comunas": "COM",
    "centros_fulfillment": "FCX",
    "carriers": "CARX",
    "sellers": "SELX",
    "ordenes": "ORDX",
    "envios": "ENVX",
    "eventos_tracking": "EVTX",
}

CLEAN_ID = {
    "ordenes": re.compile(r"ORD-\d{6}"),
    "envios": re.compile(r"ENV-\d{6}"),
}


@dataclass(frozen=True)
class Generation:
    tables: dict[str, list[dict[str, str]]]
    manifest: dict


def stamp(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def format_ts(dt: datetime) -> str:
    base = dt.strftime("%Y-%m-%d %H:%M:%S")
    off = dt.strftime("%z")
    return f"{base}{off[:3]}:{off[3:]}"


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S%z")


def _blank_budget() -> dict[str, dict[str, int]]:
    return {
        table: {kind: 0 for kind in ANOMALY_KINDS} for table in TABLE_ORDER
    }


def _sample(rows: list[dict[str, str]], n: int, rng: random.Random) -> list[dict[str, str]]:
    if n <= 0:
        return []
    if n > len(rows):
        raise ValueError(f"presupuesto de anomalías {n} > filas limpias {len(rows)}")
    return [dict(rows[i]) for i in rng.sample(range(len(rows)), n)]


def late_probability(region: str, carrier: str) -> float:
    base = LATE_BASE[region] + LATE_CARRIER.get(carrier, 0.0)
    return min(0.62, max(0.02, base))


def choose_carrier(region: str, rng: random.Random) -> str:
    if region in {"RM", "VS"} and rng.random() < 0.10:
        return "CAR-DIA"
    if region == "RM" and rng.random() < 0.22:
        return "CAR-MOTO"
    if region in {"AI", "MA", "LL", "LR"}:
        return rng.choices(["CAR-SUR", "CAR-ANDES"], weights=[78, 22], k=1)[0]
    if region in {"AP", "AN", "TA", "AT"}:
        return rng.choices(
            ["CAR-NORTE", "CAR-ANDES", "CAR-SUR"], weights=[62, 28, 10], k=1
        )[0]
    if region in {"RM", "VS"}:
        return rng.choices(
            ["CAR-ANDES", "CAR-SUR", "CAR-NORTE"], weights=[72, 16, 12], k=1
        )[0]
    return rng.choices(
        ["CAR-ANDES", "CAR-SUR", "CAR-NORTE"], weights=[55, 30, 15], k=1
    )[0]


def choose_fc(region: str, tipo: str, rng: random.Random) -> str:
    if tipo == "flex":
        return ""
    if tipo == "cross_dock":
        return "FC-PMT" if region in {"LR", "LL", "AI", "MA", "AR"} else "FC-SCL-SUR"
    if region == "RM":
        return rng.choices(["FC-SCL-NOR", "FC-SCL-SUR"], weights=[68, 32], k=1)[0]
    if region in {"VS", "CO"}:
        return "FC-VAP"
    if region in {"LI", "ML"}:
        return "FC-SCL-SUR"
    if region in {"NB", "BI", "AR"}:
        return "FC-CON"
    if region in {"LR", "LL", "AI", "MA"}:
        return "FC-PMT"
    return "FC-ANF"


def choose_motivo(region: str, fc_id: str, carrier: str, rng: random.Random) -> str:
    weights = {
        "sin_stock_fc": 42,
        "capacidad_fc": 12,
        "dano_en_preparacion": 8,
        "carrier_no_retira": 14,
        "direccion_invalida": 12,
        "extravio": 12,
    }
    if fc_id == "FC-ANF":
        weights["sin_stock_fc"] += 30
    if fc_id == "FC-SCL-SUR":
        weights["capacidad_fc"] += 12
    if carrier == "CAR-SUR":
        weights["carrier_no_retira"] += 16
        weights["extravio"] += 6
    if region in EXTREME:
        weights["direccion_invalida"] += 14
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def choose_status(rng: random.Random) -> str:
    labels, weights = zip(*STATUS_WEIGHTS)
    return rng.choices(list(labels), weights=list(weights), k=1)[0]


def place_times(
    *,
    fecha_creacion: date,
    fecha_entrega: date | None,
    needs_dispatch: bool,
    rng: random.Random,
) -> tuple[datetime, datetime | None, datetime | None]:
    ts_creacion = stamp(fecha_creacion, 9, rng.randint(0, 25))
    if fecha_entrega is None:
        if not needs_dispatch:
            return ts_creacion, None, None
        return ts_creacion, ts_creacion + timedelta(hours=rng.randint(6, 22)), None
    ts_entrega = stamp(fecha_entrega, 18, rng.randint(0, 25))
    if ts_entrega <= ts_creacion + timedelta(hours=6):
        ts_creacion = stamp(fecha_creacion, 8, 0)
        ts_entrega = stamp(fecha_entrega, 19, 0)
    span = (ts_entrega - ts_creacion).total_seconds()
    ts_despacho = ts_creacion + timedelta(seconds=span * 0.35)
    return ts_creacion, ts_despacho, ts_entrega


def _masters() -> dict[str, list[dict[str, str]]]:
    regiones = [
        {"region": code, "region_nombre": name, "zona": zona}
        for code, name, zona in REGIONES
    ]
    comunas = [
        {"comuna_id": cid, "comuna_nombre": name, "region": region}
        for cid, name, region, _weight in COMUNAS
    ]
    fcs = [
        {
            "fc_id": fid,
            "fc_nombre": name,
            "tipo_fc": tipo,
            "comuna_id": comuna,
            "activo": "true",
        }
        for fid, name, tipo, comuna in FCS
    ]
    carriers = [
        {
            "carrier_id": cid,
            "carrier_nombre": name,
            "tipo_servicio": tipo,
            "activo": "true",
        }
        for cid, name, tipo in CARRIERS
    ]
    sellers = [
        {
            "seller_id": sid,
            "seller_nombre": name,
            "tipo_seller": tipo,
            "region_origen": region,
            "activo": activo,
        }
        for sid, name, tipo, region, activo in SELLERS
    ]
    return {
        "regiones": regiones,
        "comunas": comunas,
        "centros_fulfillment": fcs,
        "carriers": carriers,
        "sellers": sellers,
    }


def _event_plan(envio: dict[str, str], rng: random.Random) -> list[tuple[str, datetime, bool, bool]]:
    ts0 = parse_ts(envio["ts_creacion"])
    plan: list[tuple[str, datetime, bool, bool]] = [("creado", ts0, False, False)]
    estado = envio["estado"]
    if estado == "creado":
        return plan
    ts_prep = ts0 + timedelta(hours=2, minutes=rng.randint(0, 20))
    plan.append(("en_preparacion", ts_prep, False, False))
    if estado == "en_preparacion":
        return plan
    if not envio["ts_despacho"]:
        code = (
            "cancelado_logistica"
            if estado == "cancelado_logistica"
            else "cancelado_no_logistica"
        )
        plan.append((code, ts_prep + timedelta(hours=1, minutes=rng.randint(5, 40)), False, False))
        return plan
    ts_d = parse_ts(envio["ts_despacho"])
    plan.append(("despachado", ts_d, True, False))
    ts_tr = ts_d + timedelta(hours=1, minutes=rng.randint(5, 40))
    plan.append(("en_transito", ts_tr, True, True))
    if estado == "entregado":
        ts_e = parse_ts(envio["ts_entrega"])
        gap = ts_e - ts_tr
        late = envio["ts_entrega"][:10] > envio["fecha_promesa"]
        p_intento = 0.40 if late else 0.07
        if gap > timedelta(hours=4) and rng.random() < p_intento:
            n_int = 2 if rng.random() < 0.22 else 1
            for k in range(n_int):
                frac = 0.30 + 0.22 * k
                ts_i = ts_tr + timedelta(seconds=gap.total_seconds() * frac)
                if ts_i < ts_e:
                    plan.append(("intento_fallido", ts_i, True, True))
        plan.append(("entregado", ts_e, True, True))
    elif estado == "devuelto":
        plan.append(("devuelto", ts_tr + timedelta(hours=rng.randint(8, 30)), True, True))
    elif estado == "cancelado_logistica":
        plan.append(
            ("cancelado_logistica", ts_tr + timedelta(hours=rng.randint(2, 16)), True, True)
        )
    return plan


def build_clean(rng: random.Random) -> dict[str, list[dict[str, str]]]:
    tables = _masters()
    active_sellers = [s["seller_id"] for s in tables["sellers"] if s["activo"] == "true"]
    comuna_weights = [weight for _cid, _name, _region, weight in COMUNAS]
    n_days = (HORIZON_END - HORIZON_START).days + 1

    ordenes: list[dict[str, str]] = []
    envios: list[dict[str, str]] = []
    n_envio = 0
    n_orden = 0
    while n_envio < TARGET_ENVIOS:
        n_parts = 2 if (rng.random() < 0.12 and n_envio + 2 <= TARGET_ENVIOS) else 1
        n_orden += 1
        orden_id = f"ORD-{n_orden:06d}"
        comuna = rng.choices(COMUNAS, weights=comuna_weights, k=1)[0]
        region = comuna[2]
        fecha_creacion = HORIZON_START + timedelta(days=rng.randrange(n_days))
        seller_ids = [rng.choice(active_sellers) for _ in range(n_parts)]
        # La hora de la orden se fija con el primer envío (mismo timestamp).
        first_ts: str | None = None
        for part, seller_id in enumerate(seller_ids):
            n_envio += 1
            estado = choose_status(rng)
            motivo = ""
            if estado == "cancelado_logistica":
                # FC y carrier se eligen antes del motivo para poder sesgar la causa.
                tipo = rng.choices(
                    ["full", "flex", "colecta", "cross_dock"],
                    weights=[68, 18, 8, 6],
                    k=1,
                )[0]
                fc_id = choose_fc(region, tipo, rng)
                carrier = choose_carrier(region, rng)
                motivo = choose_motivo(region, fc_id, carrier, rng)
                needs_dispatch = motivo in AFTER_SHIP_MOTIVOS
                if not needs_dispatch:
                    carrier = ""
            else:
                tipo = rng.choices(
                    ["full", "flex", "colecta", "cross_dock"],
                    weights=[68, 18, 8, 6],
                    k=1,
                )[0]
                fc_id = choose_fc(region, tipo, rng)
                needs_dispatch = estado in {
                    "despachado",
                    "en_transito",
                    "entregado",
                    "devuelto",
                }
                carrier = choose_carrier(region, rng) if needs_dispatch else ""

            promise_days = PROMISE_DAYS[region] + (1 if tipo == "flex" else 0)
            if carrier == "CAR-DIA":
                promise_days = 0
            fecha_promesa = fecha_creacion + timedelta(days=promise_days)
            fecha_entrega: date | None = None
            if estado == "entregado":
                if rng.random() < late_probability(region, carrier):
                    extra = rng.randint(2, 7) if region in EXTREME else rng.randint(1, 4)
                    fecha_entrega = fecha_promesa + timedelta(days=extra)
                else:
                    back = 0 if promise_days == 0 else rng.choice((0, 0, 0, 1))
                    fecha_entrega = fecha_promesa - timedelta(days=back)
                    if fecha_entrega < fecha_creacion:
                        fecha_entrega = fecha_creacion
            ts_creacion, ts_despacho, ts_entrega = place_times(
                fecha_creacion=fecha_creacion,
                fecha_entrega=fecha_entrega,
                needs_dispatch=needs_dispatch,
                rng=rng,
            )
            if first_ts is None:
                first_ts = format_ts(ts_creacion)
            envios.append(
                {
                    "envio_id": f"ENV-{n_envio:06d}",
                    "orden_id": orden_id,
                    "seller_id": seller_id,
                    "fc_id": fc_id,
                    "carrier_id": carrier,
                    "comuna_destino_id": comuna[0],
                    "tipo_logistica": tipo,
                    "ts_creacion": format_ts(ts_creacion),
                    "ts_despacho": format_ts(ts_despacho) if ts_despacho else "",
                    "ts_entrega": format_ts(ts_entrega) if ts_entrega else "",
                    "fecha_promesa": fecha_promesa.isoformat(),
                    "estado": estado,
                    "motivo_cancelacion_logistica": motivo,
                }
            )
        ordenes.append(
            {
                "orden_id": orden_id,
                "seller_id": seller_ids[0],
                "ts_creacion": first_ts or "",
                "comuna_destino_id": comuna[0],
                "estado_orden": "pagada",
            }
        )

    by_order: dict[str, list[dict[str, str]]] = {}
    for envio in envios:
        by_order.setdefault(envio["orden_id"], []).append(envio)
    terminal = {"entregado", "cancelado_logistica", "cancelado_no_logistica", "devuelto"}
    for orden in ordenes:
        parts = by_order[orden["orden_id"]]
        estados = {p["estado"] for p in parts}
        if estados <= {"cancelado_no_logistica"}:
            orden["estado_orden"] = "cancelada_comprador"
        elif estados <= terminal:
            orden["estado_orden"] = "cerrada"
        else:
            orden["estado_orden"] = "pagada"

    events: list[dict[str, str]] = []
    seq = 0
    for envio in envios:
        for codigo, ts, with_carrier, with_comuna in _event_plan(envio, rng):
            seq += 1
            events.append(
                {
                    "evento_id": f"EVT-{seq:08d}",
                    "envio_id": envio["envio_id"],
                    "ts_evento": format_ts(ts),
                    "codigo_evento": codigo,
                    "fc_id": envio["fc_id"] if codigo in {"creado", "en_preparacion", "despachado"} else "",
                    "carrier_id": envio["carrier_id"] if with_carrier else "",
                    "comuna_id": envio["comuna_destino_id"] if with_comuna else "",
                }
            )

    tables["ordenes"] = ordenes
    tables["envios"] = envios
    tables["eventos_tracking"] = events
    return tables


def _inject_table(
    rows: list[dict[str, str]],
    *,
    table: str,
    budget: dict[str, int],
    rng: random.Random,
    applied: dict[str, int],
    fk_patch=None,
) -> list[dict[str, str]]:
    extras: list[dict[str, str]] = []
    pk = PRIMARY_KEY[table]
    prefix = PK_PREFIX[table]

    n = budget.get("duplicado_exacto", 0)
    extras.extend(_sample(rows, n, rng))
    applied["duplicado_exacto"] = n

    n = budget.get("fk_huerfana", 0)
    options = FK_OPTIONS.get(table, ())
    if n and not options:
        raise ValueError(f"{table} no tiene FK para fk_huerfana")
    for i, row in enumerate(_sample(rows, n, rng)):
        col, sentinel = options[i % len(options)]
        row[pk] = f"{prefix}-FK-{i:04d}"
        row[col] = sentinel
        if fk_patch is not None:
            fk_patch(row)
        extras.append(row)
    applied["fk_huerfana"] = n

    n = budget.get("fecha_nula", 0)
    fecha_col = FECHA_NULA_COL.get(table)
    if n and not fecha_col:
        raise ValueError(f"{table} no tiene columna de fecha_nula")
    for i, row in enumerate(_sample(rows, n, rng)):
        row[pk] = f"{prefix}-FN-{i:04d}"
        row[fecha_col or ""] = ""
        extras.append(row)
    applied["fecha_nula"] = n

    n = budget.get("clave_nula", 0)
    for row in _sample(rows, n, rng):
        row[pk] = ""
        extras.append(row)
    applied["clave_nula"] = n
    return rows + extras


def inject_anomalies(
    clean: dict[str, list[dict[str, str]]],
    rng: random.Random,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, dict[str, int]]]:
    applied = _blank_budget()
    tables: dict[str, list[dict[str, str]]] = {}
    for table in TABLE_ORDER:
        if table == "eventos_tracking":
            continue
        budget = ANOMALY_BUDGET.get(table, {})
        tables[table] = _inject_table(
            clean[table],
            table=table,
            budget=budget,
            rng=rng,
            applied=applied[table],
        )

    events = list(clean["eventos_tracking"])
    ev_applied = applied["eventos_tracking"]
    budget = ANOMALY_BUDGET["eventos_tracking"]
    def _event_fk_patch(row: dict[str, str]) -> None:
        # Todos cuelgan de ENV-HUERFANO. Si se deja el código original, un
        # entregado y un despachado de envíos distintos arman un fuera-de-orden
        # accidental y el conteo deja de ser el presupuesto.
        row["codigo_evento"] = "creado"

    events = _inject_table(
        events,
        table="eventos_tracking",
        budget=budget,
        rng=rng,
        applied=ev_applied,
        fk_patch=_event_fk_patch,
    )
    # _inject_table ya sumó evento_fuera_de_orden = 0 porque no está en su lógica.
    n = budget.get("evento_fuera_de_orden", 0)
    despacho: dict[str, str] = {}
    entregado: dict[str, dict[str, str]] = {}
    for ev in clean["eventos_tracking"]:
        if ev["codigo_evento"] == "despachado" and ev["ts_evento"]:
            despacho.setdefault(ev["envio_id"], ev["ts_evento"])
        elif ev["codigo_evento"] == "entregado" and ev["envio_id"] not in entregado:
            entregado[ev["envio_id"]] = ev
    pool = [
        eid
        for eid, _ts in despacho.items()
        if CLEAN_ID["envios"].fullmatch(eid) and eid in entregado
    ]
    if n > len(pool):
        raise ValueError(f"evento_fuera_de_orden {n} > envíos elegibles {len(pool)}")
    for i, eid in enumerate(rng.sample(pool, n)):
        row = dict(entregado[eid])
        row["evento_id"] = f"EVT-OOO-{i:04d}"
        row["codigo_evento"] = "entregado"
        row["ts_evento"] = format_ts(parse_ts(despacho[eid]) - timedelta(hours=3))
        events.append(row)
    ev_applied["evento_fuera_de_orden"] = n
    tables["eventos_tracking"] = events
    return tables, applied


def build_manifest(
    *,
    clean_counts: dict[str, int],
    tables: dict[str, list[dict[str, str]]],
    anomalies: dict[str, dict[str, int]],
) -> dict:
    return {
        "notice": NOTICE,
        "seed": SEED,
        "horizon_start": HORIZON_START.isoformat(),
        "horizon_end": HORIZON_END.isoformat(),
        "timezone": "America/Santiago",
        "dataset": DATASET,
        "location": LOCATION,
        "clean_counts": {table: clean_counts[table] for table in TABLE_ORDER},
        "row_counts": {table: len(tables[table]) for table in TABLE_ORDER},
        "anomalies": {table: dict(anomalies[table]) for table in TABLE_ORDER},
        "note": (
            "row_counts es el total bronze (lo que debe coincidir con num_rows). "
            "anomalies cuenta filas extra inyectadas, por tabla y tipo. "
            "row_counts = clean_counts + suma de anomalies de esa tabla."
        ),
    }


def generate(seed: int = SEED) -> Generation:
    clean = build_clean(random.Random(seed))
    clean_counts = {table: len(clean[table]) for table in TABLE_ORDER}
    tables, anomalies = inject_anomalies(clean, random.Random(seed))
    manifest = build_manifest(
        clean_counts=clean_counts, tables=tables, anomalies=anomalies
    )
    return Generation(tables=tables, manifest=manifest)


def story_lines(tables: dict[str, list[dict[str, str]]]) -> list[str]:
    """Resumen de la historia sobre el núcleo limpio (ids ENV-######, sin duplicar)."""
    region_of = {
        row["comuna_id"]: row["region"]
        for row in tables["comunas"]
        if row["comuna_id"].isdigit() and len(row["comuna_id"]) == 5
    }
    seen: set[str] = set()
    entregados: list[tuple[str, str, bool]] = []
    motivos: Counter[str] = Counter()
    estados: Counter[str] = Counter()
    for envio in tables["envios"]:
        eid = envio["envio_id"]
        if not CLEAN_ID["envios"].fullmatch(eid) or eid in seen:
            continue
        seen.add(eid)
        estados[envio["estado"]] += 1
        if envio["estado"] == "cancelado_logistica":
            motivos[envio["motivo_cancelacion_logistica"]] += 1
        if envio["estado"] != "entregado" or not envio["ts_entrega"] or not envio["fecha_promesa"]:
            continue
        region = region_of.get(envio["comuna_destino_id"], "?")
        late = envio["ts_entrega"][:10] > envio["fecha_promesa"]
        entregados.append((region, envio["carrier_id"], late))

    def rate(pred) -> tuple[float, int]:
        rows = [late for region, carrier, late in entregados if pred(region, carrier)]
        if not rows:
            return 0.0, 0
        return sum(rows) / len(rows), len(rows)

    lines = [f"envios_limpios={len(seen)} entregados={len(entregados)}"]
    lines.append("estados_limpios=" + ", ".join(f"{k}:{v}" for k, v in sorted(estados.items())))
    for label, pred in (
        ("RM", lambda r, _c: r == "RM"),
        ("extremos_AP_AN_AI_MA", lambda r, _c: r in EXTREME),
        ("CAR-ANDES", lambda _r, c: c == "CAR-ANDES"),
        ("CAR-SUR", lambda _r, c: c == "CAR-SUR"),
    ):
        pct, n = rate(pred)
        lines.append(f"atrasados {label}={pct:.4f} n={n}")
    lines.append(
        "motivos=" + ", ".join(f"{k}:{v}" for k, v in sorted(motivos.items()))
    )
    return lines


def write_outputs(gen: Generation, raw_dir: Path, manifest_path: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLE_ORDER:
        write_table(csv_path(raw_dir, table), table, gen.tables[table])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(gen.manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera CSV sintéticos de fulfillment y data/manifest.json (seed 42)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Construye en memoria y reporta conteos; no escribe CSV ni manifest.",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifest.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gen = generate(args.seed)
    print(
        f"seed={args.seed} horizon={HORIZON_START.isoformat()}→{HORIZON_END.isoformat()} "
        f"timezone=America/Santiago"
    )
    print(f"dataset={DATASET} location={LOCATION}")
    for table in TABLE_ORDER:
        clean_n = gen.manifest["clean_counts"][table]
        total = gen.manifest["row_counts"][table]
        extra = total - clean_n
        print(f"  {table:22} clean={clean_n:7d}  bronze={total:7d}  anomalias=+{extra}")
    print("anomalies:")
    for table in TABLE_ORDER:
        parts = [
            f"{kind}={gen.manifest['anomalies'][table][kind]}"
            for kind in ANOMALY_KINDS
            if gen.manifest["anomalies"][table][kind]
        ]
        if parts:
            print(f"  {table}: {', '.join(parts)}")
    for line in story_lines(gen.tables):
        print(f"story {line}")
    # Toca columns para que un typo de contrato reviente antes de escribir.
    for table in TABLE_ORDER:
        missing = [col for col in columns(table) if col not in gen.tables[table][0]]
        if missing:
            raise SystemExit(f"{table} sin columnas {missing}")
    if args.dry_run:
        print("dry-run: no se escribieron CSV ni manifest.")
        return 0
    write_outputs(gen, args.output_dir, args.manifest)
    print(f"wrote {args.output_dir}/<tabla>.csv")
    print(f"wrote {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
