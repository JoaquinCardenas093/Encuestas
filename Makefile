.PHONY: dev test lint backend-install frontend-install install e2e-fixtures

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

e2e:
	cd e2e && npm test

e2e-fixtures:
	mkdir -p e2e_fixtures
	cd backend && .venv/bin/python -c "\
from pptx import Presentation; from pptx.util import Inches; \
from pptx.chart.data import CategoryChartData; from pptx.enum.chart import XL_CHART_TYPE; \
prs = Presentation(); prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5); \
blank = prs.slide_layouts[6]; \
s = prs.slides.add_slide(blank); \
cd = CategoryChartData(); cd.categories = ['Sí', 'No']; cd.add_series('Total', [75, 25]); \
s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(2), Inches(1.5), Inches(5), Inches(5), cd); \
tb = s.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(10), Inches(0.5)); tb.text_frame.text = 'El 75%% de los encuestados conoce la marca.'; \
s2 = prs.slides.add_slide(blank); \
cd2 = CategoryChartData(); cd2.categories = ['A', 'B', 'C']; cd2.add_series('Total', [40, 35, 25]); \
s2.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(1), Inches(1), Inches(10), Inches(5.5), cd2); \
prs.save('../e2e_fixtures/training_sample.pptx'); \
print('e2e_fixtures/training_sample.pptx saved')"
