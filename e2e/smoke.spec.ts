import { test, expect } from "@playwright/test"
import path from "path"

const XLSX = "/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx"
const TPL = path.resolve(__dirname, "../e2e_fixtures/template.pptx")

test("upload + wizard + add shell + add chart + export", async ({ page }) => {
  await page.goto("/")
  await page.setInputFiles('input[accept=".xlsx"]', XLSX)
  await page.setInputFiles('input[accept=".pptx"]', TPL)
  await page.click('button:has-text("Continuar")')
  await expect(page.getByText(/Verificación de datos/i)).toBeVisible()
  await page.click('button:has-text("Confirmar")')
  await page.click('button:has-text("Separador")')
  await page.fill('input[id="sep-title"]', "Recordación")
  await page.click('button:has-text("Crear")')
  await page.click('button:has-text("Slide")')
  await page.click('button:has-text("+ Chart")')
  await page.selectOption('select[id="q-select"]', { index: 0 })
  await page.click('input[aria-label="General"]')
  await page.click('button:has-text("Aplicar")')
  await expect(page.locator("img")).toBeVisible({ timeout: 15000 })
})
