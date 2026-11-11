# Guía de estilo Looker Studio — Meli Fulfillment

> **Lab de portafolio. Marca con fines ilustrativos.**  
> Paleta inspirada en la marca, sin logos y sin wordmark. El informe **todavía no está publicado**: esta guía es el contrato visual para el Paso 9.

Objetivo: que el dashboard de cumplimiento de promesa se arme sobre `f_envios` con la misma fórmula en todas las páginas, números en es-CL y contraste AA.

Fuente de las métricas: [`docs/modelo-datos.md`](../docs/modelo-datos.md). Si una fórmula de aquí no coincide con ese documento, manda el modelo.

---

## 1. Tokens de diseño

Amarillo de marca aproximado `#FFE600`. Azul de marca aproximado `#2D3277`. El amarillo es fondo de header y acento de superficie grande. No es color de texto ni de línea fina: sobre blanco no llega a AA (1,27 : 1).

| Token | Valor |
|---|---|
| Fondo página | `#F7F6F2` |
| Superficie de card | `#FFFFFF` |
| Amarillo (header / chip grande) | `#FFE600` |
| Azul (texto de header, serie, filete, valor KPI) | `#2D3277` |
| Azul profundo (hover / barra secundaria) | `#23275E` |
| Verde (texto) | `#0F6B45` — fondo `#E5F6EE` |
| Ámbar (texto) | `#8A5200` — fondo `#FFF4E0` |
| Rojo (texto) | `#B42318` — fondo `#FDECEC` |
| Texto | `#1F2937` |
| Texto secundario | `#4B5563` |
| Líneas / bordes | `#E4E2DA` |
| Fuente | **Roboto** en el tema de Looker Studio. Inter solo si un mockup futuro la trae embebida; el informe publicado no depende de una webfont externa |
| Label KPI | 11px, uppercase, weight 600, color `#4B5563` |
| Valor KPI | 28–32px, weight 700, color `#2D3277` |
| Título card | 14px, weight 600, color `#1F2937` |
| Tabla | 13px |
| Radio cards | 12px |
| Sombra | suave (`0 1px 2px` + `0 8px 24px` a ~6% de `#2D3277`) |
| Grilla | 12 columnas, gutter **24px**, margen de página 24px |
| Header | **64px**, fondo `#FFE600`, texto `#2D3277`, **filete inferior 2px** `#2D3277` |
| Footer | 32px, texto `#4B5563`: «Lab de portafolio. Marca con fines ilustrativos.» |

### Contraste AA

Ratios con la fórmula de luminancia relativa de WCAG 2.x. Umbral de texto normal: **4,5 : 1**. El semáforo no se comunica solo con color: la celda lleva el número y, en la leyenda, el rótulo (A tiempo / Atención / Atrasado).

| Texto | Fondo | Ratio | Uso |
|---|---|---|---|
| `#2D3277` | `#FFFFFF` | 11,45 : 1 | Valores KPI, series, links |
| `#2D3277` | `#FFE600` | 9,03 : 1 | Título y controles del header |
| `#FFFFFF` | `#2D3277` | 11,45 : 1 | Texto sobre azul (barra, chip activo) |
| `#1F2937` | `#FFFFFF` | 14,68 : 1 | Cuerpo |
| `#4B5563` | `#FFFFFF` | 7,56 : 1 | Label KPI, ejes, footer |
| `#0F6B45` | `#E5F6EE` | 5,84 : 1 | Semáforo dentro de meta |
| `#8A5200` | `#FFF4E0` | 5,86 : 1 | Semáforo en el borde |
| `#B42318` | `#FDECEC` | 5,76 : 1 | Semáforo fuera de meta |
| `#FFFFFF` | `#FFE600` | 1,27 : 1 | No usar |
| `#FFE600` | `#FFFFFF` | 1,27 : 1 | El amarillo no es color de texto ni de línea fina |

Líneas de gráfico sobre fondo claro: `#2D3277`. La referencia de meta, si se dibuja, va en `#8A5200` discontinua (el ámbar de texto pasa AA; el amarillo de marca no se lee como línea de 1–2px). El relleno de una barra ancha sí puede ser `#FFE600` con borde `#2D3277`.

