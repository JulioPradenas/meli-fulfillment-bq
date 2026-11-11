-- meli_silver.envios y meli_silver.q_envios
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.envios`
OPTIONS (
  description="Silver envios. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.envios`
),
raw AS (
  SELECT
    src.envio_id AS raw_envio_id,
    src.orden_id AS raw_orden_id,
    src.seller_id AS raw_seller_id,
    src.fc_id AS raw_fc_id,
    src.carrier_id AS raw_carrier_id,
    src.comuna_destino_id AS raw_comuna_destino_id,
    src.tipo_logistica AS raw_tipo_logistica,
    src.ts_creacion AS raw_ts_creacion,
    src.ts_despacho AS raw_ts_despacho,
    src.ts_entrega AS raw_ts_entrega,
    src.fecha_promesa AS raw_fecha_promesa,
    src.estado AS raw_estado,
    src.motivo_cancelacion_logistica AS raw_motivo_cancelacion_logistica,
    NULLIF(TRIM(CAST(src.envio_id AS STRING)), '') AS envio_id,
    NULLIF(TRIM(CAST(src.orden_id AS STRING)), '') AS orden_id,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.fc_id AS STRING)), '') AS fc_id,
    NULLIF(TRIM(CAST(src.carrier_id AS STRING)), '') AS carrier_id,
    NULLIF(TRIM(CAST(src.comuna_destino_id AS STRING)), '') AS comuna_destino_id,
    NULLIF(LOWER(TRIM(CAST(src.tipo_logistica AS STRING))), '') AS tipo_logistica,
    NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS ts_creacion_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS TIMESTAMP) AS ts_creacion,
    NULLIF(TRIM(CAST(src.ts_despacho AS STRING)), '') AS ts_despacho_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_despacho AS STRING)), '') AS TIMESTAMP) AS ts_despacho,
    NULLIF(TRIM(CAST(src.ts_entrega AS STRING)), '') AS ts_entrega_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_entrega AS STRING)), '') AS TIMESTAMP) AS ts_entrega,
    NULLIF(TRIM(CAST(src.fecha_promesa AS STRING)), '') AS fecha_promesa_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_promesa AS STRING)), '') AS DATE) AS fecha_promesa,
    NULLIF(LOWER(TRIM(CAST(src.estado AS STRING))), '') AS estado,
    NULLIF(LOWER(TRIM(CAST(src.motivo_cancelacion_logistica AS STRING))), '') AS motivo_cancelacion_logistica
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) OR (ts_despacho_txt IS NOT NULL AND ts_despacho IS NULL) OR (ts_entrega_txt IS NOT NULL AND ts_entrega IS NULL) OR (fecha_promesa_txt IS NOT NULL AND fecha_promesa IS NULL) THEN 'cast_fallido'
      WHEN envio_id IS NULL OR orden_id IS NULL OR seller_id IS NULL OR comuna_destino_id IS NULL OR tipo_logistica IS NULL OR ts_creacion IS NULL OR fecha_promesa IS NULL OR estado IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'SAFE_CAST falló en ts_creacion'
      WHEN (ts_despacho_txt IS NOT NULL AND ts_despacho IS NULL) THEN 'SAFE_CAST falló en ts_despacho'
      WHEN (ts_entrega_txt IS NOT NULL AND ts_entrega IS NULL) THEN 'SAFE_CAST falló en ts_entrega'
      WHEN (fecha_promesa_txt IS NOT NULL AND fecha_promesa IS NULL) THEN 'SAFE_CAST falló en fecha_promesa'
      WHEN envio_id IS NULL THEN 'envio_id vacío'
      WHEN orden_id IS NULL THEN 'orden_id vacío'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN comuna_destino_id IS NULL THEN 'comuna_destino_id vacío'
      WHEN tipo_logistica IS NULL THEN 'tipo_logistica vacío'
      WHEN ts_creacion IS NULL THEN 'ts_creacion vacío'
      WHEN fecha_promesa IS NULL THEN 'fecha_promesa vacío'
      WHEN estado IS NULL THEN 'estado vacío'
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
        PARTITION BY IF(motivo_base IS NULL, envio_id, CAST(NULL AS STRING))
        ORDER BY orden_id, seller_id, fc_id, carrier_id, comuna_destino_id, tipo_logistica, ts_creacion, ts_despacho, ts_entrega, fecha_promesa, estado, motivo_cancelacion_logistica
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
      WHEN ranked.orden_id IS NOT NULL AND fk_ordenes_orden_id.orden_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL AND ranked.ts_entrega < ranked.ts_despacho THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por envio_id'
      WHEN ranked.orden_id IS NOT NULL AND fk_ordenes_orden_id.orden_id IS NULL THEN 'orden_id no está en silver.ordenes'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'seller_id no está en silver.sellers'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fc_id no está en silver.centros_fulfillment'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'carrier_id no está en silver.carriers'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'comuna_destino_id no está en silver.comunas'
      WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL AND ranked.ts_entrega < ranked.ts_despacho THEN 'ts_entrega anterior a ts_despacho'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.ordenes` AS fk_ordenes_orden_id
    ON ranked.orden_id = fk_ordenes_orden_id.orden_id
  LEFT JOIN `meli_silver.sellers` AS fk_sellers_seller_id
    ON ranked.seller_id = fk_sellers_seller_id.seller_id
  LEFT JOIN `meli_silver.centros_fulfillment` AS fk_centros_fulfillment_fc_id
    ON ranked.fc_id = fk_centros_fulfillment_fc_id.fc_id
  LEFT JOIN `meli_silver.carriers` AS fk_carriers_carrier_id
    ON ranked.carrier_id = fk_carriers_carrier_id.carrier_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_destino_id
    ON ranked.comuna_destino_id = fk_comunas_comuna_destino_id.comuna_id
)
SELECT
  envio_id,
  orden_id,
  seller_id,
  fc_id,
  carrier_id,
  comuna_destino_id,
  tipo_logistica,
  ts_creacion,
  ts_despacho,
  ts_entrega,
  fecha_promesa,
  estado,
  motivo_cancelacion_logistica
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY envio_id
  ORDER BY orden_id, seller_id, fc_id, carrier_id, comuna_destino_id, tipo_logistica, ts_creacion, ts_despacho, ts_entrega, fecha_promesa, estado, motivo_cancelacion_logistica
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_envios`
OPTIONS (
  description="Cuarentena de envios. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.envios`
),
raw AS (
  SELECT
    src.envio_id AS raw_envio_id,
    src.orden_id AS raw_orden_id,
    src.seller_id AS raw_seller_id,
    src.fc_id AS raw_fc_id,
    src.carrier_id AS raw_carrier_id,
    src.comuna_destino_id AS raw_comuna_destino_id,
    src.tipo_logistica AS raw_tipo_logistica,
    src.ts_creacion AS raw_ts_creacion,
    src.ts_despacho AS raw_ts_despacho,
    src.ts_entrega AS raw_ts_entrega,
    src.fecha_promesa AS raw_fecha_promesa,
    src.estado AS raw_estado,
    src.motivo_cancelacion_logistica AS raw_motivo_cancelacion_logistica,
    NULLIF(TRIM(CAST(src.envio_id AS STRING)), '') AS envio_id,
    NULLIF(TRIM(CAST(src.orden_id AS STRING)), '') AS orden_id,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.fc_id AS STRING)), '') AS fc_id,
    NULLIF(TRIM(CAST(src.carrier_id AS STRING)), '') AS carrier_id,
    NULLIF(TRIM(CAST(src.comuna_destino_id AS STRING)), '') AS comuna_destino_id,
    NULLIF(LOWER(TRIM(CAST(src.tipo_logistica AS STRING))), '') AS tipo_logistica,
    NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS ts_creacion_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS TIMESTAMP) AS ts_creacion,
    NULLIF(TRIM(CAST(src.ts_despacho AS STRING)), '') AS ts_despacho_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_despacho AS STRING)), '') AS TIMESTAMP) AS ts_despacho,
    NULLIF(TRIM(CAST(src.ts_entrega AS STRING)), '') AS ts_entrega_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_entrega AS STRING)), '') AS TIMESTAMP) AS ts_entrega,
    NULLIF(TRIM(CAST(src.fecha_promesa AS STRING)), '') AS fecha_promesa_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_promesa AS STRING)), '') AS DATE) AS fecha_promesa,
    NULLIF(LOWER(TRIM(CAST(src.estado AS STRING))), '') AS estado,
    NULLIF(LOWER(TRIM(CAST(src.motivo_cancelacion_logistica AS STRING))), '') AS motivo_cancelacion_logistica
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) OR (ts_despacho_txt IS NOT NULL AND ts_despacho IS NULL) OR (ts_entrega_txt IS NOT NULL AND ts_entrega IS NULL) OR (fecha_promesa_txt IS NOT NULL AND fecha_promesa IS NULL) THEN 'cast_fallido'
      WHEN envio_id IS NULL OR orden_id IS NULL OR seller_id IS NULL OR comuna_destino_id IS NULL OR tipo_logistica IS NULL OR ts_creacion IS NULL OR fecha_promesa IS NULL OR estado IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'SAFE_CAST falló en ts_creacion'
      WHEN (ts_despacho_txt IS NOT NULL AND ts_despacho IS NULL) THEN 'SAFE_CAST falló en ts_despacho'
      WHEN (ts_entrega_txt IS NOT NULL AND ts_entrega IS NULL) THEN 'SAFE_CAST falló en ts_entrega'
      WHEN (fecha_promesa_txt IS NOT NULL AND fecha_promesa IS NULL) THEN 'SAFE_CAST falló en fecha_promesa'
      WHEN envio_id IS NULL THEN 'envio_id vacío'
      WHEN orden_id IS NULL THEN 'orden_id vacío'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN comuna_destino_id IS NULL THEN 'comuna_destino_id vacío'
      WHEN tipo_logistica IS NULL THEN 'tipo_logistica vacío'
      WHEN ts_creacion IS NULL THEN 'ts_creacion vacío'
      WHEN fecha_promesa IS NULL THEN 'fecha_promesa vacío'
      WHEN estado IS NULL THEN 'estado vacío'
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
        PARTITION BY IF(motivo_base IS NULL, envio_id, CAST(NULL AS STRING))
        ORDER BY orden_id, seller_id, fc_id, carrier_id, comuna_destino_id, tipo_logistica, ts_creacion, ts_despacho, ts_entrega, fecha_promesa, estado, motivo_cancelacion_logistica
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
      WHEN ranked.orden_id IS NOT NULL AND fk_ordenes_orden_id.orden_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL AND ranked.ts_entrega < ranked.ts_despacho THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por envio_id'
      WHEN ranked.orden_id IS NOT NULL AND fk_ordenes_orden_id.orden_id IS NULL THEN 'orden_id no está en silver.ordenes'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'seller_id no está en silver.sellers'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fc_id no está en silver.centros_fulfillment'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'carrier_id no está en silver.carriers'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'comuna_destino_id no está en silver.comunas'
      WHEN ranked.ts_entrega IS NOT NULL AND ranked.ts_despacho IS NOT NULL AND ranked.ts_entrega < ranked.ts_despacho THEN 'ts_entrega anterior a ts_despacho'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.ordenes` AS fk_ordenes_orden_id
    ON ranked.orden_id = fk_ordenes_orden_id.orden_id
  LEFT JOIN `meli_silver.sellers` AS fk_sellers_seller_id
    ON ranked.seller_id = fk_sellers_seller_id.seller_id
  LEFT JOIN `meli_silver.centros_fulfillment` AS fk_centros_fulfillment_fc_id
    ON ranked.fc_id = fk_centros_fulfillment_fc_id.fc_id
  LEFT JOIN `meli_silver.carriers` AS fk_carriers_carrier_id
    ON ranked.carrier_id = fk_carriers_carrier_id.carrier_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_destino_id
    ON ranked.comuna_destino_id = fk_comunas_comuna_destino_id.comuna_id
)
SELECT
  raw_envio_id AS envio_id,
  raw_orden_id AS orden_id,
  raw_seller_id AS seller_id,
  raw_fc_id AS fc_id,
  raw_carrier_id AS carrier_id,
  raw_comuna_destino_id AS comuna_destino_id,
  raw_tipo_logistica AS tipo_logistica,
  raw_ts_creacion AS ts_creacion,
  raw_ts_despacho AS ts_despacho,
  raw_ts_entrega AS ts_entrega,
  raw_fecha_promesa AS fecha_promesa,
  raw_estado AS estado,
  raw_motivo_cancelacion_logistica AS motivo_cancelacion_logistica,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
