# Diseño: conteos por celda manejan la extracción

**Fecha:** 2026-06-30
**Estado:** aprobado, pendiente de plan de implementación
**Relacionado:** [[2026-06-29-count-cells-verification-design]] (auto-select + highlight de celdas de conteo)

## Problema

La feature "Seleccionar conteos" resalta (y ahora auto-selecciona al abrir el editor) las celdas de conteo detectadas. Pero las marcas son **solo visuales**: la extracción lee cada opción×categoría por geometría (filas de opción × columnas de categoría dentro de `counts_cols`), sin importar qué celdas estén marcadas. Si el usuario borra una marca para indicar "este conteo está mal / no va", el dato igual se lee.

El usuario quiere que **seleccionar/borrar marcas se aplique**: la extracción debe respetar exactamente las celdas marcadas como conteo.

## Objetivo

Que el conjunto de celdas marcadas con rol `counts` determine qué conteos se leen. Borrar la marca de una opción×categoría hace que ese conteo quede en **0**; agregarla lo incluye. Compatible hacia atrás: sin marcas guardadas, se lee todo como hoy.

## Decisiones (cerradas con el usuario)

- **Excluido = conteo 0**, la opción **sigue apareciendo** en gráfico/tabla (estructura intacta). No se omite la fila/barra.
- **Backward-compat:** `count_cells` vacío ⇒ leer todo (comportamiento actual). Proyectos existentes sin el campo no cambian.
- **Truncado:** si la hoja se mostró truncada (200×120), NO se persiste `count_cells` (queda read-all) para no poner en 0 conteos fuera de la vista. Aviso en UI.

## No-objetivos

- Remapear la celda fuente de un conteo (mover de qué celda se lee). Solo incluir/excluir.
- Editar el valor numérico inline (descartado antes).
- Tocar el modelo de overrides de valor (`value_overrides`) — sigue aplicando encima del conteo leído.

## Arquitectura

### 1. Modelo — `backend/aurum_encuestas/models.py`

Agregar a `class ParsedDB`:

```python
    count_cells: list[list[int]] = Field(default_factory=list)
```

Pares `[row, col]` **1-based** (convención openpyxl, igual que `/api/count-cells`). Lista vacía = sin filtro (leer todo).

Frontend `ParsedDB` (en `frontend/src/types/index.ts`):

```ts
  count_cells?: number[][]
```

### 2. Extracción — `backend/aurum_encuestas/data_extractor.py`

Ambas funciones (`extract_chart_data`, `extract_all_breakdowns_data`) reciben un nuevo parámetro `count_cells: list | None = None` (último, después de `overrides`).

Helper de normalización (cerca de `_override_key`):

```python
def _count_cell_set(count_cells: list | None) -> set[tuple[int, int]] | None:
    """list[[row,col]] → set of (row,col); None/empty → None (sin filtro)."""
    if not count_cells:
        return None
    return {(int(r), int(c)) for r, c in count_cells}
```

En el loop de cada opción×categoría, **antes** de aplicar overrides, después de leer `count_v` de la celda:

```python
            if cset is not None and (row, col) not in cset:
                count_v = 0
```

donde `cset = _count_cell_set(count_cells)` se calcula una vez al inicio de la función, y `row`/`col` son los mismos `(q_rows[opt], breakdown_cols[cat])` 1-based que ya se usan para leer la celda. El `pct` se recalcula de `count_v` como hoy (`count_v / total_v` → 0.0 cuando `count_v == 0`). El bloque de `overrides` queda **después**, intacto: un override explícito puede re-subir un conteo excluido.

### 3. Callers — pasar `count_cells`

Igual que se pasó `overrides` en la feature previa:
- `pattern_classifier.py`: ambas llamadas → `count_cells=getattr(parsed_db, "count_cells", None)`.
- `api.py`: las llamadas a `extract_chart_data` / `extract_all_breakdowns_data` (analysis-context, suggest-layout, cell-values) → `count_cells=state.parsed_db.count_cells`.
- `pptx_generator.py`: `extract_chart_data(...)` → `count_cells=state.parsed_db.count_cells if state.parsed_db else None`.

