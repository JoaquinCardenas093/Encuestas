# Convención XLSX esperada (heurística B)

AurumEncuestas auto-detecta la estructura del xlsx con heurística + wizard de verificación 1-click. La convención esperada (matchea 100% del ejemplo Aurum):

## Layout de hojas

Una sola hoja. Nombre típico: `BD - Análisis`. Si tu workbook tiene varias hojas, app usa la primera.

## Filas

| Fila | Contenido |
|---|---|
| 1 | Headers de grupos de breakdown (Rango de edad, Sexo, NSE, Punto) en cols dispersas |
| 2 | Sub-categorías de cada breakdown bajo su grupo. La col donde aparece `General` marca inicio de cada bloque de columnas. |
| 3 | Total muestral (col 2 = "Total", col 3 = N, cols 4+ = N por sub-categoría) |
| 4 a ~17 | Distribución demográfica de la muestra (rows con label en col A) |
| 18+ | Bloques de preguntas |

## Marcador de pregunta

Col A no vacía con uno de:
- `$pN.label` (literal `$p` + dígitos + `.` + texto) — confianza 1.0
- Texto que termina en `?` — confianza 0.9
- Texto largo (>40 chars) — confianza 0.5

## Opciones de pregunta

Filas posteriores a la del marcador, con col A vacía y col B con texto de opción.

## Columnas — 3 bloques

| Bloque | Contenido | Valores |
|---|---|---|
| 1 (cols 3-17 típicamente) | Conteos | enteros > 1 |
| 2 (cols 21-35) | % de fila | 0-1 |
| 3 (cols 41-55) | % de columna | 0-1 |

Cada bloque arranca donde row2 = "General". Detección automática.

## Breakdowns soportados (auto-mapeo)

- `General` (col donde row2=="General")
- `Rango de edad` → id `edad`
- `Sexo` → id `sexo`
- `NSE` → id `nse`
- `Punto` → id `punto`

Cualquier otro breakdown en row1 se ignora.

## Si tu xlsx no matchea

El wizard de verificación lista lo detectado con ✓/⚠. Si hay rojo, podés:
1. Re-exportar el xlsx en la convención
2. Usar "Editar mapping manual" (M5+)
