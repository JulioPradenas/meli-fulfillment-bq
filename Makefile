# Meli Fulfillment — lab runners (Paso 1)
# Uso: make test
#
# CI corre `make test` (pytest). Sin generador de datos y sin llamadas GCP.

PY ?= python3

.PHONY: help test

help:
	@echo "Targets: test"
	@echo "PY=$(PY)"

test:
	$(PY) -m pytest -q
