# Quitar la feature de Entrenamiento

Fecha: 2026-08-16

## Objetivo

Remover la feature de "entrenamiento" (subir PPTs a un corpus y generar un style
guide con IA) del código, sin alterar el resto de la app. La generación de PPTX y de
análisis IA debe seguir funcionando idéntica.

Decisión del usuario: **solo código; no se borran los datos en el VPS**
(`~/.aurum/training` queda huérfano pero inofensivo).

## Contexto / acoplamiento (verificado)

- El **motor de render** de PPTX depende de dos módulos que NO son "entrenamiento":
  `pptx_generator.py:180-223` importa `pattern_classifier.classify/build_slide_config`
  y `style_guide.BUILTIN_STYLE_GUIDE/load_active`. Genera cada slide clasificando
  contra el style guide, con fallback a `BUILTIN_STYLE_GUIDE` (ya existente,
  `pptx_generator.py:188`).
  → `style_guide.py`, `pattern_classifier.py`, `pattern_renderer.py` **SE QUEDAN**.
- La feature de **entrenar** es lo removible: subir corpus + analizarlo con IA +
  editar patterns en una pantalla dedicada.
- `generate_analysis`, `suggest_layout`, `correct_slide_layout` (llm_client.py) **no**
  usan training. Intactos.
- `/api/config/recent-colors` **no** es training (config.py, agnóstico). Intacto.
- ColorPicker usa `useStyleGuideStore` solo para `styleGuide.global.suggested_palette`
  (sección "Sugeridas del training"), con fallback `?? []`.

## Alcance

### Backend — borrar

Módulos (solo-training):
- `backend/aurum_encuestas/style_guide_analyzer.py` (render corpus + visión Claude)
- `backend/aurum_encuestas/training_sets.py` (CRUD corpus)

Endpoints en `api.py` (borrar la ruta + su función):
- `POST /api/training/corpus/add`
- `GET  /api/training/corpus/list`
- `POST /api/training/corpus/delete`
- `POST /api/training/analyze-with-ai`
- `GET  /api/training/analysis-status/{job_id}`
- `GET  /api/training/style-guide`
- `PUT  /api/training/style-guide/pattern/{pattern_id}`
- `POST /api/training/clear-cache`

Imports en `api.py` que quedan sin uso al borrar los endpoints (quitar solo los que
ya no se usan; dejar los que sigan en uso):
- de `.config`: `get_corpus_dir`, `get_render_cache_dir` (solo los usaban corpus /
  clear-cache).
- de `.style_guide`: `BUILTIN_STYLE_GUIDE`, `Pattern`, `load_active_style_guide`,
  `save_style_guide` (solo endpoints de training). **Mantener `migrate_legacy_files`**
  si sigue llamándose en el lifespan (ver abajo).
- de `.training_sets` y `.style_guide_analyzer`: cualquier import (módulos borrados).
- Cualquier estado en memoria de jobs de análisis (dict de progreso) que solo servía a
  analyze-with-ai / analysis-status.

`lifespan` (`api.py`): `migrate_legacy_files()` migra archivos legacy de style guide.
Es inofensivo (crea dir con `mkdir parents=True`). **Se deja** para no tocar el
arranque; `style_guide.py` (que lo define) se queda.

### Backend — NO tocar
- `style_guide.py` (models + `BUILTIN_STYLE_GUIDE` + `load_active` + `save` +
  `migrate_legacy_files`), `pattern_classifier.py`, `pattern_renderer.py`,
  `pptx_generator.py`, `element_renderers/`, `llm_client.py`.
- `config.py`: los helpers `get_training_dir`, `get_corpus_dir`, `get_render_cache_dir`,
  `get_ai_logs_dir`, `get_analysis_logs_dir`, `get_style_guide_path`,
  `get_layout_bank_path` **se dejan** (los que queden sin uso son código muerto
  inofensivo; `get_style_guide_path`/`get_training_dir`/`get_layout_bank_path` siguen
  en uso por `style_guide.py`/`pptx_generator.py`). No se editan para minimizar riesgo.

### Frontend — borrar

- `frontend/src/pages/Training/` (TrainingPage.tsx, StyleGuideViewer.tsx,
  AnalysisProgressModal.tsx)
- `frontend/src/api/training.ts`
- `frontend/src/store/styleGuide.ts`
- Ruta `/training` + import de `TrainingPage` en `App.tsx`
- NavLink "Entrenamiento" (`to="/training"`) en `Topbar.tsx`

### Frontend — desacoplar ColorPicker

`ColorPicker.tsx`: quitar `import { useStyleGuideStore }` y la lectura de
`suggested_palette`. Reemplazar `suggestedPalette` por `[]` (o eliminar la sección
"Sugeridas del training" del render). El resto del componente —incluido
`/api/config/recent-colors`— queda igual.

### Tests — borrar
- Backend: `backend/tests/test_style_guide_analyzer.py`
- Frontend: `frontend/tests/TrainingPage.test.tsx`,
  `frontend/tests/styleGuide.store.test.ts`, `frontend/tests/training-api.test.ts`

### Tests — mantener
- Backend: `test_style_guide.py`, `test_pattern_classifier.py` (módulos que se quedan).
- Frontend: `ColorPicker.test.tsx` — revisar si mockea el styleGuide store; si sí,
  actualizarlo para no depender de él.

## Resultado esperado

- Desaparece la pantalla "Entrenamiento" y toda su navegación/backend.
- Generación de PPTX: idéntica, usando siempre `BUILTIN_STYLE_GUIDE` (comportamiento
  que ya ocurría cuando no había style guide entrenado).
- ColorPicker: sin la fila "Sugeridas del training"; recientes y defaults intactos.
- Suites de test verdes salvo los fallos pre-existentes ya conocidos.

## Verificación
- Backend: `arch -arm64 .venv/bin/pytest -q` — sin fallos nuevos; `python -c "import
  aurum_encuestas.api"` importa limpio (sin ImportError por símbolos borrados).
- Frontend: `npx tsc --noEmit` limpio (caza imports colgados a Training/styleGuide);
  `npx vitest run` sin fallos nuevos.
- Manual: la app abre, se crea proyecto, se genera PPTX, se exporta — sin la pantalla
  de entrenamiento.

## Fuera de alcance
- Borrar datos en el VPS (`~/.aurum/training`).
- Limpiar los helpers muertos de `config.py` (se dejan por seguridad).
- Cualquier cambio al motor de render / BUILTIN_STYLE_GUIDE.
