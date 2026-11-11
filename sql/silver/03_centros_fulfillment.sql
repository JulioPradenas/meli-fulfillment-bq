-- meli_silver.centros_fulfillment y meli_silver.q_centros_fulfillment
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.centros_fulfillment`
OPTIONS (
  description="Silver centros_fulfillment. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.centros_fulfillment`
),
raw AS (
  SELECT
    src.fc_id AS raw_fc_id,
    src.fc_nombre AS raw_fc_nombre,
    src.tipo_fc AS raw_tipo_fc,
    src.comuna_id AS raw_comuna_id,
    src.activo AS raw_activo,
    NULLIF(TRIM(src.fc_id), '') AS fc_id,
    NULLIF(TRIM(src.fc_nombre), '') AS fc_nombre,
    NULLIF(LOWER(TRIM(src.tipo_fc)), '') AS tipo_fc,
    NULLIF(TRIM(src.comuna_id), '') AS comuna_id,
    NULLIF(LOWER(TRIM(src.activo)), '') AS activo_txt,
    SAFE_CAST(NULLIF(LOWER(TRIM(src.activo)), '') AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN fc_id IS NULL OR fc_nombre IS NULL OR tipo_fc IS NULL OR comuna_id IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN fc_id IS NULL THEN 'fc_id vacío'
      WHEN fc_nombre IS NULL THEN 'fc_nombre vacío'
      WHEN tipo_fc IS NULL THEN 'tipo_fc vacío'
      WHEN comuna_id IS NULL THEN 'comuna_id vacío'
      WHEN activo IS NULL THEN 'activo vacío'
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
        PARTITION BY IF(motivo_base IS NULL, fc_id, CAST(NULL AS STRING))
        ORDER BY fc_nombre, tipo_fc, comuna_id, activo
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
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por fc_id'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'comuna_id no está en silver.comunas'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_id
    ON ranked.comuna_id = fk_comunas_comuna_id.comuna_id
)
SELECT
  fc_id,
  fc_nombre,
  tipo_fc,
  comuna_id,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY fc_id
  ORDER BY fc_nombre, tipo_fc, comuna_id, activo
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_centros_fulfillment`
OPTIONS (
  description="Cuarentena de centros_fulfillment. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.centros_fulfillment`
),
raw AS (
  SELECT
    src.fc_id AS raw_fc_id,
    src.fc_nombre AS raw_fc_nombre,
    src.tipo_fc AS raw_tipo_fc,
    src.comuna_id AS raw_comuna_id,
    src.activo AS raw_activo,
    NULLIF(TRIM(src.fc_id), '') AS fc_id,
    NULLIF(TRIM(src.fc_nombre), '') AS fc_nombre,
    NULLIF(LOWER(TRIM(src.tipo_fc)), '') AS tipo_fc,
    NULLIF(TRIM(src.comuna_id), '') AS comuna_id,
    NULLIF(LOWER(TRIM(src.activo)), '') AS activo_txt,
    SAFE_CAST(NULLIF(LOWER(TRIM(src.activo)), '') AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN fc_id IS NULL OR fc_nombre IS NULL OR tipo_fc IS NULL OR comuna_id IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN fc_id IS NULL THEN 'fc_id vacío'
      WHEN fc_nombre IS NULL THEN 'fc_nombre vacío'
      WHEN tipo_fc IS NULL THEN 'tipo_fc vacío'
      WHEN comuna_id IS NULL THEN 'comuna_id vacío'
      WHEN activo IS NULL THEN 'activo vacío'
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
        PARTITION BY IF(motivo_base IS NULL, fc_id, CAST(NULL AS STRING))
        ORDER BY fc_nombre, tipo_fc, comuna_id, activo
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
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por fc_id'
      WHEN ranked.comuna_id IS NOT NULL AND fk_comunas_comuna_id.comuna_id IS NULL THEN 'comuna_id no está en silver.comunas'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_id
    ON ranked.comuna_id = fk_comunas_comuna_id.comuna_id
)
SELECT
  raw_fc_id AS fc_id,
  raw_fc_nombre AS fc_nombre,
  raw_tipo_fc AS tipo_fc,
  raw_comuna_id AS comuna_id,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
