-- % a tiempo por región, carrier y semana de la promesa.
-- Solo numerador y denominador. Looker hace SUM(n_a_tiempo)/SUM(n_entregados).
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `meli_gold.v_puntualidad_semana`
OPTIONS (
  description="Aditivos de puntualidad por region_id, carrier_id y lunes de la semana ISO de fecha_promesa. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  f.region_id,
  f.grupo_zona,
  f.carrier_id,
  d.lunes_semana,
  d.semana_iso,
  d.anio_iso,
  COUNT(*) AS n_envios,
  SUM(f.es_entregado) AS n_entregados,
  SUM(f.es_a_tiempo) AS n_a_tiempo,
  SUM(f.es_atrasado) AS n_atrasados,
  SUM(f.es_cancelado_logistica) AS n_cancelado_logistica
FROM `meli_gold.f_envios` AS f
INNER JOIN `meli_gold.d_fecha` AS d
  ON f.fecha_promesa = d.fecha
GROUP BY
  f.region_id,
  f.grupo_zona,
  f.carrier_id,
  d.lunes_semana,
  d.semana_iso,
  d.anio_iso;
