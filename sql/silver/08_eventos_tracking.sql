-- meli_silver.eventos_tracking y meli_silver.q_eventos_tracking
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.eventos_tracking`
OPTIONS (
  description="Silver eventos_tracking. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.eventos_tracking`
),
raw AS (
  SELECT
    src.evento_id AS raw_evento_id,
    src.envio_id AS raw_envio_id,
    src.ts_evento AS raw_ts_evento,
    src.codigo_evento AS raw_codigo_evento,
    src.fc_id AS raw_fc_id,
    src.carrier_id AS raw_carrier_id,
    src.comuna_id AS raw_comuna_id,
    NULLIF(TRIM(CAST(src.evento_id AS STRING)), '') AS evento_id,
    NULLIF(TRIM(CAST(src.envio_id AS STRING)), '') AS envio_id,
    NULLIF(TRIM(CAST(src.ts_evento AS STRING)), '') AS ts_evento_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_evento AS STRING)), '') AS TIMESTAMP) AS ts_evento,
    NULLIF(LOWER(TRIM(CAST(src.codigo_evento AS STRING))), '') AS codigo_evento,
    NULLIF(TRIM(CAST(src.fc_id AS STRING)), '') AS fc_id,
    NULLIF(TRIM(CAST(src.carrier_id AS STRING)), '') AS carrier_id,
    NULLIF(TRIM(CAST(src.comuna_id AS STRING)), '') AS comuna_id
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_evento_txt IS NOT NULL AND ts_evento IS NULL) THEN 'cast_fallido'
      WHEN evento_id IS NULL OR envio_id IS NULL OR ts_evento IS NULL OR codigo_evento IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_evento_txt IS NOT NULL AND ts_evento IS NULL) THEN 'SAFE_CAST falló en ts_evento'
      WHEN evento_id IS NULL THEN 'evento_id vacío'
      WHEN envio_id IS NULL THEN 'envio_id vacío'
      WHEN ts_evento IS NULL THEN 'ts_evento vacío'
      WHEN codigo_evento IS NULL THEN 'codigo_evento vacío'
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
        PARTITION BY IF(motivo_base IS NULL, evento_id, CAST(NULL AS STRING))
        ORDER BY envio_id, ts_evento, codigo_evento, fc_id, carrier_id, comuna_id
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
      WHEN ranked.envio_id IS NOT NULL AND fk_envios_envio_id.envio_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.codigo_evento = 'entregado' AND env_desp.ts_despacho IS NOT NULL AND ranked.ts_evento < env_desp.ts_despacho THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por evento_id'
      WHEN ranked.envio_id IS NOT NULL AND fk_envios_envio_id.envio_id IS NULL THEN 'envio_id no está en silver.envios'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fc_id no está en silver.centros_fulfillment'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'carrier_id no está en silver.carriers'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'comuna_id no está en silver.comunas'
      WHEN ranked.codigo_evento = 'entregado' AND env_desp.ts_despacho IS NOT NULL AND ranked.ts_evento < env_desp.ts_despacho THEN 'evento entregado anterior al despacho del envío'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.envios` AS fk_envios_envio_id
    ON ranked.envio_id = fk_envios_envio_id.envio_id
  LEFT JOIN `meli_silver.centros_fulfillment` AS fk_centros_fulfillment_fc_id
    ON ranked.fc_id = fk_centros_fulfillment_fc_id.fc_id
  LEFT JOIN `meli_silver.carriers` AS fk_carriers_carrier_id
    ON ranked.carrier_id = fk_carriers_carrier_id.carrier_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_id
    ON ranked.comuna_id = fk_comunas_comuna_id.comuna_id
  LEFT JOIN `meli_silver.envios` AS env_desp
    ON ranked.envio_id = env_desp.envio_id
)
SELECT
  evento_id,
  envio_id,
  ts_evento,
  codigo_evento,
  fc_id,
  carrier_id,
  comuna_id
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY evento_id
  ORDER BY envio_id, ts_evento, codigo_evento, fc_id, carrier_id, comuna_id
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_eventos_tracking`
OPTIONS (
  description="Cuarentena de eventos_tracking. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.eventos_tracking`
),
raw AS (
  SELECT
    src.evento_id AS raw_evento_id,
    src.envio_id AS raw_envio_id,
    src.ts_evento AS raw_ts_evento,
    src.codigo_evento AS raw_codigo_evento,
    src.fc_id AS raw_fc_id,
    src.carrier_id AS raw_carrier_id,
    src.comuna_id AS raw_comuna_id,
    NULLIF(TRIM(CAST(src.evento_id AS STRING)), '') AS evento_id,
    NULLIF(TRIM(CAST(src.envio_id AS STRING)), '') AS envio_id,
    NULLIF(TRIM(CAST(src.ts_evento AS STRING)), '') AS ts_evento_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_evento AS STRING)), '') AS TIMESTAMP) AS ts_evento,
    NULLIF(LOWER(TRIM(CAST(src.codigo_evento AS STRING))), '') AS codigo_evento,
    NULLIF(TRIM(CAST(src.fc_id AS STRING)), '') AS fc_id,
    NULLIF(TRIM(CAST(src.carrier_id AS STRING)), '') AS carrier_id,
    NULLIF(TRIM(CAST(src.comuna_id AS STRING)), '') AS comuna_id
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_evento_txt IS NOT NULL AND ts_evento IS NULL) THEN 'cast_fallido'
      WHEN evento_id IS NULL OR envio_id IS NULL OR ts_evento IS NULL OR codigo_evento IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_evento_txt IS NOT NULL AND ts_evento IS NULL) THEN 'SAFE_CAST falló en ts_evento'
      WHEN evento_id IS NULL THEN 'evento_id vacío'
      WHEN envio_id IS NULL THEN 'envio_id vacío'
      WHEN ts_evento IS NULL THEN 'ts_evento vacío'
      WHEN codigo_evento IS NULL THEN 'codigo_evento vacío'
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
        PARTITION BY IF(motivo_base IS NULL, evento_id, CAST(NULL AS STRING))
        ORDER BY envio_id, ts_evento, codigo_evento, fc_id, carrier_id, comuna_id
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
      WHEN ranked.envio_id IS NOT NULL AND fk_envios_envio_id.envio_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.codigo_evento = 'entregado' AND env_desp.ts_despacho IS NOT NULL AND ranked.ts_evento < env_desp.ts_despacho THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por evento_id'
      WHEN ranked.envio_id IS NOT NULL AND fk_envios_envio_id.envio_id IS NULL THEN 'envio_id no está en silver.envios'
      WHEN ranked.fc_id IS NOT NULL AND fk_centros_fulfillment_fc_id.fc_id IS NULL THEN 'fc_id no está en silver.centros_fulfillment'
      WHEN ranked.carrier_id IS NOT NULL AND fk_carriers_carrier_id.carrier_id IS NULL THEN 'carrier_id no está en silver.carriers'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'comuna_id no está en silver.comunas'
      WHEN ranked.codigo_evento = 'entregado' AND env_desp.ts_despacho IS NOT NULL AND ranked.ts_evento < env_desp.ts_despacho THEN 'evento entregado anterior al despacho del envío'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.envios` AS fk_envios_envio_id
    ON ranked.envio_id = fk_envios_envio_id.envio_id
  LEFT JOIN `meli_silver.centros_fulfillment` AS fk_centros_fulfillment_fc_id
    ON ranked.fc_id = fk_centros_fulfillment_fc_id.fc_id
  LEFT JOIN `meli_silver.carriers` AS fk_carriers_carrier_id
    ON ranked.carrier_id = fk_carriers_carrier_id.carrier_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_id
    ON ranked.comuna_id = fk_comunas_comuna_id.comuna_id
  LEFT JOIN `meli_silver.envios` AS env_desp
    ON ranked.envio_id = env_desp.envio_id
)
SELECT
  raw_evento_id AS evento_id,
  raw_envio_id AS envio_id,
  raw_ts_evento AS ts_evento,
  raw_codigo_evento AS codigo_evento,
  raw_fc_id AS fc_id,
  raw_carrier_id AS carrier_id,
  raw_comuna_id AS comuna_id,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
