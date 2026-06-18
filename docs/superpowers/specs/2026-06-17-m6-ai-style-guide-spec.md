# M6 — AI Style Guide & Pattern-Based Generator — Design Spec

**Fecha:** 2026-06-17
**Estado:** Spec aprobado tras 19 rondas de grilling
**Branch:** `feat/m6-ai-style-guide` (cut desde `feat/m5-polish`)
**Predecesor:** v0.1.0 (M1-M5)

---

## 1. Problem statement

v0.1.0 genera PPT con charts standalone heurísticos. Lejos del "estilo Aurum" del corpus de entrenamiento. Color extraction XML era frágil, mezclaba estilos de PPTs distintos, no entendía intent (sysClr+lumMod renderizado como greys salía como rojo en su lugar). Layout matching geométrico raramente matcheaba. Imposible replicar Aurora ejemplo target (usa Excel OLE embebido).

**Goal v0.2.0:** App genérica donde con cualquier xlsx + template, el output PPT sea **sumamente parecido en diseño/estructura** al training set Aurum. Training = referencia interpretada por AI (Sonnet 4.6 vision), no clone de bytes. Colores 100% control usuario.

---

## 2. Core architectural shift

### v0.1.0 (obsoleto)
- Heurística XML extrae colors/positions de training PPTs
- `layout_matcher` busca match geométrico por signature → fallback heurística grid
- `_apply_training_style` aplica colors via python-pptx API
- 1 corpus training plano, conflictos entre PPTs con estilos distintos

### v0.2.0 (este spec)
- **AI analyzer** (Sonnet 4.6 vision) sintetiza style guide JSON estructurado del corpus
- **Pattern classifier** matchea slide config contra patterns con triggers ricos (operators $and/$or/$not/comparators)
- **Pattern renderer** interpreta `implementation.elements[]` schema declarativamente
- **Element renderers** (chart/table/text/shape/image) ejecutan render por kind
- **Color resolver** = symbolic roles → hex via cascade (chart.colors → project.palette → style_guide.suggested_palette → built-in)
- **Único corpus global** ("Aurum way") — no sets, no per-project override

---

## 3. Goal del training

Training corpus = "como hemos estado haciendo los proyectos en Aurum". AI debe **sintetizar best-of cross-corpus**: identifica patterns recurrentes, picks best implementation example por pattern, devuelve style guide unificado.

Cada nuevo proyecto hereda **automáticamente** el style guide global. Sin selector por proyecto. Si corpus vacío → fallback built-in generic style guide (Calibri + 5 patterns básicos).

---

## 4. Stack tecnológico

**Sin cambios al stack base** (React + FastAPI + libreoffice + python-pptx).

**Nuevas dependencias:**
- Frontend: `react-json-view-lite` (style guide tree viewer)
- Backend: ninguna nueva — Anthropic SDK ya integrada

**Modelo LLM:**
- **Análisis style guide**: Claude Sonnet 4.6 vision (`claude-sonnet-4-6`)
- **Generación análisis**: Claude Haiku 4.5 (sin cambios)

---

## 5. Filesystem layout

```
~/.aurum/
├── config.json                       # recents, prefs (sin cambios)
├── training/
│   ├── corpus/                       # flat list de PPTs, no sets
│   │   ├── Aurora ejemplo.pptx
│   │   ├── Precancelaciones-MAF.pptx
│   │   └── ...
│   ├── style_guide.json              # AI-generated global, override manual permitido
│   ├── .last_ai_raw.json             # raw AI response para debug
│   ├── ai_analysis_logs/             # JSON logs por análisis (prompt, response, validation, cost)
│   │   └── {timestamp}.json
│   └── render_cache/                 # PNG cache per pptx_hash + slide_idx (max 500MB LRU)
│       └── {sha256_16chars}_{slide_idx}.png
└── uploads/                          # xlsx/template upload persists (sin cambios)
```

---

## 6. Style Guide schema (pydantic)

