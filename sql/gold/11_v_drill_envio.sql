-- Drill a nivel envío. Las fechas son DATE para el control de período de Looker.
-- Los flags 0/1 se suman; no se promedian.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `meli_gold.v_drill_envio`
OPTIONS (
  description="Una fila por envío con fechas DATE y flags 0/1. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  f.envio_id,
  f.orden_id,
  f.fecha_creacion,
  f.fecha_despacho,
  f.fecha_promesa,
  f.fecha_entrega,
  f.estado,
  f.motivo_cancelacion_logistica,
  f.es_entregado,
  f.es_a_tiempo,
  f.es_atrasado,
  f.es_cancelado_logistica,
  f.lead_time_orden_horas,
  f.lead_time_despacho_horas,
  f.region_id,
  g.region_nombre,
  g.grupo_zona,
  g.comuna_id,
  g.comuna_nombre,
  f.carrier_id,
  c.carrier_nombre,
  f.seller_id,
  s.seller_nombre,
  f.fc_id,
  fc.fc_nombre
FROM `meli_gold.f_envios` AS f
INNER JOIN `meli_gold.d_geografia` AS g
  ON f.comuna_id = g.comuna_id
INNER JOIN `meli_gold.d_seller` AS s
  ON f.seller_id = s.seller_id
LEFT JOIN `meli_gold.d_carrier` AS c
  ON f.carrier_id = c.carrier_id
LEFT JOIN `meli_gold.d_centro_fulfillment` AS fc
  ON f.fc_id = fc.fc_id;
