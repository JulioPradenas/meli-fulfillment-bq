-- Meli Fulfillment — DDL bronze (landing crudo, todo STRING NULLABLE).
-- Dataset: meli_bronze · location: US · expiración: 60 días.
-- Sandbox sin facturación: sin DML y sin streaming. Este archivo solo tiene
-- CREATE OR REPLACE TABLE. Los CSV entran por load job WRITE_TRUNCATE
-- con max_bad_records=0. No hay ALTER.
--
-- Todas las columnas son STRING. Un BOOL/DATE/TIMESTAMP en el load rechaza
-- el token 'NO-CAST' y el job falla entero (incidente PR #3: regiones y
-- comunas cargaron; el resto no). Silver castea con SAFE_CAST.
--
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_bronze.regiones` (
  region STRING,
  region_nombre STRING,
  zona STRING
)
OPTIONS (
  description="Bronze regiones. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.comunas` (
  comuna_id STRING,
  comuna_nombre STRING,
  region STRING
)
OPTIONS (
  description="Bronze comunas. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.centros_fulfillment` (
  fc_id STRING,
  fc_nombre STRING,
  tipo_fc STRING,
  comuna_id STRING,
  activo STRING
)
OPTIONS (
  description="Bronze centros_fulfillment. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.carriers` (
  carrier_id STRING,
  carrier_nombre STRING,
  tipo_servicio STRING,
  activo STRING
)
OPTIONS (
  description="Bronze carriers. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.sellers` (
  seller_id STRING,
  seller_nombre STRING,
  tipo_seller STRING,
  region_origen STRING,
  activo STRING
)
OPTIONS (
  description="Bronze sellers. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.ordenes` (
  orden_id STRING,
  seller_id STRING,
  ts_creacion STRING,
  comuna_destino_id STRING,
  estado_orden STRING
)
OPTIONS (
  description="Bronze ordenes. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.envios` (
  envio_id STRING,
  orden_id STRING,
  seller_id STRING,
  fc_id STRING,
  carrier_id STRING,
  comuna_destino_id STRING,
  tipo_logistica STRING,
  ts_creacion STRING,
  ts_despacho STRING,
  ts_entrega STRING,
  fecha_promesa STRING,
  estado STRING,
  motivo_cancelacion_logistica STRING
)
OPTIONS (
  description="Bronze envios. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `meli_bronze.eventos_tracking` (
  evento_id STRING,
  envio_id STRING,
  ts_evento STRING,
  codigo_evento STRING,
  fc_id STRING,
  carrier_id STRING,
  comuna_id STRING
)
OPTIONS (
  description="Bronze eventos_tracking. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);