```jsonc
{
  "version": 1,
  "is_builtin": false,                              // true si fallback
  "generated_at": "2026-06-17T20:00:00Z",
  "ai_prompt_version": "v1.0",
  "source_pptxs": ["Aurora.pptx", "Precanc.pptx"],
  "manual_edits": {                                 // tracking patterns editados manualmente
    "pattern_id": "edited_at_timestamp"
  },

  "global": {
    "typography": {
      "font_family": "Arial",
      "title_size": 16,
      "subtitle_size": 12,
      "label_size": 9,
      "body_size": 10
    },
    "text_patterns": {
      "title": "{question_code}. {question_text}",
      "notes": "{tipo_respuesta}. Número de observaciones: {sample_size}.",
      "analysis_style": "El {X}% de los encuestados {finding}. {context}.",
      "tone": "formal técnico español neutral"
    },
    "suggested_palette": ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9"],
    "vibe": "Minimalista profesional. Greys dominan. Yellow accent puntual. Layouts limpios."
  },

  "available_chart_types": ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED", "TABLE_WITH_MINIBARS"],

  "patterns": [
    {
      "id": "binary_general_demographics",
      "priority": 0,
      "trigger": {
        "$and": [
          {"field": "n_charts_in_slide", "$eq": 1},
          {"field": "question_type", "$eq": "binary"},
          {"field": "n_breakdowns", "$gte": 2}
        ]
      },
      "extends": null,
      "best_example": "Aurora ejemplo.pptx#slide17",
      "why_picked": "Pie clean izq + tablas con mini-bars der. Compacto y comparable.",
      "implementation": {
        "elements": [
          {
            "kind": "chart",
            "id": "main_pie",
            "position": {"x_rel": 0.05, "y_rel": 0.25, "w_rel": 0.3, "h_rel": 0.55},
            "chart_type": "PIE",
            "data_source": {"chart_ref_index": 0, "value_field": "pct"},
            "labels": {
              "show_category_name": true,
              "show_percentage": true,
              "position": "outside_end",
              "format": "0.0%"
            },
            "legend": "none"
          },
          {
            "kind": "table",
            "id": "demographics_table",
            "position": {"x_rel": 0.4, "y_rel": 0.25, "w_rel": 0.55, "h_rel": 0.55},
            "structure": "segmented_breakdowns",
            "data_source": {
              "chart_ref_index": 0,
              "breakdown_groups": "all_except_general"
            },
            "cells": {
              "group_header": {"style": {"fill": "primary", "text_color": "background", "font_size": 10, "bold": true, "align_h": "center"}, "merge_per_breakdown": true},
              "category_header": {"style": {"fill": "secondary", "size": 9, "bold": true}},
              "counts_row": {"style": {"fill": "background", "size": 9, "align_h": "center"}, "label_first_col": "Observaciones"},
              "option_row": {
                "style": {"fill": "background", "size": 9},
                "label_col_width_rel": 0.10,
                "value_format": "percentage",
                "value_decimals": 1,
                "minibar": {
                  "enabled": true,
                  "color_role": "primary",
                  "height_rel_to_cell": 0.4,
                  "show_percent_text": true,
                  "percent_text_position": "left_of_bar"
                }
              }
            }
          }
        ]
      }
    }
  ]
}
```

### Trigger operators soportados

| Operator | Semantics |
|---|---|
| `$eq` | equal |
| `$neq` | not equal |
| `$gt`, `$gte`, `$lt`, `$lte` | numeric comparison |
| `$in` | value in array |
| `$nin` | value not in array |
| `$and` | array of conditions, all must match |
| `$or` | array of conditions, any must match |
| `$not` | single condition, must NOT match |

Operators componibles: `{"$and": [{"$or": [...]}, {"$not": {...}}, {"field": "x", "$eq": 5}]}`.

### Trigger fields disponibles

- `n_charts_in_slide` (int)
- `all_charts_share_question` (bool)
- `question_type` (`"binary" | "multi_small" | "multi_large" | "ranking" | "open"`)
- `n_options_per_question` (int)
- `breakdowns_used` (list[str])
- `n_breakdowns` (int)
- `n_analyses` (int)
- `n_chart_analyses` (int)
- `n_question_analyses` (int)
- `has_slide_analysis` (bool)

### Question type detection (heurística)

- 2 opciones → `binary`
- 3-5 opciones → `multi_small`
- 6+ opciones → `multi_large`
- Question text contiene "ranking", "ordenar", "preferir" → `ranking`
- Sin opciones detectadas → `open`

### Pattern inheritance

`pattern.extends: "parent_id"` → renderer merge-deep parent.implementation con child overrides. Permite reuso DRY: define `base_pie` con position+labels+legend, hijos `binary_pie extends base_pie` solo overridean trigger.

