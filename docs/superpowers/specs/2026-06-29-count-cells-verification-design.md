# Diseño: "Seleccionar conteos" — verificación de celdas en Editar en Excel

**Fecha:** 2026-06-29
**Estado:** aprobado, pendiente de plan de implementación

## Problema

El editor "Editar en Excel" (`SheetGrid`) deja pintar roles (pregunta, opción, breakdown, categoría, counts, total) arrastrando sobre las celdas crudas de la hoja. El rol `counts` hoy se pinta a mano como un rango de columnas indicativo.

El usuario no tiene forma de **corroborar visualmente que el sistema tomó los conteos correctos** — es decir, qué celda exacta `(fila-opción × columna-categoría)` lee el extractor como conteo de cada opción en cada categoría de cada breakdown.

## Objetivo

Un botón **"Seleccionar conteos"** en el modo Excel que resalta de una **todas las celdas de conteo detectadas** por el backend, usando el rol `counts` existente. El usuario las corrobora; puede borrar/agregar con las herramientas actuales de la toolbar. No cambia el modelo de extracción.

## No-objetivos (descartados explícitamente)

- Edición inline del valor numérico en la celda.
- Overrides de conteo/% desde el grid (eso sigue en "Editar campos" vía `CellValuesEditor`).
- Cambiar el modelo de extracción de rango de columnas (`counts_cols`) a celdas individuales.
- Marca/rol nuevo dedicado: se reusa el rol `counts` existente.

## Arquitectura

Dos piezas, sin cambios en el modelo de datos ni en la extracción.

### 1. Backend — endpoint `POST /api/count-cells`

- **Request model:** `CountCellsRequest { state: dict }`.
- **Lógica:** valida `ProjectState`; abre el xlsx (`state.inputs.db_path`); recorre **todas** las preguntas × **todos** los breakdowns y, reusando `_find_question_rows(ws, question)` y `_resolve_breakdown_cols(ws, breakdown_id, counts_start)`, junta la coordenada `(row, col)` de cada celda de conteo `(q_rows[opción], breakdown_cols[categoría])`.
- **Salida:** `{ cells: [{row, col}], error? }` con coordenadas **1-based** (convención openpyxl, igual que el resto del backend). Las coordenadas se **deduplican** (un mismo `(row,col)` puede surgir una sola vez).
- **Fallback-safe:** mismo patrón que `/api/cell-values` y `/api/sheet-grid` — cualquier fallo (estado inválido, sin `parsed_db`/`inputs`, error al abrir) devuelve `{ error: <str>, cells: [] }`, nunca lanza al cliente.

Pseudo-forma de la respuesta:

```json
{ "cells": [ {"row": 5, "col": 3}, {"row": 6, "col": 3}, {"row": 5, "col": 4} ] }
```

`counts_start = state.parsed_db.data_blocks["counts_cols"][0]` (igual que los extractores). El recorrido reusa la misma resolución que `extract_chart_data`, así que las celdas marcadas son exactamente las que el extractor lee.

### 2. Frontend

**Cliente** (`frontend/src/api/client.ts`):

```ts
export interface CountCellsResponse {
  cells: { row: number; col: number }[]   // 1-based
  error?: string
}
export async function fetchCountCells(state: any): Promise<CountCellsResponse>
```
Sigue el patrón de `fetchCellValues` (POST `/count-cells`, `request<CountCellsResponse>`).

**UI** (`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`, bloque `mode === "excel"`):

- Botón **"Seleccionar conteos"** ubicado junto a los controles del grid (encima o al lado del `SheetGrid`).
- Handler `handleSelectCounts`:
  1. `const res = await fetchCountCells(storeState)`.
  2. Si `res.error` → setea un aviso (`gridError` o estado análogo) y corta.
  3. Convierte cada `{row, col}` 1-based → 0-based `(row-1, col-1)`.
  4. **Filtra a la ventana visible**: descarta celdas con `r >= gridCells.length` o `c >= nCols` (`nCols = max ancho de fila`). Cuenta cuántas quedaron afuera.
  5. Pinta el rol `counts` en las celdas restantes: parte de `paint` actual y setea `next[cellKey(r,c)] = "counts"` para cada una; `setPaint(next)`.
  6. Si quedaron celdas afuera de la ventana → aviso ámbar: "N celdas de conteo fuera de la vista (hoja truncada a 200×120)".
