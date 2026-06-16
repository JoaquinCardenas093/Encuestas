# AurumEncuestas — Design Spec

**Fecha:** 2026-06-16
**Estado:** Brainstorming → Spec aprobado, pendiente plan de implementación
**Autor:** Joaquín Cardenas + Claude (brainstorming asistido)

---

## 1. Overview

**AurumEncuestas** es una app web local single-user que genera presentaciones PPT editables a partir de encuestas tabuladas en Excel. El usuario sube tres cosas:

1. **DB xlsx** — datos tabulados de encuesta (preguntas, opciones, breakdowns demográficos)
2. **Template pptx** — archivo de 2 slides (shell vacío + separador) con branding/placeholders
3. **Training PPTs** (opcional, varios) — corpus de decks finalizados de los que la app aprende layouts y estilos de chart

La app:
- Parsea automáticamente el xlsx detectando preguntas, opciones, breakdowns y sus tres bloques de columnas (conteos, %fila, %col)
- Permite armar slides eligiendo qué preguntas mostrar, con qué breakdowns, qué tipos de chart, y qué análisis de texto incluir
- Auto-decide layouts usando un banco aprendido del corpus de entrenamiento; cae a una heurística determinística si no hay match; opcionalmente pide a Claude que sugiera un layout alternativo
- Genera análisis de texto con Claude Haiku 4.5 (editable por el usuario antes de aceptar)
- Renderiza preview de cada slide en tiempo real vía LibreOffice headless
- Exporta el deck final como `.pptx` editable preservando branding del template

La app es **genérica** — no hardcodea ninguna marca ni convención específica del cliente Aurum. El template aporta todo el look-and-feel del output.

### Out of scope (MVP)

- Multi-usuario, autenticación, colaboración en vivo
- Edición de intro/portada/metodología en la app (el deck final son solo slides generadas; el usuario añade portada/metodología en PowerPoint si las quiere)
- Generación automática del template o del separador (los provee el usuario)
- Versionado automático de proyectos (`.bak`)
- Telemetría externa, analytics
- Branding hardcodeado de Aurum o cualquier cliente
- Tipos de chart fuera de los 9 soportados (sin treemap, gauge, sankey, etc.)
- LLM como decisor primario de layouts (solo on-demand)

---

## 2. Arquitectura

### Stack

**Frontend:**
- React 18 + TypeScript + Vite
- Estado: zustand + zundo (undo/redo middleware)
- Estilos: Tailwind CSS
- Drag-drop: @dnd-kit/sortable
- Iconos: Lucide

**Backend:**
- Python 3.11+
- FastAPI + uvicorn
- openpyxl (parsing xlsx)
- python-pptx (lectura/escritura pptx, manipulación de shapes y charts)
- Anthropic SDK (LLM)
- LibreOffice headless (rasterización de slides para preview)

**Comunicación:** REST stateless. El frontend es autoridad del state. El backend hace transformaciones puras: parse, render, generate, export. No hay sesión server-side ni WebSocket.

**Persistencia:** archivos JSON en disco (`*.aurum.json` por proyecto, `~/.aurum/` para config global y corpus de training). Sin base de datos.

### Procesos en desarrollo (`make dev`)

1. Backend: `uvicorn aurum_encuestas.api:app --port 8000`
2. Frontend: `vite dev` en puerto 5173, con proxy `/api` → `:8000`
3. Usuario abre `http://localhost:5173`

### Dependencias externas que el usuario debe tener instaladas

- Python 3.11+
- Node 20+
- LibreOffice (provee `soffice --headless --convert-to png`)
- API key Anthropic en archivo `.env`

### Endpoints backend (resumen)

| Endpoint | Propósito |
|---|---|
| `POST /api/parse-xlsx` | Recibe xlsx, devuelve estructura detectada (preguntas, breakdowns, bloques, sample_size) |
| `POST /api/parse-template` | Recibe template.pptx, valida (2 slides + `@Titulo`), extrae shell + separador + zona libre + placeholders |
| `POST /api/preview-slide` | Recibe slide config JSON, devuelve PNG bytes del render |
| `POST /api/generate-analysis` | Recibe `{scope, target, context}`, llama Haiku con prompt cache, devuelve texto |
| `POST /api/suggest-layout` | Recibe slide config, llama Haiku para layout alternativo |
| `POST /api/training/add-pptx` | Sube training PPT, extrae layouts/styles, actualiza `layout_bank.json` |
| `POST /api/training/reprocess` | Re-procesa todos los training PPTs |
| `GET /api/training/bank` | Devuelve `layout_bank.json` actual |
| `POST /api/export-pptx` | Recibe project state, genera pptx, escribe a path |
| `GET /api/recents` / `POST /api/recents` | Lista/actualiza últimos 5 proyectos |