### Element kinds

#### `chart`
```jsonc
{
  "kind": "chart",
  "id": "string",
  "position": {"x_rel": float, "y_rel": float, "w_rel": float, "h_rel": float},
  "chart_type": "PIE" | "DONUT" | ...,
  "data_source": {
    "chart_ref_index": int,                          // indexes slide.charts[]
    "value_field": "pct" | "count"
  },
  "labels": {
    "show_category_name": bool,
    "show_value": bool,
    "show_percentage": bool,
    "position": "inside" | "outside_end" | "center" | "best_fit",
    "format": "string format spec",                  // ej "0.0%", "0,000"
    "font_size": int (opt)
  },
  "legend": "none" | "right" | "bottom" | "top" | "left",
  "title": "string | null",
  "sort": "none" | "desc_by_value" | "asc_by_value" | "category_order"
}
```

#### `table`
```jsonc
{
  "kind": "table",
  "id": "string",
  "position": {...},
  "structure": "segmented_breakdowns" | "comparison_grid" | "simple_data",
  "data_source": {
    "chart_ref_index": int,
    "breakdown_groups": list[str] | "all" | "all_except_general"
  },
  "layout": {
    "col_widths": "auto" | list[float] | "equal",
    "header_height_rel": float,
    "counts_row_height_rel": float
  },
  "cells": {
    "group_header": {"style": {...}, "merge_per_breakdown": bool},
    "category_header": {"style": {...}},
    "counts_row": {"style": {...}, "label_first_col": "string"},
    "option_row": {
      "style": {...},
      "label_col_width_rel": float,
      "label_style": {...},
      "value_format": "percentage" | "count" | "both",
      "value_decimals": int,
      "minibar": {
        "enabled": bool,
        "color_role": "primary" | "secondary" | ...,
        "track_color_role": "string",
        "height_rel_to_cell": float,
        "align": "left" | "center" | "right",
        "show_percent_text": bool,
        "percent_text_position": "left_of_bar" | "inside_bar" | "right_of_bar"
      }
    }
  }
}
```

#### `text`
```jsonc
{
  "kind": "text",
  "id": "string",
  "position": {...},
  "content_source": {
    "type": "analysis" | "static" | "computed",
    "scope": "slide" | "question" | "chart",          // if analysis
    "ref_index": int,                                  // if analysis: which chart's analysis
    "text": "static text"                              // if static
  },
  "style": {
    "fill": "color_role",
    "text_color": "color_role",
    "font_size": int,
    "border_left": {"color": "color_role", "width_pt": float},
    "padding": int,
    "align_h": "left" | "center" | "right",
    "bold": bool
  }
}
```

#### `shape`
```jsonc
{
  "kind": "shape",
  "id": "string",
  "position": {...},
  "shape_type": "line" | "rectangle",
  "style": {
    "color": "color_role",
    "fill": "color_role | null",
    "width_pt": float
  }
}
```

#### `image`
```jsonc
{
  "kind": "image",
  "id": "string",
  "position": {...},
  "source_ref": "template_shape_id"                   // image lives in template, referenced
}
```

### Position model

- `x_rel`, `y_rel`: top-left corner as fraction of `free_area` (0-1)
- `w_rel`, `h_rel`: width/height as fraction of `free_area`
- Renderer resolves: `x_emu = free_area.x + x_rel * free_area.cx` etc

### Anchored positioning (opcional)

```jsonc
"position": {
  "anchor": "main_pie",                              // element id
  "relative": "right_of" | "below" | "above" | "left_of",
  "offset_rel": 0.02,
  "w_rel": 0.3, "h_rel": 0.5
}
```

Renderer resolves anchor positions in topological order.

---

## 7. Generator pipeline

```
slide_def (separator | shell)
  │
  ├─ separator → clone template separator slide, substitute @Titulo
  │
  └─ shell:
     │
     ▼ build slide_config = {
       n_charts, charts: [...], analyses: [...], 
       parsed_db ref, free_area
     }
     │
     ▼ classify_pattern(slide_config, style_guide.patterns[])
     │  iterates priority asc, first $eq/etc match wins
     │  if no match → fallback "generic_grid" pattern from built-in
     │
     ▼ pattern matched → render_pattern(pattern, slide_config, data)
     │  for each element in pattern.implementation.elements:
     │     resolve position (rel→abs via free_area)
     │     resolve data_source (chart_ref_index → slide.charts[i])
     │     resolve colors (symbolic → hex via color_resolver)
     │     dispatch to element_renderers[kind]
     │
     ▼ element_renderer renders shape on slide via python-pptx
     │
     ▼ shell slide done → continue to next slide_def
```

