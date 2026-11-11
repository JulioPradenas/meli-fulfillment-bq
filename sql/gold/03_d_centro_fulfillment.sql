-- d_centro_fulfillment. Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.d_centro_fulfillment`
OPTIONS (
  description="Centros de fulfillment. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  fc_id,
  fc_nombre,
  tipo_fc,
  comuna_id,
  activo
FROM `meli_silver.centros_fulfillment`;
