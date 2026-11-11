-- f_envios: 1 fila por envío. No lleva partición por fecha.
-- El sandbox vence las particiones a los 60 días según la fecha de la partición.
-- El horizonte es 2026-05-01 → 2026-10-31, así que partir el hecho por fecha
-- borraría casi todo. CLUSTER BY region_id, carrier_id no vence por fecha.
--
-- A tiempo: es_entregado = 1 y fecha_entrega <= fecha_promesa.
-- fecha_entrega = DATE(ts_entrega, 'America/Santiago'). El mismo día de la
-- promesa es a tiempo. El intradiario no cuenta.
-- es_atrasado es el complemento dentro de los entregados.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.f_envios`
CLUSTER BY region_id, carrier_id
OPTIONS (
  description="Hecho 1 fila por envío. Cluster por region_id y carrier_id, sin partición por fecha. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH base AS (
  SELECT
    e.envio_id,
    e.orden_id,
    e.seller_id,
    e.fc_id,
    e.carrier_id,
    e.comuna_destino_id AS comuna_id,
    g.region_id,
    g.grupo_zona,
    e.estado,
    e.motivo_cancelacion_logistica,
    e.ts_creacion,
    e.ts_despacho,
    e.ts_entrega,
    DATE(e.ts_creacion, 'America/Santiago') AS fecha_creacion,
    DATE(e.ts_despacho, 'America/Santiago') AS fecha_despacho,
    e.fecha_promesa,
    DATE(e.ts_entrega, 'America/Santiago') AS fecha_entrega
  FROM `meli_silver.envios` AS e
  INNER JOIN `meli_gold.d_geografia` AS g
    ON e.comuna_destino_id = g.comuna_id
)
SELECT
  envio_id,
  orden_id,
  seller_id,
  fc_id,
  carrier_id,
  comuna_id,
  region_id,
  grupo_zona,
  estado,
  motivo_cancelacion_logistica,
  ts_creacion,
  ts_despacho,
  ts_entrega,
  fecha_creacion,
  fecha_despacho,
  fecha_promesa,
  fecha_entrega,
  IF(estado = 'entregado' AND fecha_entrega IS NOT NULL, 1, 0) AS es_entregado,
  IF(
    estado = 'entregado' AND fecha_entrega IS NOT NULL AND fecha_entrega <= fecha_promesa,
    1,
    0
  ) AS es_a_tiempo,
  IF(
    estado = 'entregado' AND fecha_entrega IS NOT NULL AND fecha_entrega > fecha_promesa,
    1,
    0
  ) AS es_atrasado,
  IF(estado = 'cancelado_logistica', 1, 0) AS es_cancelado_logistica,
  IF(
    estado = 'entregado' AND fecha_entrega IS NOT NULL,
    TIMESTAMP_DIFF(ts_entrega, ts_creacion, MINUTE) / 60.0,
    NULL
  ) AS lead_time_orden_horas,
  IF(
    estado = 'entregado' AND fecha_entrega IS NOT NULL AND ts_despacho IS NOT NULL,
    TIMESTAMP_DIFF(ts_entrega, ts_despacho, MINUTE) / 60.0,
    NULL
  ) AS lead_time_despacho_horas
FROM base;