---

## 8. AI Style Guide Analyzer

### Pipeline

```
trigger: user clicks "Re-analizar con AI" in Training tab
  ↓
1. List corpus/*.pptx
  ↓
2. For each PPT: extract slides with ≥1 chart shape
  Sample max 15 if more (uniform across slide indices)
  Total slides: min(N_with_charts, 15) per PPT, capped at 30 across corpus
  ↓
3. For each selected slide:
   - Check render_cache for {pptx_hash}_{slide_idx}.png
   - If miss → libreoffice headless render
   - Build XML metadata summary (shape counts, types, key text)
  ↓
4. Build user message:
   Header text + per-slide PNG + per-slide metadata
  ↓
5. Call Claude Sonnet 4.6 vision:
   system = SYSTEM_PROMPT_V1 (cached ephemeral 1h)
   user = above message
   max_tokens = 8000
   temperature = 0.2
  ↓
6. Parse response as JSON
  ├─ JSON inválido → retry 1× with error feedback
  └─ Falla 2× → save raw to .last_ai_raw.json + fallback built-in
  ↓
7. Pydantic schema validate
  ├─ Schema invalid → retry 1× with feedback
  └─ Falla 2× → fallback built-in
  ↓
8. Semantic validation + repair:
   - Drop patterns with broken triggers/positions/refs
   - Clamp coords to [0,1]
   - Map unsupported chart_types to closest available
   - Log all repairs
  ↓
9. Merge with existing manual_edits (preserve user overrides)
  ↓
10. Save ~/.aurum/training/style_guide.json
  ↓
11. Save log to ai_analysis_logs/{timestamp}.json
  ↓
12. Return summary to UI: N patterns valid, M removed, M2 manual preserved
```

### System prompt (v1.0)

```
Sos un design system analyst especializado en presentaciones de encuestas.

Tu trabajo: analizar las slides de entrenamiento provistas y derivar un style guide ESTRUCTURADO en JSON que permita generar slides nuevas con datos arbitrarios manteniendo el estilo, jerarquía visual y patrones de presentación de las training slides.

Reglas:
- IGNORÁ colores específicos. El usuario elegirá colores aparte. NO incluyas palette/colors hex en patterns.
- IDENTIFICÁ patterns de presentación: cómo se presenta cada tipo de pregunta (binaria, múltiple, ranking), cómo se muestran breakdowns demográficos (tablas con mini-bars vs charts agrupados), dónde van los análisis.
- IDENTIFICÁ tipos de gráfico/elemento usados (PIE, BAR_HORIZONTAL, TABLE_WITH_MINIBARS, etc). Lista en available_chart_types SOLO los que VES.
- DETECTÁ "best examples" cross-corpus: si pattern X tiene 3 ejemplos en distintas slides, elegí EL MEJOR (más limpio, jerarquía más clara, más legible) y explicá por qué en why_picked.
- Posiciones: usá fracciones relativas (0-1) del área libre, no EMU absolutos.
- 8-15 patterns total. Más específicos primero (priority).

[SCHEMA + few-shot example completo]

Devolvé ÚNICAMENTE el JSON válido. Sin markdown, sin comentarios fuera del JSON.
```

### Caching

- **System prompt cached** (ephemeral 1h TTL) — ~85% input tokens hit cache en re-analyze
- **Render cache** (`render_cache/{pptx_hash}_{slide_idx}.png`) — skip libreoffice si hit
- **Cache invalidate**: pptx hash change → re-render

### Cost estimate

- Sonnet 4.6 vision: ~$3/M input, $15/M output
- Por re-analyze (15 slides): ~50K input tokens (mostly vision images) + ~5K output JSON
- Cached input: ~85% hit → effective ~7.5K fresh input
- Cost: ~$0.20-0.30 per re-analyze (one-shot al modificar corpus)

---

## 9. Color picker UX

### ColorPicker component spec

