.PHONY: dev test lint backend-install install

install: backend-install

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev-backend:
	cd backend && .venv/bin/uvicorn aurum_encuestas.api:app --reload --port 8000

test-backend:
	cd backend && .venv/bin/pytest -v

lint-backend:
	cd backend && .venv/bin/ruff check aurum_encuestas tests

dev: dev-backend

test: test-backend

lint: lint-backend
