-- Lead time aditivo. Looker: SUM(suma_horas) / SUM(n_con_lead).
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `meli_gold.v_lead_time`
OPTIONS (
  description="Suma de horas y conteo, por region, carrier y semana de la promesa. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  f.region_id,
  f.carrier_id,
  d.lunes_semana,
  SUM(f.lead_time_orden_horas) AS suma_lead_time_orden_horas,
  COUNTIF(f.lead_time_orden_horas IS NOT NULL) AS n_lead_time_orden,
  SUM(f.lead_time_despacho_horas) AS suma_lead_time_despacho_horas,
  COUNTIF(f.lead_time_despacho_horas IS NOT NULL) AS n_lead_time_despacho
FROM `meli_gold.f_envios` AS f
INNER JOIN `meli_gold.d_fecha` AS d
  ON f.fecha_promesa = d.fecha
GROUP BY f.region_id, f.carrier_id, d.lunes_semana;