**Inline en AddChartModal:**
```
Colores:
  [⬛ #7F7F7F ▾] (principal)
  ▾ Avanzados (N slots individuales)
```

Click `[⬛ ▾]` → popup picker:
```
┌──────────────────────────────────┐
│ Sugeridas del training:          │
│  ⬛ ⬛ ⬛ ⬛ ⬛                  │
│                                  │
│ Defaults:                         │
│  ⬛ ⬛ ⬛ ⬛ ⬛ ⬛                │
│  ⬜ ⬛ ⬜ ⬛                      │
│                                  │
│ Recientes:                        │
│  ⬛ ⬛ ⬛ ⬛                      │
│                                  │
│ Hex:    [#________]               │
│                                  │
│ [↺ Auto]   [Cancelar] [OK]       │
└──────────────────────────────────┘
```

### Color cascade (resolver)

`Chart.colors[i]` → `ProjectState.palette[role]` → `style_guide.global.suggested_palette[i]` → built-in default greys

### Auto-derive (N-1 from primary)

If user picks color #1 only, N-1 derived via `lumMod`:
- N=2: [primary, primary lumMod 0.5 → lighter grey variation]
- N=3: [primary, primary lumMod 0.3, primary lumMod 0.6]
- N=K: K colors evenly spaced lumMod

### Auto button

Click "Auto" → `Chart.colors = []` → resolver cascades to project palette / style_guide / built-in default.

### "Avanzados" expand

Reveals N independent color slots, one per option/series. Each with its own popup.

### Color storage

```jsonc
ProjectState.palette: {                            // optional project-level defaults
  "primary": "#7F7F7F",
  "secondary": "#BFBFBF",
  "accent": "#FFC000",
  ...
}

Chart.colors: ["#7F7F7F", "#BFBFBF"]               // per slice/series; if [] → cascade
```

### Recientes

`~/.aurum/config.json` mantiene `recent_colors: list[str]` (last 8). ColorPicker muestra row "Recientes".

---

## 10. UI changes

### TrainingPage (rewrite)

```
+---------------------------------------------+
| Topbar                                       |
+---------------------------------------------+
|  Corpus de entrenamiento                    |
|  Style guide AI · 12 patterns · last AI ✓   |
|                                              |
|  PPTs en corpus (5)                          |
|  ┌─────────────────────────────────────────┐ |
|  │ ▸ Aurora.pptx (15 charts)        🗑    │ |
|  │ ▸ Precanc.pptx (20 charts)       🗑    │ |
|  │ [+ Agregar PPT al corpus]              │ |
|  └─────────────────────────────────────────┘ |
|                                              |
|  Style guide                                  |
|  [Ver style guide ▾] [Re-analizar con AI]   |
|                                              |
|  Available chart types: PIE, BAR_H,           |
|  TABLE_WITH_MINIBARS, COLUMN_STACKED        |
+---------------------------------------------+
```

### WelcomePage

Sin selector training set (usa global). Banner top si corpus vacío:
```
⚡ Cargá training PPTs para que las generaciones reflejen tu estilo casa → [Configurar]
```

### AddChartModal

- Chart type dropdown poblado dinámico desde `style_guide.available_chart_types`
- ColorPicker inline (Q15)

### ConfigPanel

- Chart row muestra indicator: "Layout: pattern `binary_general_demographics` ✓ (matched)" / "fallback heurístico"
- ColorPicker accesible vía edit chart

---

## 11. Validation, error handling, repair

### AI output validation pipeline

| Stage | Failure | Action |
|---|---|---|
| JSON parse | Malformed | Retry 1× with error feedback. If fails 2× → save raw + fallback built-in + UI warning ⚠ |
| Pydantic schema | Missing/wrong field | Retry 1× with feedback. Fails 2× → fallback built-in |
| Semantic checks | extends ref broken | Drop inheritance, log warning |
|  | position out [0,1] | Clamp, log warning |
|  | chart_type not in available | Map to closest, log |
|  | color_role unrecognized | Default to "primary", log |
|  | trigger operators invalid | Skip pattern, log |
|  | duplicate pattern.id | Keep first, drop rest, log |

### Manual edit preservation

- `style_guide.json` includes `manual_edits: {pattern_id: timestamp}` map
- On re-analyze, modal asks user: "Re-analizar va a sobreescribir N patterns editados manualmente. [Mantener manuales] [Sobreescribir todo] [Cancelar]"
- Default = mantener

