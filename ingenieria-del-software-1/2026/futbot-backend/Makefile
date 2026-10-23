# Las recetas sólo llaman a Python, así funcionan igual en PowerShell (cmd), Git Bash, WSL, Linux y macOS.

ifeq ($(OS),Windows_NT)
  PYTHON ?= python
  VENV_BIN := .venv/Scripts
else
  PYTHON ?= python3
  VENV_BIN := .venv/bin
endif

VENV_PY := $(VENV_BIN)/python
PORT ?= 8000

# Python del sistema aunque haya un venv activo: Windows no deja borrar el python del .venv mientras corre.
BASE_PYTHON = $(shell $(PYTHON) -c "import sys; print(sys._base_executable)")

# Sin esto, los acentos salen rotos en Git Bash.
export PYTHONIOENCODING := utf-8

.DEFAULT_GOAL := help
.PHONY: help install reinstall dev test coverage lint clean

help: ## Muestra los comandos disponibles
	@$(PYTHON) -c "import re; [print('  make ' + t.ljust(10) + ' ' + d) for t, d in re.findall(r'^([a-zA-Z0-9_-]+):.*?## (.*)', open('Makefile', encoding='utf-8').read(), re.M)]"

# pyvenv.cfg como objetivo: el venv sólo se crea si no existe.
.venv/pyvenv.cfg:
	"$(BASE_PYTHON)" -m venv .venv

install: .venv/pyvenv.cfg ## Crea el .venv si no existe e instala las dependencias
	$(VENV_PY) -m pip install -r requirements.txt

# Recrea el venv acá mismo: depender de install podría reusar lo que make ya sabía de pyvenv.cfg antes de borrarlo.
# Renombrar primero funciona aunque el python del venv viejo esté corriendo; sus restos se borran en la próxima corrida o con make clean.
reinstall: ## Borra el .venv y lo crea de cero (al cambiar de sistema o si quedó roto)
	$(if $(BASE_PYTHON),,$(error Python no arranca. Si hay un .venv activado y roto, correr deactivate y repetir make reinstall))
	"$(BASE_PYTHON)" -c "import os, shutil; shutil.rmtree('.venv-old', ignore_errors=True); os.path.isdir('.venv') and os.rename('.venv', '.venv-old'); shutil.rmtree('.venv-old', ignore_errors=True)"
	"$(BASE_PYTHON)" -m venv .venv
	$(VENV_PY) -m pip install -r requirements.txt

dev: ## Levanta la API con recarga automática (PORT=8000 por defecto)
	$(VENV_PY) -m uvicorn app.main:app --reload --port $(PORT)

test: ## Corre los tests con reporte de cobertura en la terminal
	$(VENV_PY) -m pytest --cov=app --cov-report=term-missing

coverage: ## Corre los tests y genera el reporte de cobertura en htmlcov/index.html
	$(VENV_PY) -m pytest --cov=app --cov-report=term-missing --cov-report=html
	@echo Reporte: htmlcov/index.html

lint: ## Revisa el código con Ruff
	$(VENV_PY) -m ruff check app tests

clean: ## Borra cachés y reportes (no toca .env, .venv ni futbot.db)
	@$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if '.venv' not in p.parts]"
	@$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', 'htmlcov', 'build', 'dist', '.venv-old']]"
	@$(PYTHON) -c "import glob, pathlib, shutil; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', 'coverage.xml']]; [shutil.rmtree(p) for p in glob.glob('*.egg-info')]"