---

## 3. Modelo de datos

### Project state (`*.aurum.json`)

```jsonc
{
  "version": 1,
  "app_name": "AurumEncuestas",
  "project_name": "Estudio violencia 2026",
  "created_at": "2026-06-16T22:00:00Z",
  "updated_at": "2026-06-16T22:14:00Z",

  "inputs": {
    "db_path": "./BD.xlsx",                    // relativo al .aurum.json
    "template_path": "./template.pptx",
    "font_override": "Open Sans"               // null si usuario no eligió
  },

  "parsed_db": {                               // cache de parsing, sobrevive al cierre
    "questions": [
      {"id": "q1", "code": "P1", "text": "¿Recuerda...?", "options": ["Sí", "No"], "confidence": 1.0}
    ],
    "breakdowns": [
      {"id": "general", "label": "General", "categories": ["Total"]},
      {"id": "sexo", "label": "Sexo", "categories": ["Hombre", "Mujer"]},
      {"id": "edad", "label": "Rango de edad", "categories": ["18-39", "40-59"]},
      {"id": "nse", "label": "NSE", "categories": ["Alto", "Medio", "Bajo superior", "Bajo inferior", "Marginal"]},
      {"id": "punto", "label": "Punto", "categories": ["..."]}
    ],
    "sample_size": 500,
    "data_blocks": {
      "counts_cols": [3, 17],
      "pct_row_cols": [21, 35],
      "pct_col_cols": [41, 55]
    }
  },

  "slides": [
    { "id": "sl_001", "type": "separator", "title": "Caracterización de la muestra" },
    {
      "id": "sl_002",
      "type": "shell",
      "charts": [
        {
          "id": "ch_001",
          "question_id": "muestra",            // pseudo-pregunta para caracterización
          "breakdown_id": "sexo",
          "chart_type": "PIE",                 // PIE|DONUT|BAR|COLUMN|BAR_STACKED|COLUMN_STACKED|LINE|AREA|RADAR
          "multi_series": false
        }
      ],
      "analyses": [
        { "id": "an_001", "scope": "chart", "target_id": "ch_001", "text": "El 50%...", "ai_generated": true, "edited": false },
        { "id": "an_002", "scope": "slide", "target_id": null, "text": "Resumen...", "ai_generated": true, "edited": true }
      ],
      "auto_notes": "Respuesta única. Número de observaciones: 500."
    },
    { "id": "sl_003", "type": "separator", "title": "Recordación espontánea" }
  ],

  "history": {                                 // zundo snapshots persistidos
    "past": [/* últimos N snapshots de state */],
    "future": []
  }
}
```

### Globales (`~/.aurum/`)

```
~/.aurum/
├── config.json                # recientes, prefs UI
├── training/
│   ├── deck_a.pptx
│   ├── deck_b.pptx
│   └── layout_bank.json       # banco extraído del corpus
```

`config.json`:

```jsonc
{
  "recents": [
    {"path": "/Users/joa/proyectos/violencia.aurum.json", "name": "Estudio violencia 2026", "opened_at": "..."},
    "..."
  ],
  "ui": {"theme": "dark"}
}
```

### Reglas de modelo

- **Tipos de slide:** `separator` o `shell`. Nada más en MVP.
- **Herencia de título:** todo `shell` hereda el título del último `separator` previo en la lista. No hay override per-shell.
- **Slide sin separador previo:** el botón `+ Slide` está deshabilitado hasta que exista al menos un separador.
- **Numeración de separadores:** auto-incremental por posición en la lista (1., 2., 3., ...). Se renumera al reordenar.
- **Pseudo-pregunta `muestra`:** representa los datos de caracterización demográfica (rows 4-17 del xlsx). Se trata exactamente como cualquier otra pregunta para fines de chart-building.
- **Multi-serie:** toggle por chart. Default `false` (una serie agregada). `true` desglosa por sub-categorías del breakdown.

---

## 4. Flujos core

### 4.1 Nuevo proyecto

1. Topbar `Nuevo` → pantalla vacía con prompts para los 3 inputs
2. Sube `template.pptx` → backend valida que tenga exactamente 2 slides (shell + separador) y `@Titulo` en ambos. Si falla, banner rojo.
3. Sube `xlsx` → backend parsea con heurística → devuelve `parsed_db`
4. **Wizard de verificación** (siempre, 1 click default):
   - Lista preguntas detectadas con texto + count de opciones + ✓/⚠ confianza
   - Lista breakdowns detectados con categorías
   - Bloques de columnas detectados (counts/%row/%col)
   - Dropdown opcional "Fuente" (lista curada + opción "Custom" con input texto)
   - Si todo en verde → botón "Confirmar" (1 click, Enter)
   - Si hay rojo → "Editar mapping manual" abre wizard de corrección
