# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: m6-flow.spec.ts >> M6 training + AI analyze + color + export flow >> upload training PPT → Re-analizar (mock/real) → add chart with color → export pptx
- Location: m6-flow.spec.ts:52:7

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/Análisis completado/i)
Expected: visible
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 120000ms
  - waiting for getByText(/Análisis completado/i)

```

```yaml
- banner:
  - link "AurumEncuestas":
    - /url: /
  - navigation:
    - link "Editor":
      - /url: /editor
    - link "Entrenamiento":
      - /url: /training
  - button "Abrir ▾"
  - button "Guardar" [disabled]
  - button "Exportar PPTX" [disabled]
- main:
  - heading "Corpus de entrenamiento" [level=2]
  - paragraph: Style guide built-in (fallback) · 5 patterns · actualizado 6/16/2026
  - heading "PPTs en corpus (3)" [level=3]:
    - img
    - text: PPTs en corpus (3)
  - button "Agregar PPT al corpus":
    - img
    - text: Agregar PPT al corpus
  - text: Aurum - Encuestas - Precancelaciones - MAF - Mayo 2026.pptx48 charts · agregado 6/17/2026
  - button "eliminar":
    - img
  - text: PPT Aurora ejemplo.pptx30 charts · agregado 6/17/2026
  - button "eliminar":
    - img
  - text: training_sample.pptx2 charts · agregado 6/18/2026
  - button "eliminar":
    - img
  - heading "Style guide" [level=3]
  - button "Ver style guide":
    - img
    - text: Ver style guide
  - button "Re-analizar con AI":
    - img
    - text: Re-analizar con AI
  - text: "Tipos disponibles: PIE, DONUT, BAR_HORIZONTAL, BAR_CLUSTERED, COLUMN_CLUSTERED, TABLE_WITH_MINIBARS"
  - status "Analizando"
  - heading "Analizando corpus con AI..." [level=3]
  - paragraph: 70% — Validando y reparando style guide...
