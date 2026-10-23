# Las recetas sólo llaman a Node y npm, así funcionan igual en PowerShell (cmd), Git Bash, WSL, Linux y macOS.

.DEFAULT_GOAL := help
.PHONY: help install reinstall dev test test-unit test-e2e coverage coverage-unit coverage-e2e lint clean

help: ## Muestra los comandos disponibles
	@node -e "const s = require('fs').readFileSync('Makefile', 'utf8'); for (const m of s.matchAll(/^([a-zA-Z0-9_-]+):.*?## (.*)/gm)) console.log('  make ' + m[1].padEnd(14) + ' ' + m[2])"

install: ## Instala las dependencias y el Chromium que usa Playwright
	npm install
	npx playwright install chromium

reinstall: ## Borra node_modules y reinstala (al cambiar de sistema o si quedó roto)
	node -e "require('fs').rmSync('node_modules', { recursive: true, force: true })"
	npm install
	npx playwright install chromium

dev: ## Levanta la app en http://localhost:5173 con recarga automática
	npm run dev

test: test-unit test-e2e ## Corre los tests unitarios y después los e2e

test-unit: ## Corre los tests unitarios (Vitest) una sola vez
	npm test -- --run

test-e2e: ## Corre los tests e2e (Playwright); requiere el puerto 5173 libre
	npm run test:e2e

coverage: coverage-unit coverage-e2e ## Corre las dos coberturas y calcula el total combinado (en líneas)
	node tests/coverage_report.js total
	@echo Reporte: coverage-total/index.html

coverage-unit: ## Cobertura de los tests unitarios (Vitest) en coverage/index.html
	npm test -- --run --coverage
	@echo Reporte: coverage/index.html

# Variable propia de este target: activa la medición en tests/fixtures.js sin depender de la sintaxis de cada terminal.
coverage-e2e: export E2E_COVERAGE := 1
coverage-e2e: ## Cobertura de los tests e2e (Playwright) en coverage-e2e/index.html
	npm run test:e2e
	node tests/coverage_report.js e2e
	@echo Reporte: coverage-e2e/index.html

lint: ## Revisa el código con ESLint
	npm run lint

clean: ## Borra builds y reportes (no toca .env ni node_modules)
	@node -e "for (const d of ['dist', 'dist-ssr', 'coverage', 'coverage-e2e', 'coverage-total', 'playwright-report', 'test-results']) require('fs').rmSync(d, { recursive: true, force: true })"
