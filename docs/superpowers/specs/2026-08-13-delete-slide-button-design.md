# Botón para eliminar diapositivas enteras

Fecha: 2026-08-13

## Objetivo

Permitir al usuario borrar una slide completa (con sus charts y análisis) desde el
editor. Hoy se pueden agregar separadores/shells y reordenar, pero no eliminar una
slide individual salvo el "Reset todo" (que borra todas).

## Contexto existente

- `store/project.ts` ya expone `removeSlide(slideId)` (línea ~171). Filtra la slide
  del array y re-aplica `applyTitleInheritance`. **No requiere cambios.**
- El store usa `zundo`/`temporal`: el borrado es reversible con Undo (footer).
- La selección de slide (`selectedId`) vive como estado local en `EditorPage.tsx`,
  no en el store. Se pasa a `SlideRail`, `Preview`, `ConfigPanel`.
- `EditorFooter.tsx` ya usa `window.confirm` para el botón "Reset todo" — patrón
  de confirmación establecido en el proyecto.

## Decisiones (acordadas con el usuario)

1. **Ubicación:** ambos accesos.
   - X en la esquina superior derecha de cada thumbnail, visible en hover.
   - Botón "Eliminar slide" en el footer, opera sobre la slide seleccionada.
2. **Confirmación:** `window.confirm` nativo (consistente con "Reset todo"). Sin
   modal propio.
3. **Selección tras borrar la slide seleccionada:** la vecina anterior; si se borró
   la primera, la primera restante; si no queda ninguna, `null`.

## Alcance de cambios (3 archivos; store y backend intactos)

### 1. `frontend/src/pages/Editor/EditorPage.tsx`

Dueño de `selectedId`. Nuevo handler que centraliza borrado + reubicación de
selección:

```
function handleDeleteSlide(id: string) {
  const idx = slides.findIndex((s) => s.id === id)
  removeSlide(id)
  if (id === selectedId) {
    const remaining = slides.filter((s) => s.id !== id)
    const next = remaining[idx - 1] ?? remaining[0] ?? null
    setSelectedId(next ? next.id : null)
  }
}
```

- `removeSlide` se obtiene del store (`useProjectStore`).
- Se pasa `onDelete={handleDeleteSlide}` a `SlideRail`.
- Se pasa `selectedId` + `onDeleteSlide={handleDeleteSlide}` a `EditorFooter`.

Nota: `slides` se lee del render actual (pre-borrado), por eso `idx` y `remaining`
se calculan con ese snapshot antes/junto al `removeSlide`.

### 2. `frontend/src/pages/Editor/SlideRail.tsx`

- `SlideRail` recibe nueva prop `onDelete(id: string): void` y la pasa a cada
  `SortableThumb`.
- `SortableThumb`: agregar clase `group` al div raíz y un botón X:
  - Posición: `absolute -top-2 -right-2`.
  - Visibilidad: `opacity-0 group-hover:opacity-100`.
  - Icono `X` de `lucide-react` (ya se importa `Plus` de ahí).
  - `data-testid={`delete-slide-${slide.id}`}`, `aria-label="eliminar slide"`.
  - Handler:
    ```
    onPointerDown={(e) => e.stopPropagation()}   // no iniciar drag de dnd-kit
    onClick={(e) => {
      e.stopPropagation()                        // no seleccionar el thumbnail
      if (window.confirm("¿Eliminar esta slide?")) onDelete(slide.id)
    }}
    ```

### 3. `frontend/src/pages/Editor/EditorFooter.tsx`

- Nuevas props: `selectedId: string | null`, `onDeleteSlide(id: string): void`.
- Nuevo botón junto a "Reset todo":
  - Icono `Trash2` de `lucide-react`, texto "Eliminar slide".
  - `disabled={!selectedId}`.
  - `aria-label="eliminar slide"`.
  - Estilo rojo suave consistente con "Reset todo".
  - `onClick`: `if (selectedId && window.confirm("¿Eliminar esta slide?")) onDeleteSlide(selectedId)`.

## Flujo de datos

```
EditorPage (selectedId, handleDeleteSlide)
  ├─ SlideRail    onDelete ──► X en hover (confirm) ──► handleDeleteSlide(thumbId)
  └─ EditorFooter onDeleteSlide + selectedId ──► botón (confirm) ──► handleDeleteSlide(selectedId)

handleDeleteSlide ──► store.removeSlide(id)  (undoable)
                 └──► setSelectedId(vecina)  si se borró la seleccionada
```

## Manejo de errores / borde

- Borrar cuando queda 0 slides: `selectedId` pasa a `null`; `EditorPage` línea ~37
  ya repone la primera cuando vuelva a haber slides. Preview/ConfigPanel deben
  tolerar `slideId=null` (ya lo hacen hoy con el estado inicial).
- Deshacer: Undo del footer revierte el borrado (temporal).
- No hay restricción de tipo: se puede borrar separadores o shells. Al borrar un
  separador, `applyTitleInheritance` recalcula títulos heredados de los shells
  siguientes (comportamiento ya existente en `removeSlide`).

## Testing

Vitest + Testing Library (`frontend/tests` / colocados). Casos:

1. **SlideRail:** el botón X existe por cada thumbnail (`data-testid`); con
   `window.confirm` mockeado a `true`, click llama `onDelete` con el id correcto;
   con `confirm` a `false`, no llama.
2. **EditorFooter:** botón "Eliminar slide" `disabled` cuando `selectedId` es null;
   habilitado y llama `onDeleteSlide(selectedId)` con confirm `true`.
3. **EditorPage (integración/reducer de selección):** borrar la slide seleccionada
   en el medio deja seleccionada la anterior; borrar la primera deja la primera
   restante; borrar la última slide deja `selectedId=null`.

`window.confirm` se mockea (`vi.spyOn(window, "confirm")`).

## Fuera de alcance

- Modal de confirmación propio (se usa nativo).
- Borrado múltiple / selección múltiple.
- Atajo de teclado para borrar (Delete key) — se puede agregar luego.
