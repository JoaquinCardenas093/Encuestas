# Spec del template.pptx

El template define el branding y los layouts base. Debe cumplir:

## Estructura exacta

**2 slides**, en este orden:

1. **Slide 1 = shell** (canvas para charts + análisis)
2. **Slide 2 = separador** (sección divider)

Si el orden está invertido, app muestra warning con opción de swap manual al subir.

## Placeholders

Cada slide debe tener un textbox con `@Titulo` exacto. El shell puede tener adicionalmente `@Notas` (opcional).

Variables soportadas:
- `@Titulo` — título de slide (separador) o título de sección heredado (shell). Requerido.
- `@Notas` — texto auto-computado por app `{tipo_respuesta}. Número de observaciones: {N}`. Opcional.

Variables futuras (no MVP): `@Subtitulo`, `@NumSlide`, `@Fecha`.

## Área libre del shell

App calcula automáticamente la zona libre donde meter charts y análisis: detecta el rectángulo más grande no ocupado por shapes/placeholders fijos.

Para máxima zona libre, mantené el branding (logo, líneas) en bordes superior/inferior, dejando el centro libre.

## Tamaño slide

Recomendado: 16:9 estándar (13.33 × 7.5 in). Otros tamaños funcionan, el área libre se recalcula.

## Fuente

La fuente del primer textbox del shell se considera fuente default. El usuario puede sobrescribir con el font picker al subir el xlsx (override total en analyses y charts generados).

## Ejemplo mínimo

```
Slide 1 (shell):
  - Textbox top-left "@Titulo"
  - Textbox bottom-left "@Notas"
  - Logo top-right (PNG)
  - Línea separadora horizontal bajo header

Slide 2 (separador):
  - Textbox medio "Análisis de resultados\n@Titulo"
  - Logo lateral
```
