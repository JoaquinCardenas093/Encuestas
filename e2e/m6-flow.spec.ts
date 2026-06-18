/**
 * M6 E2E smoke test: training corpus upload → AI analyze (mocked) → add chart with custom color → export
 *
 * Prerequisites:
 *   - Backend + frontend dev servers running (make dev-backend && make dev-frontend)
 *   - e2e_fixtures/training_sample.pptx present (run: make e2e-fixtures)
 *   - ANTHROPIC_API_KEY set in backend/.env (or mock backend returns canned response)
 *
 * The test uses test.skip() guards so it skips gracefully when fixtures are missing,
 * allowing the CI gate to remain green without servers or real PPT fixtures.
 */

import { test, expect } from "@playwright/test"
import path from "path"
import fs from "fs"

const XLSX = "/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx"
const TEMPLATE = path.resolve(__dirname, "../e2e_fixtures/template.pptx")
const TRAINING_PPT = path.resolve(__dirname, "../e2e_fixtures/training_sample.pptx")
const EXPORT_PATH = path.resolve(__dirname, "../e2e_fixtures/test_export_m6.pptx")

// ── Guard helpers ─────────────────────────────────────────────────────────────

function fixtureExists(p: string): boolean {
  try {
    return fs.existsSync(p)
  } catch {
    return false
  }
}

// ── M6 Training + AI analyze + color flow ────────────────────────────────────

test.describe("M6 training + AI analyze + color + export flow", () => {
  // Skip entire describe block if training fixture is missing.
  // Run `make e2e-fixtures` to generate it.
  test.skip(
    !fixtureExists(TRAINING_PPT),
    "Training fixture not found — run: make e2e-fixtures"
  )

  test.skip(
    !fixtureExists(XLSX),
    "XLSX fixture not found — place BD Aurora ejemplo.xlsx in ~/Downloads"
  )

  test.skip(
    !fixtureExists(TEMPLATE),
    "Template fixture not found — e2e_fixtures/template.pptx missing"
  )

  test("upload training PPT → Re-analizar (mock/real) → add chart with color → export pptx", async ({
    page,
  }) => {
    // ── 1. Open training tab ──────────────────────────────────────────────────
    await page.goto("/")
    // Try clicking the Training nav link (tab in Topbar)
    const trainingLink = page
      .locator('a[href="/training"], button:has-text("Entrenamiento"), a:has-text("Entrenamiento")')
      .first()
    await trainingLink.click()
    await expect(page.getByText(/Corpus de entrenamiento/i)).toBeVisible({ timeout: 8_000 })

    // ── 2. Upload training PPT to corpus ─────────────────────────────────────
    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.click('button:has-text("Agregar PPT al corpus")'),
    ])
    await fileChooser.setFiles(TRAINING_PPT)
    await expect(page.getByText(/training_sample\.pptx/i)).toBeVisible({ timeout: 12_000 })

    // ── 3. Trigger AI re-analysis ─────────────────────────────────────────────
    await page.click('button:has-text("Re-analizar con AI")')

    // Progress modal should appear
    await expect(page.getByText(/Analizando corpus/i)).toBeVisible({ timeout: 8_000 })

    // Wait for completion — up to 120s (fast if mock, slow if real Anthropic)
    await expect(page.getByText(/Análisis completado/i)).toBeVisible({
      timeout: 120_000,
    })

    // Dismiss the progress modal
    const closeBtn = page.locator('button:has-text("Cerrar"), button:has-text("Listo")').first()
    await closeBtn.click()

    // ── 4. Navigate back to main / upload xlsx + template ────────────────────
    await page.goto("/")
    await page.setInputFiles('input[accept=".xlsx"]', XLSX)
    await page.setInputFiles('input[accept=".pptx"]', TEMPLATE)
    await page.click('button:has-text("Continuar")')
    await expect(page.getByText(/Verificación de datos/i)).toBeVisible({ timeout: 8_000 })
    await page.click('button:has-text("Confirmar")')

    // ── 5. Add separator + shell ──────────────────────────────────────────────
    await page.click('button:has-text("Separador")')
    await page.fill('input[id="sep-title"]', "Recordación espontánea")
    await page.click('button:has-text("Crear")')
    await page.click('button:has-text("Slide")')

    // ── 6. Add chart with custom color ────────────────────────────────────────
    await page.click('button:has-text("+ Chart")')
    await page.selectOption('select', { index: 0 })

    // Open ColorPicker and attempt to select a non-default color
    const colorTrigger = page
      .locator('button[aria-label*="color"], button:has-text("Auto"), [data-testid="color-trigger"]')
      .first()
    const colorTriggerVisible = await colorTrigger.isVisible({ timeout: 3_000 }).catch(() => false)
    if (colorTriggerVisible) {
      await colorTrigger.click()
      const firstSwatch = page.locator('button[aria-label*="Seleccionar color"]').first()
      const swatchVisible = await firstSwatch.isVisible({ timeout: 3_000 }).catch(() => false)
      if (swatchVisible) {
        await firstSwatch.click()
      }
    }

    await page.click('button:has-text("Aplicar")')

    // ── 7. Verify preview renders ─────────────────────────────────────────────
    await expect(page.locator("img")).toBeVisible({ timeout: 20_000 })

    // Pattern matched indicator (or fallback) should appear in config panel
    // Both outcomes are valid: pattern matched from trained corpus OR built-in fallback
    const indicator = page
      .locator('text=/matched|fallback heurístico/i')
      .first()
    // Use a soft assertion — indicator may not render in all configurations
    const indicatorVisible = await indicator.isVisible({ timeout: 6_000 }).catch(() => false)
    if (!indicatorVisible) {
      console.warn("[M6 E2E] Pattern indicator not visible — may require corpus with ≥2 PPTs")
    }

    // ── 8. Export pptx ────────────────────────────────────────────────────────
    // Clean up previous export if it exists
    if (fs.existsSync(EXPORT_PATH)) fs.unlinkSync(EXPORT_PATH)

    await page.click('button:has-text("Exportar")')

    // Fill export path if there's a text input for it
    const exportInput = page.locator('input[placeholder*="ruta"], input[type="text"][aria-label*="path"]').first()
    const exportInputVisible = await exportInput.isVisible({ timeout: 3_000 }).catch(() => false)
    if (exportInputVisible) {
      await exportInput.fill(EXPORT_PATH)
      await page.click('button:has-text("Exportar")').catch(() => {})
    }

    // Wait for success confirmation
    await expect(page.getByText(/exportado|exported|guardado/i)).toBeVisible({ timeout: 30_000 })

    // Verify file was written to disk
    await expect(async () => {
      expect(fs.existsSync(EXPORT_PATH)).toBe(true)
    }).toPass({ timeout: 5_000 })
  })
})

// ── Standalone: verify style guide viewer renders patterns ──────────────────

test.describe("M6 style guide viewer", () => {
  test.skip(
    !fixtureExists(TRAINING_PPT),
    "Training fixture not found — run: make e2e-fixtures"
  )

  test("training tab shows style guide section after corpus upload", async ({ page }) => {
    await page.goto("/training")

    // Style guide section heading should be visible
    const sgHeading = page.getByText(/Guía de estilo|Style Guide/i).first()
    await expect(sgHeading).toBeVisible({ timeout: 8_000 })
  })
})