---

## 2. Layout por página

Misma cromática y el mismo header en las cinco páginas. Título de texto «Fulfillment · cumplimiento de promesa». Sin logo.

Controles del header, a la derecha: **Periodo** (sobre `fecha_promesa`), **FC**, **Región**. El Drill suma **Seller**. Un botón **Restablecer** visible. Los cross-filters entre gráficos quedan apagados: un click en el heatmap no debe vaciar las tarjetas.

Población de cada página, salvo Cancelaciones cuando se diga lo contrario: envíos cuya `fecha_promesa` cae en el período.

### Overview

Responde: ¿cumplimos la promesa en el período? ¿Qué tan atrasados van los entregados? ¿Cuánto tarda un envío y qué parte se cancela por logística?

| Filas | Bloque | Columnas |
|---|---|---|
| 1 | 4 KPI cards | 3 + 3 + 3 + 3 |
| 2 | Serie semanal de cumplimiento de promesa, con meta dibujada | 8 |
| 2 | Barras de las 3 causas logísticas con más envíos | 4 |
| 3 | Tabla región de destino: envíos, entregados, % atrasados, lead time | 12 |

La semana de la serie es la semana ISO de `fecha_promesa`.

### Atrasos

Responde: ¿el atraso está en un centro, en un carrier o en una región?

| Filas | Bloque | Columnas |
|---|---|---|
| 1 | KPI % atrasados vs promesa (mismo número que Overview, con el filtro de esta página) | 12, una sola card ancha o tres cortes: total, peor FC, peor carrier |
| 2 | Heatmap FC × semana | 12 |
| 3 | Barras por carrier | 6 |
| 3 | Barras por región de destino | 6 |

El color del heatmap pinta **solo** la medida % atrasados, con la escala de la sección 3. La celda muestra el porcentaje, no un bloque de color mudo.

### Cancelaciones

Responde: ¿qué causa domina, en qué seller o FC, y eso es mucho sobre todos los envíos o solo dentro de las cancelaciones?

| Filas | Bloque | Columnas |
|---|---|---|
| 1 | KPI tasa de cancelación logística y KPI cancelaciones (conteo) | 6 + 6 |
| 2 | Barras horizontales por motivo (conteo) | 7 |
| 2 | Participación de la causa (suma 100%) | 5 |
| 3 | Tabla seller × motivo, con el FC | 12 |

La participación usa de denominador las cancelaciones logísticas. La tasa usa todos los envíos. Van en gráficos distintos, con el denominador escrito en el subtítulo de la card.

### Lead time

Responde: ¿cuántas horas van de la creación a la entrega, y qué tramo se las queda?

| Filas | Bloque | Columnas |
|---|---|---|
| 1 | KPI lead time total, preparación, tránsito | 4 + 4 + 4 |
| 2 | Serie semanal del lead time total | 12 |
| 3 | Barras por FC (preparación) | 6 |
| 3 | Barras por carrier (tránsito) | 6 |

Preparación y tránsito salen de la misma población: entregados con `ts_despacho`. El subtítulo de las tres cards lo dice, para que el total cuadre con la suma de los tramos.

### Drill

Responde: ¿qué seller × comuna × carrier explica el número del Overview, y si hay reintentos detrás del atraso?

Una tabla a 12 columnas. Orden por defecto: `SUM(envios)` descendente. Columnas: seller, comuna, región, carrier, FC, envíos, entregados, % atrasados, cumplimiento de promesa, lead time (horas), intentos fallidos. El formato condicional va solo en la celda de % atrasados.

---

## 3. Checklist paso a paso (Data Studio)

Etiquetas de la UI en español. El informe se crea en el Paso 9; esta lista es el orden de armado.

### (a) Tema

1. Tema del informe → fuente **Roboto**, fondo `#F7F6F2`.
2. Paleta: `#2D3277`, `#FFE600`, `#0F6B45`, `#8A5200`, `#B42318`.
3. Header 64px amarillo, texto azul, filete azul 2px. Repetirlo en las cinco páginas, no solo en Overview.

### (b) KPI cards

