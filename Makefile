# Meli Fulfillment — lab runners
# Uso: make test | make data | make bronze | make run
#       make run DRY=1
#
# make run reconstruye todo desde cero: CSV, bronze, silver y gold
# (CREATE OR REPLACE, sin DML). Gold no parte por fecha: cluster por
# region_id y carrier_id. verify_bronze imprime OK/FAIL.
# verify_silver y verify_gold imprimen OK/FALLA.
#
# Sandbox (sin facturación): sin DML, sin streaming. Las tablas y las
# particiones expiran a los 60 días; por eso make run no depende de lo que
# haya quedado de la corrida anterior.
#
# Auth: ADC. GCP_PROJECT es obligatorio para bronze/run reales (no hay default).
# DRY=1 no llama a BigQuery. Igual regenera los CSV: son locales y el load
# en dry-run los necesita para validar headers.

PY  ?= python3
DRY ?= 0
ifeq ($(DRY),1)
  DRY_FLAG := --dry-run
else
  DRY_FLAG :=
endif

.PHONY: help test data bronze silver gold run

help:
	@echo "Targets: data | bronze | silver | gold | run | test"
	@echo "PY=$(PY)  DRY=$(DRY)"
	@echo "GCP_PROJECT debe estar exportado para bronze, silver, gold y run reales (no hay default)."
	@echo "DRY=1 regenera CSV y valida sin consultar BigQuery."

test:
	$(PY) -m pytest -q

data:
	$(PY) src/generate_data.py

bronze:
	$(PY) src/apply_ddl.py $(DRY_FLAG)
	$(PY) src/load_bronze.py $(DRY_FLAG)

silver:
	$(PY) src/build_silver.py $(DRY_FLAG)

gold:
	$(PY) src/build_gold.py $(DRY_FLAG)

run: data bronze silver gold
	$(PY) src/verify_bronze.py $(DRY_FLAG)
	$(PY) src/verify_silver.py $(DRY_FLAG)
	$(PY) src/verify_gold.py $(DRY_FLAG)