5. Entra al Editor. State inicial: `slides: []`. Botón `+ Slide` deshabilitado hasta crear separador.

### 4.2 Agregar slides

- **`+ Separador`** (botón rail) → modal con input `Título sección` + `Crear`. Inserta `{type: "separator", title}` al final del rail. Renderiza thumbnail con estilo distintivo (color/icono).
- **`+ Slide`** (botón rail, habilitado si hay separador) → inserta `{type: "shell", charts: [], analyses: []}` al final, hereda título del último separador. Aparece thumbnail en rail. Backend renderiza preview vacío (solo branding + título).

### 4.3 Agregar charts

1. Slide shell seleccionada → panel derecho `+ Chart`
2. Modal:
   - Dropdown pregunta (catálogo detectado, incluye pseudo-pregunta `muestra`)
   - Multi-select breakdowns (General, Edad, Sexo, NSE, Punto)
   - Dropdown tipo de chart (auto-sugerido según pregunta+breakdown, editable)
   - Toggle multi-serie (default off)
   - Botón `Aplicar`
3. Crea N charts (uno por breakdown seleccionado, todos con el mismo tipo y toggle). Una operación = un snapshot de undo.
4. Backend re-renderiza el preview de la slide (debounced 500ms tras último cambio).
5. Cambio de tipo individual post-creación: clickear chart en preview o en lista del panel → abre config del chart → cambia tipo solo de ese chart.

### 4.4 Agregar análisis

1. Panel derecho `+ Análisis`
2. Modal:
   - Radio scope: `slide` / `pregunta` / `chart`
   - Si scope = pregunta → dropdown pregunta
   - Si scope = chart → dropdown chart
   - Botón `Generar`
3. Backend llama Haiku con contexto apropiado al scope; devuelve texto
4. Modal muestra texto generado en textarea editable
5. Botones `Aceptar` / `Editar` (queda en textarea) / `Regenerar`
6. Al aceptar, se agrega al `analyses` de la slide y se re-renderiza preview

### 4.5 Reordenar slides

- Drag-drop de thumbnails en rail izquierdo (`@dnd-kit/sortable`)
- Si se arrastra un shell entre secciones (cambia de separador padre), su título auto se actualiza al nuevo separador
- Si se mueve un separador, todos los shells entre ese separador y el siguiente cambian de sección
- Numeración auto se recalcula por posición

### 4.6 Undo / Redo

- Snapshot pattern (zundo middleware sobre zustand). Cada acción atómica = un snapshot del state JSON.
- Atajos: `Cmd+Z` / `Cmd+Shift+Z`. Botones en footer.
- "Reset slide" = revert state.slides[idx] al snapshot inicial de esa slide.
- "Reset todo" = clear history + state vacío (vuelve a paso post-wizard).
- History persiste en `.aurum.json` y sobrevive al cierre de la app.
- Stack limitado a 100 snapshots por proyecto (~2-5 KB cada uno).

### 4.7 Training

1. Tab `Entrenamiento` en topbar → vista propia
2. Tabla de PPTs subidos (en `~/.aurum/training/`): nombre, fecha agregado, count de layouts extraídos, status (✓/⏳/⚠), acciones
3. Botón `+ Agregar PPT entrenamiento` → upload → backend extrae layouts/chart styles/text styles → actualiza `layout_bank.json` global
4. Indicador en encabezado: `Banco: N layouts de M PPTs`
5. `Ver layouts` por PPT → modal con thumbnails de cada layout aprendido
6. `Re-procesar todo` → re-train forzado del banco completo
7. `Eliminar` PPT → quita del corpus y re-train

### 4.8 Export

1. Topbar `Exportar PPTX` → modal:
   - Input nombre (default `AurumEncuestas_YYYYMMDD_HHMM.pptx`)
   - Input carpeta (default `~/Downloads/`)
   - Checkbox `Abrir en PowerPoint al terminar` (default ON)
   - Botón `Exportar`
2. Backend:
   - Copia `template.pptx` a path destino
   - Borra las 2 slides del template (shell + separador) — se usaron solo como source
   - Por cada slide en state: clona el layout source apropiado (shell o separador), rellena placeholders `@Titulo` / `@Notas` / etc., agrega shapes de charts + análisis según layout decidido
   - Guarda
3. Progress bar slide por slide (cache de renders ya tibio)
4. Toast `✓ Exportado a /path` + botón `Abrir carpeta`
5. Si `Abrir en PowerPoint` = ON: lanza el archivo con el handler default del SO

---

## 5. Parser xlsx (auto-detect heurística)

**Estrategia:** auto-detect con verificación humana siempre (wizard 1-click). No se asume convención estricta.

### Heurísticas