1. Cuatro cards en Overview, en este orden: cumplimiento de promesa, % atrasados vs promesa, lead time (horas), tasa de cancelación logística.
2. Label 11–12px, uppercase, weight 600. Valor ~30px (entre 28 y 32), weight 700, color `#2D3277`.
3. Cada card lleva en la descripción del campo la fórmula de la sección «Fórmulas canónicas». El número no va solo.
4. Polaridad del delta (comparación vs período anterior). Verde no significa «subió»:
   - Cumplimiento de promesa: subir es mejor.
   - % atrasados vs promesa: bajar es mejor.
   - Lead time: bajar es mejor.
   - Tasa de cancelación logística: bajar es mejor.
5. El delta compara el mismo SUM/SUM en los dos períodos. No compara promedios de porcentajes.
6. Sin sparkline que use otra agregación que la de la card.

### (c) Formato de números es-CL

Locale del informe: **Español (Chile)** (`es-CL`).

| Medida | Tipo en Looker | Ejemplo |
|---|---|---|
| Porcentaje en card | Porcentaje, 1 decimal | `12,4%` |
| Porcentaje en tabla | Porcentaje, 2 decimales | `12,38%` |
| Conteos | Número, 0 decimales, miles con punto | `10.718` |
| Lead time | Número, 1 decimal, sufijo ` h` | `36,5 h` |
| Fecha | `dd/mm/yyyy` | `11/11/2026` |
| Nulo (denominador 0) | Guion, no cero | `—` |

No hay montos en CLP en este informe. Un cero de envíos sí se muestra como `0`: el guion es para un ratio sin denominador.

### (d) Formato condicional, solo en la celda de % atrasados

Umbrales de **diseño del lab**, no un SLA de la marca. Se pueden mover cuando existan datos; no se mueven en silencio dentro de un gráfico.

1. Abrir la tabla (Overview por región, o Drill).
2. Formato condicional → aplicar **solo** a la columna % atrasados, no a la fila.
3. Reglas, sobre el ratio ya calculado con SUM/SUM:
   - `≤ 0,05` → texto `#0F6B45`, fondo `#E5F6EE`
   - `> 0,05` y `≤ 0,10` → texto `#8A5200`, fondo `#FFF4E0`
   - `> 0,10` → texto `#B42318`, fondo `#FDECEC`

El cumplimiento de promesa es el complemento (a tiempo / entregados). No se pinta con otra escala: si hace falta color, se usan las bandas espejo `≥ 0,95`, `0,90–0,95`, `< 0,90`.

### (e) Serie y heatmap

1. Métrica de la serie = cumplimiento de promesa, no el promedio de un porcentaje semanal precalculado.
2. Línea de meta en `#8A5200` discontinua. El valor de la meta es un parámetro del informe (el lab arranca en 95% de cumplimiento), escrito en el subtítulo. No es un dato medido.
3. Heatmap de Atrasos: orden de la semana cronológico, FC por `SUM(entregados)` descendente. Color solo en % atrasados.

### (f) Cancelaciones, dos denominadores

1. Gráfico de participación: métrica `SUM(cancelado_causa) / SUM(cancelado_logistica)`.
2. Card de tasa: métrica `SUM(cancelado_logistica) / SUM(envios)`.
3. El subtítulo de cada uno dice el denominador en palabras: «sobre cancelaciones logísticas» o «sobre todos los envíos».

### (g) Lead time que cuadra

1. Las tres cards filtran entregados con despacho cuando se muestran juntas.
2. Comprobar, con el mismo filtro: preparación + tránsito = total, dentro del redondeo de 1 decimal.
3. No usar `AVG` de un campo que ya sea el promedio de la región.

---

## Fórmulas canónicas

Se escriben igual que en el modelo. Los nombres `atrasado`, `entregados`, `a_tiempo`, `cancelado_causa`, `cancelado_logistica` y `lead_time_horas` son los indicadores de `f_envios` (0/1 o horas por envío), no porcentajes guardados.

```text
% atrasados vs promesa = SUM(atrasado) / SUM(entregados)

cumplimiento de promesa = SUM(a_tiempo) / SUM(entregados)

participación de la causa = SUM(cancelado_causa) / SUM(cancelado_logistica)

lead time (horas) = SUM(lead_time_horas) / SUM(entregados)
```

