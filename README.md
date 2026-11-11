# Meli — Fulfillment de marketplace en BigQuery

> **Lab de portafolio. Marca con fines ilustrativos.**  
> No es un entregable de empleo ni un claim sobre Mercado Libre. Sin logos.

Analista: [Julio Pradenas](https://github.com/JulioPradenas)

Proyecto 2 del portafolio Analista BI.  
Proyecto 1: [kora-logistica-bq](https://github.com/JulioPradenas/kora-logistica-bq) (WMS + last mile).

## Objetivo

Un solo número (SSoT) para el cumplimiento de la **promesa de entrega** de un marketplace de fulfillment estilo Mercado Libre, en Chile: atrasos contra la fecha prometida, cancelaciones logísticas por causa y lead time, con grano **un envío**.

## Problema

Operaciones mira la promesa en un export de envíos, el tracking en otro y al seller en una planilla. El «% atrasados» de un FC no se puede sumar con el de otro porque alguien promedió porcentajes. No hay forma de decir si el atraso se fue en el centro de fulfillment o en el carrier, ni qué causa cancela de verdad.

## Preguntas de negocio

1. De los envíos **entregados**, ¿qué porcentaje llegó después de la fecha promesa?
2. ¿Cuál es el cumplimiento de promesa del período (a tiempo / entregados), y cómo se mueve por semana?
3. ¿Qué causas explican las cancelaciones logísticas, y en qué seller o FC se concentran?
4. ¿Cuál es el lead time real (creación → entrega) y qué tramo se lo queda: preparación o tránsito?
5. ¿El incumplimiento de un seller se explica por el FC que lo opera o por la comuna de destino?

Fórmulas cerradas (SUM/SUM, nunca promedio de porcentajes): [docs/modelo-datos.md](docs/modelo-datos.md).

## Solución (sandbox, por construir)

```text
CSV sintéticos → Python (laptop) → BigQuery bronze → silver → gold
                                                              ↓
                                                        Looker Studio
                                                        (f_envios + dims)
```

- **Hecho gold:** `f_envios` — 1 fila por envío.
- **Proyecto GCP previsto:** `meli-fulfillment` (no se crea en este paso).
- **Datasets previstos:** `bronze_meli` · `silver_meli` · `gold_meli`.
- **Región prevista:** `southamerica-west1`.
- **Zona horaria:** `America/Santiago`.

Cloud Scheduler / Cloud Functions / Composer: solo se narrarán en pasos posteriores. No hay credenciales en este repo.

## Roadmap

| Paso | Entrega | Estado |
|---|---|---|
| 1 | Esqueleto, modelo de datos, guía de estilo | ✅ este repo |
| 2 | Datos sintéticos + contrato de columnas | ⏳ |
| 3 | Datasets BigQuery (medallón) | ⏳ |
| 4 | DDL vacío (shapes + estrella) | ⏳ |
| 5 | Carga bronze | ⏳ |
| 6 | Silver + cuarentena | ⏳ |
| 7 | Gold `f_envios` + dimensiones | ⏳ |
| 8 | Demo de partition / cluster | ⏳ |
| 9 | Looker Studio según la guía de estilo | ⏳ |
| 10 | One-pager de portafolio | ⏳ |

El Paso 1 no genera datos y no abre GCP. Fija la forma de las tablas, el grano, las métricas y el diseño del dashboard futuro.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make test
```

`make test` corre pytest. No llama a BigQuery.

## Docs

- [Modelo de datos](docs/modelo-datos.md) — fuentes, `f_envios`, fórmulas, páginas del dashboard
- [Guía de estilo Looker Studio](looker/STYLE_GUIDE.md) — paleta, layout, KPI cards, es-CL, contraste AA

## Disclaimer

Lab de portafolio. Marca con fines ilustrativos. Los pasos 2–10 conectarán datos sintéticos y un gold que alimente Looker Studio. Con presupuesto cloud, el mismo contrato se puede orquestar; eso queda fuera de este paso.