**Detección de filas de pregunta:**
- Col A no vacía y matchea uno de:
  - Prefijo `$pN.label` (literal `$p` + dígitos + `.` + texto)
  - Texto termina en `?` (pregunta directa)
  - Texto largo (>40 chars) seguido de N filas con texto corto en col B (opciones)

**Detección de filas de opción:**
- Col A vacía, col B no vacía, col C+ con números

**Detección de breakdown columns:**
- Row 1 tiene celdas con texto en posiciones discontinuas → cada texto es el nombre de breakdown
- Row 2 tiene categorías de cada breakdown debajo del header de su grupo
- Primer columna después de "Total" en row 3 = `General`

**Detección de los 3 bloques de columnas:**
- Recorre cols de izq a der. Cuando aparece `General` en row 2 después de un grupo cerrado, empieza nuevo bloque.
- Bloque 1: valores > 1 → es conteos
- Bloque 2: valores 0-1 → es % (de fila o de col según el valor; típicamente %fila)
- Bloque 3: valores 0-1 → otro %

**Confianza por pregunta:**
- 1.0 si matchea `$pN.label`
- 0.9 si termina en `?` y tiene ≥2 opciones reconocibles
- 0.7 si solo tiene texto largo + opciones
- < 0.7 → marca ⚠ en el wizard, pide confirmación humana

### Wizard de verificación

Pantalla simple post-parse:

```
Preguntas detectadas (N):
  ✓ P1: ¿Recuerda usted...? (2 opciones)
  ✓ P2: $p2.mensajes (14 opciones)
  ⚠ P3: $p3.llamado.acción (10 opciones, confianza 0.7)
  ...

Breakdowns detectados:
  ✓ General (1 categoría)
  ✓ Sexo (Hombre, Mujer)
  ✓ Rango de edad (2 categorías)
  ✓ NSE (5 categorías)
  ✓ Punto (5 categorías)

Bloques de columnas:
  ✓ Conteos: C3-C17
  ✓ % de fila: C21-C35
  ✓ % de columna: C41-C55

Sample size: 500
Fuente (opcional): [Default del template ▼]

[ Editar mapping manual ]      [ Confirmar ]
```

Click `Confirmar` (Enter) → entra al editor.

---

## 6. Layout engine

### Signature de slide

Tupla determinística:

```
(N_charts, [chart_types ordenados], N_chart_analyses, N_question_analyses, has_slide_analysis)
```

Ejemplo: `(2, [PIE, BAR_CLUSTERED], 1, 0, 1)`

### Pipeline

```
slide_config
  → signature
  → match layout_bank por signature
  → match exacto? → aplica learned layout
  → no match? → heurística A (grid determinístico)
  → (opcional, on-demand) AI suggest layout via Haiku
  → python-pptx escribe shapes
  → libreoffice render → PNG (preview)
```

### Layout bank (`~/.aurum/training/layout_bank.json`)

```jsonc
{
  "extracted_at": "2026-06-16T20:00:00Z",
  "source_pptxs": ["deck_a.pptx", "deck_b.pptx"],
  "layouts": [
    {
      "id": "lay_001",
      "signature": "2|PIE,BAR_CLUSTERED|1|0|1",
      "source": "deck_a.pptx#slide17",
      "free_area": { "x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000 },  // EMU
      "elements": [
        { "role": "chart_0", "x": 600000, "y": 1200000, "cx": 5000000, "cy": 4000000, "chart_type": "PIE" },
        { "role": "chart_1", "x": 6000000, "y": 1200000, "cx": 5000000, "cy": 4000000, "chart_type": "BAR_CLUSTERED" },
        { "role": "chart_analysis_0", "x": 600000, "y": 5300000, "cx": 5000000, "cy": 900000, "anchor_chart": 0 },
        { "role": "slide_analysis", "x": 600000, "y": 6300000, "cx": 11000000, "cy": 500000 }
      ],
      "chart_style": {
        "PIE": { "colors": ["#2A4D8F", "#FFC940", "#6B8FC9"], "data_labels": true, "legend": "right", "font": "Calibri", "font_size": 10 },
        "BAR_CLUSTERED": { "...": "..." }
      },
      "text_style": {
        "chart_analysis": { "font": "Calibri", "size": 9, "color": "#555555", "fill": "#F7F3E8", "border_left": "#FFC940" },
        "slide_analysis": { "...": "..." }
      }
    }
  ]
}
```

### Heurística A (fallback determinística)

