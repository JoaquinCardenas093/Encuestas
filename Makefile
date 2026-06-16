.PHONY: dev test lint backend-install frontend-install install

install: backend-install frontend-install

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

frontend-install:
	cd frontend && npm install --cache /tmp/npm-cache

dev-backend:
	cd backend && .venv/bin/uvicorn aurum_encuestas.api:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test-backend:
	cd backend && .venv/bin/pytest -v

test-frontend:
	cd frontend && npm test

build-frontend:
	cd frontend && npm run build

lint-backend:
	cd backend && .venv/bin/ruff check aurum_encuestas tests

dev: dev-backend

test: test-backend test-frontend

lint: lint-backend

dev-all:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"