### Logs

`~/.aurum/training/ai_analysis_logs/{timestamp}.json`:
```jsonc
{
  "timestamp": "...",
  "duration_seconds": 58.3,
  "corpus_pptxs": ["Aurora.pptx", "Precanc.pptx"],
  "slides_analyzed": 22,
  "prompt_version": "v1.0",
  "input_tokens": 48230,
  "output_tokens": 4521,
  "cached_input_tokens": 41123,
  "estimated_cost_usd": 0.22,
  "validation_errors": [
    {"pattern_id": "X", "error": "...", "action": "dropped"}
  ],
  "patterns_valid": 12,
  "patterns_dropped": 2,
  "patterns_repaired": 1
}
```

---

## 12. Performance + caching

| Cache | Key | Storage | Eviction |
|---|---|---|---|
| Render cache | `{pptx_hash}_{slide_idx}.png` | disk `~/.aurum/training/render_cache/` | LRU at 500MB |
| Style guide in-memory | `style_guide.json` modtime | backend module-level var | reload on modtime change |
| Preview render | `{project_id}_{slide_id}_{slide_state_hash}.png` | backend dict | LRU 50 entries |
| Pattern classifier | `(slide_config_hash, style_guide_hash)` | backend dict | LRU 200 entries |
| Built-in style guide | const | Python module load | never evicted |
| Anthropic prompt cache | system prompt hash | API-side | TTL 1h |

Debug mode (`AURUM_DEBUG=1`) logs cache hit rates.

---

## 13. Backend module map (post-refactor)

### Delete (obsolete)

- `aurum_encuestas/layout_matcher.py` ❌
- `aurum_encuestas/layout_engine.py` ❌ (replaced by fallback in pattern_renderer)
- `aurum_encuestas/training_extractor.py` ❌ (replaced by AI analyzer)
- `aurum_encuestas/pptx_generator.py::_apply_training_style` lógica colors ❌

### New modules

- `aurum_encuestas/style_guide.py` — pydantic schemas + built-in const + load_active() helper
- `aurum_encuestas/style_guide_analyzer.py` — Claude vision wrapper + validation + repair
- `aurum_encuestas/pattern_classifier.py` — trigger evaluation + question_type detection + field extraction
- `aurum_encuestas/pattern_renderer.py` — orchestrator, dispatches to element_renderers
- `aurum_encuestas/color_resolver.py` — symbolic → hex cascade + lumMod auto-derive
- `aurum_encuestas/training_sets.py` — corpus CRUD (rename from training_extractor concept) — actually flat corpus, not sets
- `aurum_encuestas/element_renderers/__init__.py`
- `aurum_encuestas/element_renderers/chart_renderer.py`
- `aurum_encuestas/element_renderers/table_renderer.py`
- `aurum_encuestas/element_renderers/text_renderer.py`
- `aurum_encuestas/element_renderers/shape_renderer.py`
- `aurum_encuestas/element_renderers/image_renderer.py`

### Modify

- `aurum_encuestas/pptx_generator.py` — refactor to use pattern_classifier + pattern_renderer
- `aurum_encuestas/models.py` — `Chart.colors: list[str]`, `ProjectState.palette: dict | None`, remove `style_set` (sets concept dropped)
- `aurum_encuestas/api.py` — new endpoints (next section)
- `aurum_encuestas/llm_client.py` — add `analyze_training_corpus()` method

### Keep unchanged

- `aurum_encuestas/xlsx_parser.py`
- `aurum_encuestas/data_extractor.py`
- `aurum_encuestas/pptx_template.py`
- `aurum_encuestas/project_store.py`
- `aurum_encuestas/render_service.py`
- `aurum_encuestas/config.py`

---

## 14. Backend API (M6 additions)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/training/corpus/add` | multipart `file` | `{filename, slides_with_charts}` |
| POST | `/api/training/corpus/delete` | `{filename}` | `{deleted: bool}` |
| GET | `/api/training/corpus/list` | — | `{pptxs: [{filename, slides_with_charts, added_at}]}` |
| POST | `/api/training/analyze-with-ai` | — | `{job_id}` (async) |
| GET | `/api/training/analysis-status/{job_id}` | — | `{progress: 0-100, status: "running"|"done"|"error", message}` |
| GET | `/api/training/style-guide` | — | `StyleGuide JSON` |
| PUT | `/api/training/style-guide/pattern/{pattern_id}` | `Pattern JSON` | `{ok: true}` |
| POST | `/api/training/clear-cache` | `{cache_type: "render"|"classifier"|"all"}` | `{cleared}` |