1. Canvas = `template.shell.free_area` (calculado al subir template). Algoritmo: arranca con el rect completo del slide, resta el bbox de cada shape fijo y placeholder. El rect libre resultante (el más grande contiguo) es el canvas. Si el template tiene shapes muy distribuidos, el canvas puede ser pequeño — se loguea warning.
2. Grid charts: `N → (rows, cols)` con tabla:
   - 1 → 1×1
   - 2 → 1×2
   - 3 → 1×3 (o 2×2 con el último centrado)
   - 4 → 2×2
   - 5-6 → 2×3
   - 7-9 → 3×3
   - >9 → bloqueado en MVP. Modal warning "Máximo 9 charts por slide. Reducí o creá otra slide manual."
3. Reservar zona inferior (15% alto) para `slide_analysis` si existe
4. Reservar zona adyacente a cada chart con `chart_analysis` (debajo si chart ancho > alto, derecha si no)
5. `question_analysis`: caja debajo del bloque de charts de esa pregunta (charts agrupados por `question_id`)
6. Padding 10px, fonts/colors heredados del primer `text_style` del banco (o default `Inter 10pt #333` si banco vacío)

### AI suggest layout

Botón en panel derecho. Llama Haiku:

- **System (cacheable):** "Sos diseñador de slides. Te paso config slide en JSON. Devolvé JSON con posiciones EMU para cada elemento (charts y análisis), respetando free_area canvas. No overlaps. Padding mínimo 200000 EMU. Output: solo JSON válido."
- **User:** slide config + dims canvas + N elementos requeridos

Validación post-response:
- JSON parseable
- Coords todas dentro de canvas
- No overlaps (rectángulos disjuntos)
- Cubre todos los elementos requeridos
- Si falla validación → 1 retry, luego fallback heurística A
- Resultado se muestra como alternativa overlay. Usuario `Aceptar` o `Descartar`.

---

## 7. LLM integration (análisis)

### Modelo

`claude-haiku-4-5-20251001`

### Endpoint backend

`POST /api/generate-analysis`

Input:
```jsonc
{
  "scope": "slide" | "question" | "chart",
  "slide_id": "sl_002",
  "question_id": "q1",            // requerido si scope == "question"
  "chart_id": "ch_001",           // requerido si scope == "chart"
  "context": {                    // datos crudos ya filtrados al scope por el frontend
    "section_title": "Recordación espontánea",
    "question_text": "¿Recuerda...?",
    "options": ["Sí", "No"],
    "breakdown_label": "Sexo",
    "data": {                     // counts + percentages, ya filtrados al scope
      "Hombre": { "Sí": { "count": 229, "pct": 0.916 }, "No": { "count": 21, "pct": 0.084 } },
      "Mujer":  { "Sí": { "count": 229, "pct": 0.916 }, "No": { "count": 21, "pct": 0.084 } }
    }
  }
}
```

Output:
```jsonc
{ "text": "El 91.6% de los encuestados...", "tokens_in": 250, "tokens_out": 87, "cached": true }
```

### Prompt structure (con prompt caching)

```
system: [cache_control: ephemeral, ttl: 1h]
  Sos analista de encuestas. Generás análisis técnicos breves en español neutral.
  Tono: formal técnico, sin emojis, sin recomendaciones de acción salvo pedido.
  Formato: 2-4 oraciones. Frases tipo "El X% de los encuestados...".
  Datos: respetar números exactos provistos, no inventar cifras.
  Si scope=chart: analizás SOLO ese chart específico (distribución, mayoría, contraste por categoría).
  Si scope=question: te paso TODOS los charts de la slide que pertenecen a esa pregunta. Comparás entre breakdowns, identificás patrones cruzados de esa pregunta.
  Si scope=slide: te paso TODOS los charts de la slide (de cualquier pregunta). Sintetizás insights cruzados entre charts y preguntas.
  Idioma: español neutral. Longitud máxima: 4 oraciones.

user:
  Sección: "{section_title}"
  Pregunta: "{question_text}"
  Opciones: {options_list}
  Breakdown: {breakdown_label}
  Datos: {data_json}
  Scope: {scope}
  Target: {chart_or_question_or_slide}
```

System cacheable → 85% de los tokens input son cache-hits en sesiones largas.

### Errores

| Error | Fallback |
|---|---|
| API timeout | Texto `[Análisis no disponible — editar manualmente]` + botón retry |
| API key inválida | Mismo fallback + banner global "Configurá ANTHROPIC_API_KEY en .env" |
| Rate limit (429) | Mismo fallback + retry con backoff exponencial (3 intentos máx) |
| Response vacío o > 500 chars | Trunca + warning |
| Sin internet | Mismo fallback |

Nunca bloquea la slide. Usuario puede editar manualmente y avanzar.

### Costo estimado

Haiku 4.5: ~$1/M input, $5/M output.

Por análisis típico:
- Input: ~250 tokens (85% cached → costo efectivo ~40 tokens "frescos")
- Output: ~150 tokens
- Costo: ~$0.0009/análisis

Sesión típica 30 análisis = ~$0.03.

---