Los porcentajes se calculan como SUM/SUM, nunca como promedio de porcentajes.

`AVG(lead_time_horas)` solo se acepta en un gráfico cuyo grano sigue siendo el envío (cada fila pesa igual). En cualquier agregado, la métrica es el SUM/SUM de arriba.

Tipo de campo de los porcentajes: **Porcentaje**. No marcar el 0/1 como porcentaje dentro de la fuente: eso invitaría a promediarlo con el agregador por defecto.

---

## 4. Trampas conocidas

| Trampa | Qué pasa | Qué hacer |
|---|---|---|
| **Agregación por defecto AVG** | El scorecard hereda el promedio del porcentaje o del boolean y deja de cuadrar con la tabla | Fijar la métrica calculada SUM/SUM en cada gráfico. Revisar el override a nivel chart |
| **Promedio de porcentajes** | El % de un FC chico pesa igual que el de un FC grande. El total no es el cumplimiento real | Numerator y denominador aditivos; el % se cierra al final |
| **Denominador de la causa** | La participación sobre cancelaciones se lee como tasa sobre todos los envíos | Dos gráficos, dos subtítulos, dos fórmulas |
| **Grano evento** | Contar filas de tracking multiplica un envío por sus hitos | Fuente del informe: `f_envios`. Una fila, un `envio_id` |
| **Inner join al motivo** | Filtrar o unir el motivo se come a los entregados y el % atrasados cambia | Fila «no aplica» en la dimensión; left join |
| **Amarillo como texto** | `#FFE600` sobre blanco queda en 1,27 : 1. No es AA | Amarillo solo en header y en rellenos grandes. Texto del header en `#2D3277` |
| **Verde = siempre hacia arriba** | Un alza del % atrasados se pinta como mejora | Invertir la polaridad en atrasos, lead time y cancelaciones |
| **Cross-filter** | Un click en el heatmap vacía las cards | Interacciones apagadas; botón Restablecer |
| **Semana de la entrega** | El lunes siguiente absorbe el atraso de la promesa del viernes | Serie y filtro de período sobre `fecha_promesa` |
| **Cero en vez de nulo** | Un FC sin entregados muestra 0% de atraso y parece perfecto | Denominador 0 → `—` |

---

## 5. Checklist de verificación final

Cuando el Paso 9 publique el informe, abrirlo en incógnito, **Restablecer** filtros y comprobar lo siguiente. Este paso no tiene cifras: no se inventan valores de verificación.

| Comprobación | Esperado |
|---|---|
| Fuente de todas las páginas | `f_envios` (o un agregado de sumas). Nada de bronze |
| % atrasados vs promesa | La métrica del chart es `SUM(atrasado) / SUM(entregados)` |
| Cumplimiento de promesa | `SUM(a_tiempo) / SUM(entregados)`, y suma 100% con el % atrasados bajo el mismo filtro |
| Participación de la causa | `SUM(cancelado_causa) / SUM(cancelado_logistica)`; las causas suman 100% |
| Lead time | `SUM(lead_time_horas) / SUM(entregados)`; preparación + tránsito = total en la población con despacho |
| Locale | es-CL: miles con punto, decimales con coma, fechas `dd/mm/yyyy` |
| Contraste | Texto de header azul sobre amarillo; ningún texto en `#FFE600` |
| Aviso | El footer de cada página dice «Lab de portafolio. Marca con fines ilustrativos.» |
| Marca | No hay logo ni wordmark |

Si cumplimiento y % atrasados no suman 100%, el primer sospechoso es un `AVG` o un filtro que no comparten las dos cards.

---

## Archivos de referencia

| Archivo | Uso |
|---|---|
| [`docs/modelo-datos.md`](../docs/modelo-datos.md) | Grano de `f_envios`, indicadores y fórmulas que esta guía no reescribe |
| [`README.md`](../README.md) | Objetivo del lab, preguntas y roadmap |
| Esta guía | Tokens, layout por página, KPI cards, es-CL, contraste AA |
