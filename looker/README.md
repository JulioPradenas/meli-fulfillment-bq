# Informe Looker Studio — Meli Fulfillment

> **Lab de portafolio. Marca con fines ilustrativos.**

Estado: el informe «Meli Fulfillment · cumplimiento de promesa» está armado en Looker Studio con cinco páginas (Overview, Atrasos, Cancelaciones, Lead time y recorrido, Drill). Falta el cierre visual descrito al final. Todavía no está publicado. El contrato visual está en [`STYLE_GUIDE.md`](STYLE_GUIDE.md).

## Fuentes de datos

| Fuente en Looker | Vista de BigQuery | Uso |
|---|---|---|
| Meli · Envíos (drill) | `meli_gold.v_drill_envio` | Todas las páginas menos el embudo. Una fila por envío (32.000) |
| Meli · Hitos | `meli_gold.v_embudo_hitos` | Solo el embudo de la página Lead time y recorrido. Es global: no responde a los filtros de FC y región |

Con una sola fuente principal, los controles Período, FC y Región filtran todas las páginas. Período va sobre `fecha_promesa` (DATE), del 1 may al 31 oct 2026.

## Valores validados en el informe

| Métrica | Valor |
|---|---|
| Envíos / entregados / a tiempo / atrasados | 32.000 / 24.335 / 20.776 / 3.559 |
| Cumplimiento de promesa / % atrasados | 85,4 % / 14,6 % |
| Lead time total, preparación, tránsito | 93,1 h, 32,6 h, 60,5 h |
| Cancelaciones logísticas / tasa | 2.218 / 6,9 % |
| Embudo creado / despachado / entregado | 32.000 / 28.470 / 24.335 |
| Peor FC / peor carrier (% atrasados) | FC Puerto Montt 36,8 % / Ruta Austral 30,1 % |

## Detalles de Looker Studio que conviene saber

- **Filas «null».** Hay envíos sin FC o sin carrier asignado. En los gráficos por FC y por carrier aparece una fila «null» (en «Peor FC» marcaba 14,64 %; también aparece en el mapa de calor). Cada gráfico lleva un filtro **Excluir** → campo → **Es nulo**.
- **Tablas de una fila («Peor FC», «Peor carrier»).** Con «Filas por página = 1» queda un indicador «1 - 1 / N» con flechas. Looker Studio no deja ocultarlo; las flechas navegan al segundo y tercer peor.
- **Formato condicional del % atrasados.** Gana la regla de más abajo. El orden correcto es `> 0,05` (ámbar), luego `> 0,10` (rojo) y al final `<= 0,05` (verde). Con el orden contrario nada sale en rojo.
- **Tarjetas de resultados.** El componente no ofrece negrita para el valor; las tarjetas de Lead time quedan en tamaño 36 sin negrita.
- **Embudo.** La vista trae solo tres hitos, así que no lleva filtro por `orden_hito`. Dimensión `hito`, métrica `n_envios` (con nombre visible «Envíos»), orden por `orden_hito` ascendente.
- **Nombres.** FC y carrier se muestran con su nombre, no con el código.

## Pendiente

- Estilo de las tarjetas de Cancelaciones (valor grande y color `#111827`).
- Revisar que las columnas de texto de la tabla del Drill no se corten.
- Publicar el informe y agregar capturas a este directorio.
