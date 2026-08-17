# Textos de pregunta insertables (no automáticos)

Fecha: 2026-08-17

## Objetivo

Reemplazar el subtítulo de pregunta **automático** por textos de pregunta que el
usuario **inserta manualmente** por slide: puede agregar uno o varios, editarlos y
removerlos. El posicionamiento en el PPTX lo maneja el layout AI existente (Claude),
igual que los análisis.

## Contexto actual (verificado)

- En `pptx_generator.py:133-146`, cuando una slide tiene charts de **una sola**
  pregunta, se auto-rellena el placeholder `@Subtitulo` del template con
  `"{código}. {texto}"` derivado del `parsed_db`. Con 2+ preguntas o ninguna, queda
  vacío. No hay control del usuario.
- Los **análisis** (`Slide.analyses: list[Analysis]`) son el patrón a espejar: se
  renderizan como textboxes (`_add_analyses_textboxes`, pptx_generator.py:301),
  posicionados por `SlideLayout.positions[analysis_id]` (un `LayoutBox`) cuando el AI
  los ubicó, o en una banda fallback abajo del `free_area`.
- El layout AI (`suggest_slide_layout` en api.py) arma `payload_shapes` con
  `kind: "chart" | "analysis"` (api.py:561-601) y devuelve posiciones que se parsean
  por prefijo de id (`chart_`, `analysis_`, api.py ~640-657) hacia
  `SlideLayout.positions`.
- El Preview del editor NO renderiza el contenido de la slide (charts/análisis/
  subtítulos); el texto de pregunta solo se ve en el PPTX exportado. → sin cambios en
  Preview.

## Decisiones (acordadas)

1. **No automático.** Se elimina el auto-relleno de `@Subtitulo`; el placeholder queda
   vacío (`""`). Proyectos existentes dejan de mostrar el subtítulo hasta que el
   usuario inserte textos.
2. **Insertar manualmente**, 1 o varios por slide, **editables** y removibles.
3. **Fuente al insertar:** auto-derivado de las preguntas de los charts de la slide
   (`"{código}. {texto}"`), ya editable (snapshot; editar no afecta el parsed_db).
4. **Posicionamiento:** por el layout AI existente (prefijo `subtitle_`), con banda
   fallback cuando el AI no lo ubicó.

## Modelo de datos

Backend (`models.py`):
```python
class Subtitle(BaseModel):
    id: str
    text: str

class Slide(BaseModel):
    ...
    subtitles: list[Subtitle] = []   # nuevo campo (default [] = backward compat de carga)
```
`SlideLayout.positions` ya es `dict[str, LayoutBox]` por id genérico → sirve para
`subtitle` ids sin cambios de tipo.

Frontend (`types/index.ts`): tipo `Subtitle { id: string; text: string }` y
`Slide.subtitles: Subtitle[]`.

## Backend — render en PPTX

`pptx_generator.py`:
- **Quitar** el bloque de auto-derivación (`:134-140`): `subtitle_text` pasa a `""`
  siempre. `@Subtitulo` se sustituye por `""`.
- Nueva función `_add_subtitle_textboxes(slide, slide_def, free_area, font_override)`
  que espeja `_add_analyses_textboxes`:
  - Para cada `slide_def.subtitles`, si su id está en `layout.positions`, usar ese
    `LayoutBox`; si no, apilar en una banda fallback (banda **superior** del
    `free_area`, para no chocar con la banda inferior de análisis).
  - Render con `_add_textbox` (sin callout/dashed; el subtítulo es texto plano).
- Llamar `_add_subtitle_textboxes` en `_add_slide_content` (junto a la llamada a
  `_add_analyses_textboxes`, pptx_generator.py:260).

## Backend — layout AI

`api.py` (`suggest_slide_layout` y el parseo de retorno):
- Al armar `payload_shapes`, agregar un shape por cada `slide.subtitles` con
  `kind: "subtitle"`, `id: f"subtitle_{sub.id}"`, y su texto (para que Claude sepa
  qué es y lo ubique). Tamaño estimado como los análisis.
- En el parseo de `raw["elements"]`, reconocer el prefijo `subtitle_` →
  `key = eid[len("subtitle_"):]`, y escribir en `positions[key]` (mismo formato que
  analysis, sin `callout`/`box_style`; font_pt default de texto).
- Los helpers `_enforce_multi_row` / `_reposition_analyses` operan sobre chart/analysis;
  los subtitles quedan donde Claude los puso (o banda fallback en render). No se fuerzan.

## Frontend — UI (ConfigPanel, nivel slide)

En `ConfigPanel.tsx`, sección nueva "Textos de pregunta" a nivel slide (cerca del
campo "Título"):
- Botón **"Insertar texto de pregunta"** → menú/desplegable con las preguntas de los
  charts de la slide, deduplicadas por `question_id`, mostrando `"{código}. {texto}"`.
  Al elegir una, se agrega un `Subtitle` con ese texto (editable). Si la slide no tiene
  charts, el botón se deshabilita (no hay pregunta de dónde derivar).
- Lista de los `subtitles` actuales: cada uno un `<textarea>` editable + botón borrar.

Store (`store/project.ts`), nuevas acciones:
- `addSubtitle(slideId: string, text: string): void` — agrega `{id: uid("sub"), text}`.
- `updateSubtitle(slideId: string, subId: string, text: string): void`.
- `removeSubtitle(slideId: string, subId: string): void`.
Todas mutan `state.slides[…].subtitles` inmutablemente (patrón de las otras acciones).

## Manejo de errores / borde

- Slide sin charts → no hay pregunta para derivar → botón "Insertar" deshabilitado.
- Subtitle cuyo id no está en `layout.positions` → banda fallback superior (no rompe).
- Cargar un proyecto viejo sin `subtitles` → default `[]` (Pydantic + tipo TS).
- Borrar un chart no borra subtitles ya insertados (son snapshots independientes).
- Múltiples subtitles sin posición AI → se apilan en la banda superior.

## Testing

Backend (pytest, `arch -arm64`):
1. `Subtitle` / `Slide.subtitles` default `[]`; un ProjectState viejo (sin el campo)
   valida OK.
2. `pptx_generator`: con `slide.subtitles=[{id,text}]` y sin `layout.positions`, el
   PPTX contiene el texto (textbox en banda fallback); `@Subtitulo` del template queda
   vacío incluso con una sola pregunta (ya no auto-deriva).
3. `pptx_generator`: con `layout.positions[sub_id]` seteado, el textbox usa esas
   coordenadas.
4. `suggest_slide_layout`: payload incluye un shape `kind:"subtitle"` por subtitle; un
   `raw.elements` con id `subtitle_<x>` se parsea a `positions["<x>"]`.

Frontend (vitest):
5. store: `addSubtitle` agrega con id único; `updateSubtitle` cambia el texto;
   `removeSubtitle` lo saca.
6. `ConfigPanel`: botón "Insertar" deshabilitado sin charts; con un chart, al insertar
   aparece un textarea con `"{código}. {texto}"`; editar y borrar funcionan.

## Fuera de alcance
- Editar el texto de la pregunta en el `parsed_db` (solo se edita la copia insertada).
- Mostrar los subtítulos en el Preview del editor (no renderiza contenido).
- Estilos de caja (callout/dashed) para subtítulos — es texto plano.
- Migrar automáticamente el viejo subtítulo auto a un `Subtitle` insertado.