```

# Test source

```ts
  1   | /**
  2   |  * M6 E2E smoke test: training corpus upload → AI analyze (mocked) → add chart with custom color → export
  3   |  *
  4   |  * Prerequisites:
  5   |  *   - Backend + frontend dev servers running (make dev-backend && make dev-frontend)
  6   |  *   - e2e_fixtures/training_sample.pptx present (run: make e2e-fixtures)
  7   |  *   - ANTHROPIC_API_KEY set in backend/.env (or mock backend returns canned response)
  8   |  *
  9   |  * The test uses test.skip() guards so it skips gracefully when fixtures are missing,
  10  |  * allowing the CI gate to remain green without servers or real PPT fixtures.
  11  |  */
  12  | 
  13  | import { test, expect } from "@playwright/test"
  14  | import path from "path"
  15  | import fs from "fs"
  16  | 
  17  | const XLSX = "/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx"
  18  | const TEMPLATE = path.resolve(__dirname, "../e2e_fixtures/template.pptx")
  19  | const TRAINING_PPT = path.resolve(__dirname, "../e2e_fixtures/training_sample.pptx")
  20  | const EXPORT_PATH = path.resolve(__dirname, "../e2e_fixtures/test_export_m6.pptx")
  21  | 
  22  | // ── Guard helpers ─────────────────────────────────────────────────────────────
  23  | 
  24  | function fixtureExists(p: string): boolean {
  25  |   try {
  26  |     return fs.existsSync(p)
  27  |   } catch {
  28  |     return false
  29  |   }
  30  | }
  31  | 
  32  | // ── M6 Training + AI analyze + color flow ────────────────────────────────────
  33  | 
  34  | test.describe("M6 training + AI analyze + color + export flow", () => {
  35  |   // Skip entire describe block if training fixture is missing.
  36  |   // Run `make e2e-fixtures` to generate it.
  37  |   test.skip(
  38  |     !fixtureExists(TRAINING_PPT),
  39  |     "Training fixture not found — run: make e2e-fixtures"
  40  |   )
  41  | 
  42  |   test.skip(
  43  |     !fixtureExists(XLSX),
  44  |     "XLSX fixture not found — place BD Aurora ejemplo.xlsx in ~/Downloads"
  45  |   )
  46  | 
  47  |   test.skip(
  48  |     !fixtureExists(TEMPLATE),
  49  |     "Template fixture not found — e2e_fixtures/template.pptx missing"
  50  |   )
  51  | 
  52  |   test("upload training PPT → Re-analizar (mock/real) → add chart with color → export pptx", async ({
  53  |     page,
  54  |   }) => {
  55  |     // ── 1. Open training tab ──────────────────────────────────────────────────
  56  |     await page.goto("/")
  57  |     // Try clicking the Training nav link (tab in Topbar)
  58  |     const trainingLink = page
  59  |       .locator('a[href="/training"], button:has-text("Entrenamiento"), a:has-text("Entrenamiento")')
  60  |       .first()
  61  |     await trainingLink.click()
  62  |     await expect(page.getByText(/Corpus de entrenamiento/i)).toBeVisible({ timeout: 8_000 })
  63  | 
  64  |     // ── 2. Upload training PPT to corpus ─────────────────────────────────────
  65  |     const [fileChooser] = await Promise.all([
  66  |       page.waitForEvent("filechooser"),
  67  |       page.click('button:has-text("Agregar PPT al corpus")'),
  68  |     ])
  69  |     await fileChooser.setFiles(TRAINING_PPT)
  70  |     await expect(page.getByText(/training_sample\.pptx/i)).toBeVisible({ timeout: 12_000 })
  71  | 
  72  |     // ── 3. Trigger AI re-analysis ─────────────────────────────────────────────
  73  |     await page.click('button:has-text("Re-analizar con AI")')
  74  | 
  75  |     // Progress modal should appear
  76  |     await expect(page.getByText(/Analizando corpus/i)).toBeVisible({ timeout: 8_000 })
  77  | 
  78  |     // Wait for completion — up to 120s (fast if mock, slow if real Anthropic)
> 79  |     await expect(page.getByText(/Análisis completado/i)).toBeVisible({
      |                                                          ^ Error: expect(locator).toBeVisible() failed
  80  |       timeout: 120_000,
  81  |     })
  82  | 
  83  |     // Dismiss the progress modal
  84  |     const closeBtn = page.locator('button:has-text("Cerrar"), button:has-text("Listo")').first()
  85  |     await closeBtn.click()
  86  | 
  87  |     // ── 4. Navigate back to main / upload xlsx + template ────────────────────
  88  |     await page.goto("/")
  89  |     await page.setInputFiles('input[accept=".xlsx"]', XLSX)
  90  |     await page.setInputFiles('input[accept=".pptx"]', TEMPLATE)
  91  |     await page.click('button:has-text("Continuar")')
  92  |     await expect(page.getByText(/Verificación de datos/i)).toBeVisible({ timeout: 8_000 })
  93  |     await page.click('button:has-text("Confirmar")')
  94  | 
  95  |     // ── 5. Add separator + shell ──────────────────────────────────────────────
  96  |     await page.click('button:has-text("Separador")')
  97  |     await page.fill('input[id="sep-title"]', "Recordación espontánea")
  98  |     await page.click('button:has-text("Crear")')
  99  |     await page.click('button:has-text("Slide")')
  100 | 
  101 |     // ── 6. Add chart with custom color ────────────────────────────────────────
  102 |     await page.click('button:has-text("+ Chart")')
  103 |     await page.selectOption('select', { index: 0 })
  104 | 
  105 |     // Open ColorPicker and attempt to select a non-default color
  106 |     const colorTrigger = page
  107 |       .locator('button[aria-label*="color"], button:has-text("Auto"), [data-testid="color-trigger"]')
  108 |       .first()
  109 |     const colorTriggerVisible = await colorTrigger.isVisible({ timeout: 3_000 }).catch(() => false)
  110 |     if (colorTriggerVisible) {
  111 |       await colorTrigger.click()
  112 |       const firstSwatch = page.locator('button[aria-label*="Seleccionar color"]').first()
  113 |       const swatchVisible = await firstSwatch.isVisible({ timeout: 3_000 }).catch(() => false)
  114 |       if (swatchVisible) {
  115 |         await firstSwatch.click()
  116 |       }
  117 |     }
  118 | 
  119 |     await page.click('button:has-text("Aplicar")')
  120 | 
  121 |     // ── 7. Verify preview renders ─────────────────────────────────────────────
  122 |     await expect(page.locator("img")).toBeVisible({ timeout: 20_000 })
  123 | 
  124 |     // Pattern matched indicator (or fallback) should appear in config panel
  125 |     // Both outcomes are valid: pattern matched from trained corpus OR built-in fallback
  126 |     const indicator = page
  127 |       .locator('text=/matched|fallback heurístico/i')
  128 |       .first()
  129 |     // Use a soft assertion — indicator may not render in all configurations
  130 |     const indicatorVisible = await indicator.isVisible({ timeout: 6_000 }).catch(() => false)
  131 |     if (!indicatorVisible) {
  132 |       console.warn("[M6 E2E] Pattern indicator not visible — may require corpus with ≥2 PPTs")
  133 |     }
  134 | 
  135 |     // ── 8. Export pptx ────────────────────────────────────────────────────────
  136 |     // Clean up previous export if it exists
  137 |     if (fs.existsSync(EXPORT_PATH)) fs.unlinkSync(EXPORT_PATH)
  138 | 
  139 |     await page.click('button:has-text("Exportar")')
  140 | 
  141 |     // Fill export path if there's a text input for it
  142 |     const exportInput = page.locator('input[placeholder*="ruta"], input[type="text"][aria-label*="path"]').first()
  143 |     const exportInputVisible = await exportInput.isVisible({ timeout: 3_000 }).catch(() => false)
  144 |     if (exportInputVisible) {
  145 |       await exportInput.fill(EXPORT_PATH)
  146 |       await page.click('button:has-text("Exportar")').catch(() => {})
  147 |     }
  148 | 
  149 |     // Wait for success confirmation
  150 |     await expect(page.getByText(/exportado|exported|guardado/i)).toBeVisible({ timeout: 30_000 })
  151 | 
  152 |     // Verify file was written to disk
  153 |     await expect(async () => {
  154 |       expect(fs.existsSync(EXPORT_PATH)).toBe(true)
  155 |     }).toPass({ timeout: 5_000 })
  156 |   })
  157 | })
  158 | 
  159 | // ── Standalone: verify style guide viewer renders patterns ──────────────────
  160 | 
  161 | test.describe("M6 style guide viewer", () => {
  162 |   test.skip(
  163 |     !fixtureExists(TRAINING_PPT),
  164 |     "Training fixture not found — run: make e2e-fixtures"
  165 |   )
  166 | 
  167 |   test("training tab shows style guide section after corpus upload", async ({ page }) => {
  168 |     await page.goto("/training")
  169 | 
  170 |     // Style guide section heading should be visible
  171 |     const sgHeading = page.getByText(/Guía de estilo|Style Guide/i).first()
  172 |     await expect(sgHeading).toBeVisible({ timeout: 8_000 })
  173 |   })
  174 | })
  175 | 
```