`/api/cell-values` también pasa `count_cells` para que el crosstab de "Editar campos" refleje los conteos excluidos.

### 4. Guardado — `frontend/src/pages/Wizard/sheetPaint.ts`

`paintToParsedDb(cells, paint, prev, truncated = false)` gana un parámetro `truncated`:

- Junta las celdas con rol `counts`: `count_cells = [[r+1, c+1], ...]` (1-based), ordenadas.
- Si `truncated` es `true`: `count_cells = prev.count_cells ?? []` (no re-derivar; evita poner en 0 lo de afuera de la vista).
- Devolver `count_cells` dentro del db: `{ ...prev, ..., count_cells }`.
- `counts_cols` se sigue derivando como hoy (geometría de columnas para resolver categorías).

En `XlsxVerifyWizard.tsx`, el botón **Guardar** del modo excel pasa `gridTruncated`:

```tsx
const { db, warnings } = paintToParsedDb(gridCells, paint, parsedDb!, gridTruncated)
```

Si `gridTruncated`, mostrar antes de guardar un aviso (ej. en `warnings` o un texto): "Hoja truncada — la exclusión por celda queda deshabilitada (se leen todos los conteos)."

## Data flow

```
abrir Excel → auto-marca todas las celdas de conteo detectadas (/api/count-cells)
  → usuario borra/agrega marcas (paint interactivo)
  → Guardar → paintToParsedDb (count_cells = celdas 'counts' pintadas, 1-based)
            → setParsedDb({...db, count_cells})
  → extract_chart_data/all_breakdowns(count_cells=...) → celda no marcada ⇒ count 0
  → override (si existe) aplica encima
```

## Edge cases

- **`count_cells` vacío:** sin filtro, lee todo (legacy + proyectos viejos).
- **Hoja truncada:** no se persiste `count_cells` (read-all) + aviso. Exclusión por celda deshabilitada en ese caso.
- **Guardar sin tocar marcas:** tras auto-select, `count_cells` = todas las detectadas ⇒ equivalente a leer todo.
- **Borrar una columna entera del bloque:** `counts_cols[0]` (start) podría correr y mover la resolución de categorías. Documentado; el caso normal (borrar celdas sueltas) no lo toca.
- **Override sobre celda excluida:** el override gana (se aplica después del forzado a 0). Consistente con que el override es un valor manual explícito.

## Componentes y límites

- `_count_cell_set` (backend): normaliza lista→set, una responsabilidad.
- Filtro en extractores: una línea por loop, antes de overrides; no duplica geometría.
- `paintToParsedDb`: ya arma el db; suma `count_cells` + guard de truncado.

## Testing

**Backend** (`backend/tests/test_data_extractor.py`):
- `test_count_cells_filter_excludes_unmarked`: con `count_cells` que incluye P1 "Sí"/general/Total pero NO "No" → `data["Total"]["Sí"]["count"] == 458` y `data["Total"]["No"]["count"] == 0` (pct 0.0).
- `test_count_cells_empty_reads_all`: `count_cells=None` (o `[]`) → conteos sin cambios (igual que hoy).
- `test_count_cells_override_wins`: celda excluida por `count_cells` pero con override `{count: 5}` → resultado 5 (override aplica después).

**Frontend** (`frontend/src/pages/Wizard/sheetPaint.test.ts`):
- `paintToParsedDb` emite `count_cells` 1-based para cada celda pintada `counts`.
- Con `truncated=true`, `count_cells` se mantiene de `prev` (no re-deriva).

## Archivos afectados

- `backend/aurum_encuestas/models.py` — `count_cells` en `ParsedDB`.
- `backend/aurum_encuestas/data_extractor.py` — `_count_cell_set` + filtro en ambas funciones.
- `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` — pasar `count_cells`.
- `backend/tests/test_data_extractor.py` — tests del filtro.
- `frontend/src/types/index.ts` — `count_cells?` en `ParsedDB`.
- `frontend/src/pages/Wizard/sheetPaint.ts` — `paintToParsedDb` emite `count_cells` + guard truncado.
- `frontend/src/pages/Wizard/sheetPaint.test.ts` — tests.
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` — pasar `gridTruncated` a `paintToParsedDb` + aviso.
```