## 8. UI Structure

### Topbar (global, persiste entre tabs)

- Logo texto: `AurumEncuestas`
- Tabs: `Editor` (default) | `Entrenamiento`
- Botones (en Editor): `Nuevo` `Abrir` `Guardar` `Exportar PPTX`
- Pills de estado: `DB: BD.xlsx ✓` `Template: shell.pptx ✓` `Font: Open Sans`
- Dropdown bajo `Abrir`: lista recientes (últimos 5 con path completo)

### Tab Editor — 3 columnas + footer

| Zona | Ancho | Contenido |
|---|---|---|
| Rail izq | 130px | Thumbnails slides (separadores con color/icono distinto), botones `+ Slide` y `+ Separador` abajo, drag-drop reorder |
| Preview centro | flex | PNG render de slide actual (libreoffice). Overlay invisible con bounding boxes clickeables → click selecciona chart/análisis y abre su config en panel derecho. Spinner mientras renderiza. |
| Config panel der | 320px | Si slide separator: input `Título sección`. Si shell: input título (read-only, viene del separador previo) + lista Charts (add/edit/del/cambiar tipo) + lista Análisis (add/edit/del/regenerar) + botón `AI sugiere layout` + info `Usando: heurística A` o `Layout aprendido #lay_001` |
| Footer | alto fijo | `↶ Undo` `↷ Redo` `Reset slide` `Reset todo` · `Auto-guardado 22:14 ✓` |

### Tab Entrenamiento — layout simple

- Encabezado: `Banco aprendido: N layouts de M PPTs`
- Botón `+ Agregar PPT entrenamiento`
- Tabla: nombre archivo | fecha agregado | layouts extraídos | status | acciones (`Ver layouts` / `Eliminar`)
- Botón `Re-procesar todo`
- Click `Ver layouts` → modal con thumbnails de cada layout aprendido del PPT

### Modales clave

- **Wizard verificación xlsx**: lista preguntas + breakdowns + bloques + dropdown fuente + `Confirmar` (default Enter)
- **+ Chart**: pregunta + multi-select breakdowns + tipo (auto-sugerido) + toggle multi-serie + `Aplicar`
- **+ Análisis**: scope radio + target dropdown + `Generar` → textarea editable → `Aceptar` / `Regenerar`
- **+ Separador**: input título + `Crear`
- **Exportar PPTX**: nombre + carpeta + checkbox abrir + `Exportar`
- **Re-localizar archivos**: si paths relativos rotos al abrir proyecto

### Atajos de teclado

- `Cmd+Z` / `Cmd+Shift+Z` — undo / redo
- `Cmd+S` — save
- `Cmd+E` — exportar
- `Cmd+N` — nueva slide (cuando shell habilitada)

### Tema visual

- Dark mode: `bg #1A1A1A`, paneles `#1D1D1D`, hover `#232323`
- Acento amber `#FFC940` (botones primarios, indicadores activos, separadores en rail)
- Preview: siempre fondo blanco (refleja slide real)
- Tipografía UI: `Inter` / `-apple-system`
- Idioma UI: español neutral

---

## 9. Persistencia

### Por proyecto (`*.aurum.json`)

- Ubicación: elegida por el usuario (carpeta arbitraria). Paths a xlsx y template son **relativos** al `.aurum.json`.
- Auto-save cada 5 segundos (debounced) si el proyecto está abierto y tiene path conocido.
- `Guardar como` duplica a nuevo path y cambia path activo.
- History incluida — sobrevive al cierre de la app.

### Globales (`~/.aurum/`)

- `config.json` — recientes (max 5, paths absolutos), prefs UI (theme). No guarda API key.
- `training/*.pptx` — corpus de training PPTs (copias persistidas)
- `training/layout_bank.json` — banco extraído. Re-generado al agregar/quitar/reprocesar PPT.

### Cache de render

- En memoria del backend, keyed por `slide_id`. Invalidado cuando la slide cambia.
- Sobrevive vida del proceso backend, no a restart.

### API key

- Archivo `.env` en root del repo (dev) o `~/.aurum/.env` (instalado).
- Variable: `ANTHROPIC_API_KEY=sk-ant-...`
- Backend lee al startup. Si falta → banner global pide configurarla.

---

## 10. Template requirements

El template `.pptx` debe cumplir:

1. **Exactamente 2 slides** (ni más ni menos), en este orden:
   - **Slide 1 = shell** (canvas para charts + análisis)
   - **Slide 2 = separador** (sección divider)

   La app distingue por posición. Si el orden está invertido, el wizard de carga muestra warning y permite swap manual (radio "Slide 1 es shell" / "Slide 2 es shell").