Remove: `/api/training/list`, `/api/training/add`, `/api/training/delete`, `/api/training/reprocess`, `/api/training/bank` (M4-M5 obsolete endpoints).

---

## 15. Frontend module map

### Delete

- `frontend/src/pages/Training/TrainingPage.tsx` (rewrite)
- (Maintain shell, delete internals)

### New components

- `frontend/src/pages/Training/TrainingPage.tsx` (rewrite — flat corpus + style guide section)
- `frontend/src/pages/Training/CorpusList.tsx`
- `frontend/src/pages/Training/StyleGuideViewer.tsx`
- `frontend/src/pages/Training/AnalysisProgressModal.tsx`
- `frontend/src/components/ColorPicker/ColorPicker.tsx`
- `frontend/src/components/ColorPicker/ColorSwatch.tsx`
- `frontend/src/components/ColorPicker/HexInput.tsx`
- `frontend/src/components/ColorPicker/PaletteRow.tsx`
- `frontend/src/store/styleGuide.ts` (zustand slice for active style guide)
- `frontend/src/api/training.ts` (rewrite endpoints)

### Modify

- `frontend/src/pages/Welcome.tsx` — remove training set selector, add empty-corpus banner
- `frontend/src/pages/Editor/modals/AddChartModal.tsx` — dynamic chart types from style guide + ColorPicker integration
- `frontend/src/pages/Editor/ConfigPanel.tsx` — pattern matched indicator + color edit
- `frontend/src/store/project.ts` — add `palette` field, remove `style_set`
- `frontend/src/types/index.ts` — add Chart.colors, ProjectState.palette, StyleGuide types

---

## 16. Migration / cleanup

### Clean break strategy

- Delete `~/.aurum/training/layout_bank.json` (legacy)
- Move existing `~/.aurum/training/*.pptx` to `~/.aurum/training/corpus/` (preserve, just relocate)
- Existing project `.aurum.json` files: strip `style_set` field on load (backward compat)
- Reset `Chart.colors = []` for existing charts (user re-picks or auto-derives)

### Migration script (one-shot on first M6 backend startup)

```python
def _m6_migration():
    aurum = get_aurum_dir()
    legacy_bank = aurum / "training" / "layout_bank.json"
    if legacy_bank.exists():
        legacy_bank.rename(aurum / "training" / "layout_bank.json.legacy")
    
    legacy_pptxs = list((aurum / "training").glob("*.pptx"))
    corpus_dir = aurum / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    for p in legacy_pptxs:
        p.rename(corpus_dir / p.name)
```

Runs idempotent on startup. Logs actions.

---

## 17. Testing strategy

- Unit tests pytest per module (75% coverage target backend)
- Integration tests end-to-end pipeline with fixtures
- Schema fuzz tests with hypothesis
- AI response golden file fixtures
- Frontend vitest + RTL (70% target)
- E2E Playwright happy path smoke

Detail: see Q18 in grilling log + plans.

---

## 18. Out of scope M6 (deferred v2)

- Per-slide style guide override (different patterns on different slides in same deck)
- Multiple training "sets" (current: single global corpus)
- Color contrast warnings
- Gradient/pattern fills
- Pattern editor with visual layout designer
- CI pipeline
- OLE Excel embedding (impossible via python-pptx)
- Public API for external tools

---

## 19. Implementation plan structure

12 sub-milestones, each its own plan file in `docs/superpowers/plans/`:

