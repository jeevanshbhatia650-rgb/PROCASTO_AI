ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python
BIN := backend/.venv/Scripts
else
PY := backend/.venv/bin/python
BIN := backend/.venv/bin
endif

.PHONY: setup dev dev-back dev-front test test-unit test-int test-fe lint deadcode types demo

setup:
	cd backend && uv sync --extra dense
	cd frontend && npm install

dev:
	$(MAKE) -j2 dev-back dev-front

dev-back:
	$(PY) -m uvicorn app.main:create_app --factory --app-dir backend --port 8000

dev-front:
	npm --prefix frontend run dev

test: test-unit test-int test-fe

test-unit:
	cd backend && ../$(PY) -m pytest tests/unit -q

test-int:
	cd backend && ../$(PY) -m pytest tests/integration -q

test-fe:
	npm --prefix frontend test

lint:
	$(BIN)/ruff check backend/app backend/tests
	npm --prefix frontend run lint

deadcode:
	$(BIN)/vulture backend/app --min-confidence 70
	npm --prefix frontend run deadcode

types:
	cd backend && ../$(PY) -m scripts.export_schema ../frontend/src/types/schema.json
	npm --prefix frontend run types

demo: dev