2. Cada slide debe tener un textbox con `@Titulo` exacto en su contenido
3. Opcionalmente, slide shell puede tener textbox `@Notas` (si no existe, las notas no se renderizan)
4. Shapes/textboxes fijos (logo, líneas, branding) se preservan al clonar
5. Tamaño slide: 16:9 estándar (13.33×7.5 in) recomendado. Otros tamaños funcionan pero el área libre se recalcula.
6. Fuente del template define defaults (override con font picker al subir xlsx)

**Variables `@` soportadas (MVP):** `@Titulo`, `@Notas`. Futuras: `@Subtitulo`, `@NumSlide`, `@Fecha`.

**Validación al subir template:**
- 2 slides exactas → si no, error "Template requiere exactamente 2 slides (shell + separador)"
- `@Titulo` presente en cada → si falta, error "Slide N no tiene placeholder `@Titulo`"
- Logs los placeholders detectados al frontend (pill info: "Placeholders: @Titulo, @Notas")

---

## 11. Tipos de chart soportados

9 tipos (matchean `XL_CHART_TYPE` de python-pptx):

| App | python-pptx | Auto-sugerido para |
|---|---|---|
| `PIE` | `PIE` | Pregunta binaria + breakdown General |
| `DONUT` | `DOUGHNUT` | Idem PIE (alternativa estilística) |
| `BAR` | `BAR_CLUSTERED` | Pregunta múltiple opción + breakdown multicategoría |
| `COLUMN` | `COLUMN_CLUSTERED` | Pregunta con opciones ordinales |
| `BAR_STACKED` | `BAR_STACKED` | Multi-serie con suma 100% |
| `COLUMN_STACKED` | `COLUMN_STACKED` | Idem stacked |
| `LINE` | `LINE` | Series temporales (no aplicable a Aurum default, disponible) |
| `AREA` | `AREA` | Idem línea |
| `RADAR` | `RADAR` | Comparativos multi-dimensional |

**Auto-sugerencia (heurística):**
- Pregunta con 2 opciones + breakdown 1 categoría (General) → `PIE`
- Pregunta con 3-5 opciones + breakdown General → `PIE` o `DONUT`
- Pregunta con 6+ opciones → `BAR` (horizontal, mejor legibilidad)
- Breakdown con ≥3 categorías → `BAR_CLUSTERED` o `COLUMN_CLUSTERED`
- Toggle multi-serie ON → forzar `BAR_CLUSTERED` o `COLUMN_CLUSTERED`

Usuario puede overrider en cualquier momento desde el panel derecho.

---

## 12. Testing

### Backend (pytest)

- `test_xlsx_parser.py` — fixtures con xlsx de distintas formas, asserts sobre preguntas/breakdowns/bloques detectados
- `test_layout_engine.py` — signatures, matching, heurística A produce coords válidas, no overlaps
- `test_pptx_generator.py` — generación pptx con shapes correctas, fonts aplicadas, charts con data correcta
- `test_llm_client.py` — mock Anthropic API, prompt structure, error handling, prompt cache markers
- `test_training_extractor.py` — parser de PPT entrenamiento extrae layouts esperados
- `test_template_validator.py` — rechaza templates inválidos, acepta válidos
- `test_project_store.py` — round-trip JSON, paths relativos, recientes

### Frontend (vitest + @testing-library/react)

- `store.test.ts` — zustand actions, undo/redo, snapshots, herencia título de separador
- `SlideRail.test.tsx` — drag reorder, separator vs shell, disable `+ Slide` sin separador, renumera separadores
- `ConfigPanel.test.tsx` — add chart modal, add análisis modal, edit chart type
- `Preview.test.tsx` — bbox click selecciona chart
- `TrainingPage.test.tsx` — agregar/eliminar/reprocesar

### E2E (Playwright, smoke)

- Cargar xlsx + template → wizard → editor → agrega separador → agrega slide → agrega chart → agrega análisis → exporta → archivo `.pptx` existe en path esperado

**Coverage target:** ~70%. TDD per feature (per `superpowers:test-driven-development`).

---

## 13. Manejo de errores

| Escenario | Comportamiento |
|---|---|
| xlsx malformado | Banner rojo "No se pudo parsear: <razón>". Botón "Reintentar otro archivo". Bloquea editor. |
| Template sin 2 slides o sin `@Titulo` | Banner rojo "Template inválido: <razón>". Link a docs. Bloquea editor. |
| LLM API down / key inválida | Texto fallback `[Análisis no disponible — editar manualmente]` + retry icon. No bloquea slide. |
| LibreOffice falla render | Placeholder "[Render error — preview no disponible]" + retry. Export sigue funcionando. |
| Signature sin match + heurística falla | Fallback hard: charts en grid 1×N centrado, análisis stacked debajo. Log warning visible en panel. |
| Disco lleno al save | Toast error + retry. State queda en memoria. |
| Paths xlsx/template rotos al abrir proyecto | Modal "Re-localizar archivos" pide selección manual. |
| Training PPT corrupto | Marca PPT como ⚠ con razón. Sigue procesando los demás. |

