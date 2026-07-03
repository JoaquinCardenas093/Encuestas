# Diseño: análisis guiado por contexto opcional del usuario

**Fecha:** 2026-07-03
**Estado:** aprobado, pendiente de plan de implementación

## Problema

Los análisis generados por AI ("estan un poco malos") no siempre enfocan lo que el usuario quiere. Hoy el análisis se genera solo a partir de los datos (scope slide = todos los charts, scope chart = uno). No hay forma de que el usuario dé una guía/contexto para orientar el análisis.

## Objetivo

Un campo de **contexto/guía opcional** en el modal de análisis, para ambos scopes (slide y chart). Si el usuario escribe algo, el LLM lo usa como guía de prioridad alta para enfocar/encuadrar el análisis. Si queda en blanco, comportamiento actual (analiza según el scope).

## Decisiones (cerradas con el usuario)

- **Ambos scopes** (slide y chart) tienen el campo.
- **Efímero:** el hint se usa solo al momento de generar. NO se persiste en el modelo `Analysis` (sin cambio de modelo backend). Sin "regenerar" análisis existentes.

## No-objetivos

- Persistir la guía en el `Analysis`.
- Regenerar análisis ya creados con la guía.
- Cambiar cómo se agregan los datos por scope (ya funciona: slide=todos los charts, chart=uno).

## Arquitectura

Flujo aditivo sobre el pipeline existente: modal → client → endpoint → `generate_analysis` → prompt.

### 1. Backend — `generate_analysis` (`backend/aurum_encuestas/llm_client.py`)

Firma nueva: `generate_analysis(scope: str, context: dict, user_hint: str | None = None) -> str` (param opcional al final; llamadas existentes sin `user_hint` siguen funcionando).

Comportamiento:
- Normaliza: `hint = (user_hint or "").strip()[:500]` (cap 500 chars).
- Si `hint`: agrega al final del `user_msg` (en AMBAS ramas — multi-chart y single-chart) una línea:
  ```
  Guía del usuario (prioridad alta): {hint}
  Enfocá y encuadrá el análisis según esta guía, sin inventar datos ni contradecir las cifras.
  ```
- Si `hint` vacío: `user_msg` idéntico a hoy.

### 2. Backend — endpoint (`backend/aurum_encuestas/api.py`)

`class GenerateAnalysisRequest` gana `user_hint: str | None = None`.
`generate_analysis_endpoint`: la llamada pasa `generate_analysis(req.scope, ctx, req.user_hint)`.

### 3. Frontend — client (`frontend/src/api/client.ts`)

`generateAnalysis(scope, context, opts?)` — `opts` gana `user_hint?: string`. Se envía en el body como `user_hint: opts?.user_hint ?? null`.

### 4. Frontend — modal (`frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`)

- Nuevo estado `const [userHint, setUserHint] = useState("")`.
- Textarea **"Contexto / guía (opcional)"** visible para ambos scopes (arriba del botón Generar o bajo el selector de scope).
- `handleGenerate` pasa `user_hint: userHint` en las opts de `api.generateAnalysis`.
- Se resetea (`setUserHint("")`) junto con los demás campos al aceptar/cerrar.

## Data flow

```
modal (userHint) → api.generateAnalysis(scope, ctx, {state, slide_id, target_id, user_hint})
  → POST /generate-analysis {..., user_hint}
  → generate_analysis(scope, ctx, user_hint)
  → prompt con "Guía del usuario: <hint>" (si no vacío)
  → LLM → texto enfocado
```

## Edge cases

- **Hint vacío / solo espacios:** se ignora (`.strip()` vacío → rama actual, prompt sin cambios).
- **Hint muy largo:** se capa a 500 chars para no inflar el prompt.
- **Sin AI (`_client is None`):** igual que hoy — `generate_analysis` levanta `LLMError`; el hint no cambia eso.
- **Ambos scopes:** el hint se agrega igual en la rama multi-chart (slide) y en la flat (chart único).

## Componentes y límites

- `generate_analysis`: única responsabilidad = armar prompt + llamar LLM. El hint es un input más.
- Endpoint / client / modal: solo cablean el `user_hint` a través. Sin lógica nueva de datos.

## Testing

**Backend** (`backend/tests/test_llm_client.py`):
- `test_generate_analysis_includes_user_hint`: mock `_client`, llamar con `user_hint="enfocate en jóvenes"` → el `messages.create` recibe un `user_msg` que contiene `"enfocate en jóvenes"` y `"Guía del usuario"`.
- `test_generate_analysis_blank_hint_unchanged`: `user_hint=""` (y `None`) → el `user_msg` NO contiene `"Guía del usuario"` (prompt como hoy).
- `test_generate_analysis_hint_capped`: hint > 500 chars → el prompt incluye solo 500.

**Backend endpoint** (`backend/tests/test_api.py`, si hay patrón): `/generate-analysis` con `user_hint` no rompe (200); el hint llega a `generate_analysis` (se puede verificar con monkeypatch).

**Frontend:** `tsc --noEmit` limpio; si hay patrón de test del modal, un test chico de que el textarea manda `user_hint` en el request.

## Archivos afectados

- `backend/aurum_encuestas/llm_client.py` — `generate_analysis` param `user_hint` + inyección al prompt.
- `backend/aurum_encuestas/api.py` — `GenerateAnalysisRequest.user_hint` + pasar al llamar.
- `backend/tests/test_llm_client.py` — tests del hint.
- `frontend/src/api/client.ts` — `generateAnalysis` opts `user_hint`.
- `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx` — textarea + estado + pasar `user_hint`.