| Sub-milestone | Plan file | Scope |
|---|---|---|
| M6.1 | `2026-06-17-m6-1-schema-models.md` | Pydantic schemas + built-in const + migration |
| M6.2 | `2026-06-17-m6-2-backend-cleanup.md` | Delete obsolete + stubs new |
| M6.3 | `2026-06-17-m6-3-pattern-classifier.md` | Trigger operators + field extraction |
| M6.4 | `2026-06-17-m6-4-color-resolver.md` | Cascade + lumMod derive |
| M6.5 | `2026-06-17-m6-5-element-renderers.md` | chart/text/shape/image/table renderers |
| M6.6 | `2026-06-17-m6-6-pattern-renderer.md` | Orchestrator + new pptx_generator |
| M6.7 | `2026-06-17-m6-7-ai-analyzer.md` | Claude vision + caching + validation |
| M6.8 | `2026-06-17-m6-8-api-endpoints.md` | New training API |
| M6.9 | `2026-06-17-m6-9-training-tab.md` | TrainingPage rewrite |
| M6.10 | `2026-06-17-m6-10-color-picker.md` | ColorPicker + integration |
| M6.11 | `2026-06-17-m6-11-welcome-modal.md` | Welcome + AddChartModal updates |
| M6.12 | `2026-06-17-m6-12-integration-e2e.md` | E2E smoke + polish + v0.2.0 tag |

Total ~60 tasks. Execution: subagent-driven-development (same pattern as M1-M5). Sub-milestones tagged individually (`m6.1`...`m6.12`). Final tag `v0.2.0`.

---

## 20. Acceptance criteria (Definition of Done M6)

- [ ] Corpus de training cargado (≥2 PPTs) → "Re-analizar con AI" produce `style_guide.json` válido pydantic con ≥5 patterns
- [ ] Generar nuevo proyecto sin training → output usa built-in fallback decente (charts simples, no errores)
- [ ] Con training cargado → output charts/tablas reflejan patterns aprendidos (verified manualmente comparando con Aurora ejemplo)
- [ ] ColorPicker permite picks per-slice/series, auto-derive funciona, Recientes persiste
- [ ] Pattern matched indicator visible en ConfigPanel
- [ ] Tab Training muestra corpus + style guide + permite manual edit
- [ ] AI analysis logs guardados con cost tracking
- [ ] Render cache reduce re-analyze time
- [ ] Style guide manual edit preserva across re-analyze
- [ ] All tests passing (~150 backend + ~60 frontend)
- [ ] Tag `v0.2.0` on `main`
- [ ] README updated with v0.2 features

---

## 21. Decisiones de grilling (apéndice trazabilidad)

| Q | Decisión |
|---|---|
| Q1 | Sonnet 4.6 vision + max 15 slides con charts |
| Q2 | Schema B medio (palette + typography + chart_prefs + 8-15 patterns + text_patterns) |
| Q3-Q3.5 | Corpus único global (no sets) — "Aurum way" agregado |
| Q4 | ColorPicker C (creación + edit) + N colors granular + cascade + grid+hex+Auto |
| Q5 | Removed (sets dropped) |
| Q6 | A — AI explicit prompt para best-of cross-corpus, 8-15 patterns, all PPTs (irrelevant flag), simple versioning, pydantic validate |
| Q7 | A — style guide PRIMARIA, sub-decisiones all yes |
| Q8 | B — trigger schema JSON predicate + operators $and/$or/$not/comparators, inheritance, first-match-wins |
| Q9 | A — implementation generic renderer schema-driven, symbolic colors, anchored positions, silent skip, granular patterns |
| Q10 | Tab Training rewritten con sets initially, simplified after Q3.5 to flat corpus |
| Q11 | System prompt cached + vision + ≤15 slides + metadata + pydantic strict + permissive extras + few-shot + temperature 0.2 |
| Q12 | Clean break + unassigned move + new branch + plan formal + keep old tags |
| Q13 | Table segmented_breakdowns full schema, shape overlay minibars, sub-decisions all yes |
| Q14 | AI validation pipeline + repair + manual edit preserve + retry 1× + structured logs + version bump UI prompt |
| Q15 | Picker grid+hex+Auto, neutral defaults, Auto from style_guide suggested_palette, project palette inheritance, recents global config |
| Q16 | Built-in 5 patterns (binary_general, binary_with_demographics, multi_small, multi_large, comparison_two), Calibri default, subset chart types, banner indicator |
| Q17 | Render cache + style guide in-memory + preview LRU + classifier dict + API prompt cache + sub-decisions all yes |
| Q18 | Unit + integration + fuzz + golden files + frontend vitest + E2E Playwright + cost tests, 75/70% coverage, clean break tests |
| Q19 | 12 sub-milestones, tag per sub, mostly sequential, single spec + 12 planes, subagent-driven execution |