---

## 14. Estructura del repo

```
aurum-encuestas/
├── backend/
│   ├── aurum_encuestas/
│   │   ├── __init__.py
│   │   ├── api.py                    # FastAPI app + endpoints
│   │   ├── xlsx_parser.py            # auto-detect heurística
│   │   ├── pptx_template.py          # valida + extrae shell/separator/free_area/placeholders
│   │   ├── layout_engine.py          # bank match + heurística A + AI suggest
│   │   ├── training_extractor.py     # extrae layouts/styles de training PPTs
│   │   ├── pptx_generator.py         # arma pptx final desde state
│   │   ├── llm_client.py             # wrapper Anthropic con prompt cache
│   │   ├── render_service.py         # libreoffice wrapper
│   │   ├── project_store.py          # .aurum.json I/O + paths relativos
│   │   └── config.py                 # ~/.aurum/ I/O + recientes
│   ├── tests/
│   │   ├── fixtures/
│   │   │   ├── valid.xlsx
│   │   │   ├── invalid.xlsx
│   │   │   ├── valid_template.pptx
│   │   │   └── training_sample.pptx
│   │   └── test_*.py
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── store/
│   │   │   ├── project.ts            # zustand + zundo
│   │   │   └── slices/
│   │   ├── pages/
│   │   │   ├── Editor/
│   │   │   │   ├── EditorPage.tsx
│   │   │   │   ├── SlideRail.tsx
│   │   │   │   ├── Preview.tsx
│   │   │   │   └── ConfigPanel.tsx
│   │   │   ├── Training/
│   │   │   │   └── TrainingPage.tsx
│   │   │   └── Wizard/
│   │   │       └── XlsxVerifyWizard.tsx
│   │   ├── components/
│   │   │   ├── Topbar.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── ...
│   │   ├── api/                      # fetch wrappers tipados
│   │   ├── types/                    # ProjectState, Slide, Chart, Analysis
│   │   └── hooks/
│   ├── tests/
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docs/
│   ├── superpowers/specs/
│   │   └── 2026-06-16-aurum-encuestas-design.md   # este archivo
│   ├── xlsx-schema.md                # convención esperada xlsx + heurísticas
│   ├── template-spec.md              # cómo armar un template válido
│   └── api.md                        # endpoints backend
├── Makefile                          # make dev, make test, make build
├── README.md
└── .gitignore
```

---

## 15. Decisiones de brainstorming (apéndice de trazabilidad)

| Q | Decisión |
|---|---|
| Q1 | Stack: React + FastAPI local |
| Q2 | Preview: PPT → PNG vía libreoffice (B) |
| Q3 | Template: usuario sube uno, swappable |
| Q4 | Parser xlsx: auto-detect heurística (B) |
| Q5 | Composición slide: C — auto-layout con base en entrenamiento |
| Q6 | Aprende: layouts + chart style + text style; análisis vía LLM (no template) |
| Q7 | Análisis: LLM siempre (B) |
| Q8 | Modelo: Haiku 4.5; API key en `.env` |
| Q9 | Scope análisis: slide + pregunta + chart (3 scopes) |
| Q10 | Fallback layout: heurística determinística A |
| Q11 | UI: 3 columnas + topbar + footer, layout aprobado vía mockup |
| Q12 | Undo/redo: snapshot pattern, `Cmd+Z` / `Cmd+Shift+Z` |
| Q13 | Persistencia: `.aurum.json` por proyecto + history persistida + recientes 5 |
| Q14 | Wizard verificación xlsx siempre, 1-click default |
| Q15 | Sin intro slides; app NO genera ningún slide fijo (todas generadas) |
| Q16 | 9 tipos chart; auto-sugiere tipo; cambio individual post-creación; multi-serie toggle |
| Q17 | Export: modal con nombre + carpeta `~/Downloads/` + abrir ON + todo el deck |
| Q18 | Small decisions: empty new slide, single-user, error UX, TDD, estilo LLM, sin telemetría, ES neutral |
| Q19 | Template = shell vacío + placeholders `@Titulo` y `@Notas` (auto-computado); 1 shell universal; convención `@` |
| Q20 | App genérica `AurumEncuestas`; template = 2 slides (shell + separador); separador define título sección; auto-renumera; sin override per-shell |
| Adicional | Sub-recos training globales / font lista curada / tab persistente: confirmados |

---

## 16. Próximos pasos

1. **Plan de implementación** vía `superpowers:writing-plans` skill
2. Setup repo (scaffold backend + frontend)
3. TDD por feature siguiendo el plan