- Borrar/agregar: herramientas existentes (`counts` + `Borrar`).
- Guardar: `paintToParsedDb` sin cambios (toma `min/max` de columnas `counts` → `counts_cols`).

## Data flow

```
click "Seleccionar conteos"
  → fetchCountCells(storeState)        // estructura del parsedDb GUARDADO
  → coords 1-based
  → 0-based + filtro ventana (200×120)
  → merge rol 'counts' en PaintMap
  → setPaint  → SheetGrid resalta gris
  → usuario corrobora (borra/agrega con toolbar)
  → Guardar → paintToParsedDb (min/max col) [sin cambios]
```

## Edge cases

- **Celdas fuera de la ventana** (hoja truncada a 200×120): se filtran; aviso ámbar con el conteo de descartadas.
- **Sin preguntas/breakdowns** detectados: `cells: []`; aviso "nada que marcar".
- **Endpoint con error** (estado inválido, hoja no abre): muestra `error` en rojo (reusar `gridError`), no rompe el grid.
- **counts_cols ausente/!=2**: el backend usa `data_blocks["counts_cols"][0]` como hoy; si falta, devuelve `{error, cells: []}`.
- **Re-correr el botón**: vuelve a pintar sobre el estado actual (idempotente para las mismas celdas); no borra otros roles ya pintados salvo que una celda de conteo pise otra (se respeta el último pintado, comportamiento normal de `paint`).

## Componentes y límites

- `count_cells_endpoint` (backend): una responsabilidad — mapear estructura → coordenadas de conteo. Reusa helpers del extractor; no duplica heurística.
- `fetchCountCells` (cliente): I/O tipado, sin lógica.
- `handleSelectCounts` (wizard): orquesta fetch → convertir → filtrar → pintar; sin lógica de mapeo (vive en el backend).

## Testing

**Backend** (`backend/tests/test_api.py`):
- `test_count_cells_endpoint`: con el xlsx fixture, arma `ProjectState` (helper `_minimal_state` ya existente del test de cell-values), llama `/api/count-cells`, verifica:
  - `cells` no vacío, sin duplicados.
  - Una coordenada conocida apunta a un conteo real (ej. la celda de P1 "Sí" / general / "Total" coincide con `q_rows["Sí"]` × `counts_cols[0]`).
- `test_count_cells_endpoint_bad_state`: estado inválido → `{error, cells: []}`, status 200.

**Frontend**:
- `client`: test de `fetchCountCells` (forma de la respuesta) si hay patrón de test de cliente; si no, cubrir vía el test del handler.
- Lógica de pintado: función pura testeable que toma `(coords 1-based, gridDims) → PaintMap merge` — test de conversión 1-based→0-based, filtrado de ventana, y rol `counts` aplicado. Extraer esa función pura (p. ej. en `sheetPaint.ts`: `paintCountCells(paint, coords, nRows, nCols) → {paint, dropped}`) para testear sin render.

## Archivos afectados

- `backend/aurum_encuestas/api.py` — `CountCellsRequest` + `count_cells_endpoint`.
- `backend/tests/test_api.py` — tests del endpoint.
- `frontend/src/api/client.ts` — `CountCellsResponse` + `fetchCountCells`.
- `frontend/src/pages/Wizard/sheetPaint.ts` — `paintCountCells` (función pura) + test.
- `frontend/src/pages/Wizard/sheetPaint.test.ts` (o existente) — test de `paintCountCells`.
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` — botón + `handleSelectCounts` en `mode === "excel"`.
```
