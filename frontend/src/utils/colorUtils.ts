/**
 * Normalize a user-typed color string to a 6-char hex string (#RRGGBB).
 * Accepts: "#RGB", "#RRGGBB", "RGB", "RRGGBB".
 * Returns null if not a valid hex color (CSS named colors not supported — intentional, per spec Q15).
 */
export function normalizeHex(input: string): string | null {
  const s = input.trim().replace(/^#/, "")
  if (/^[0-9a-fA-F]{3}$/.test(s)) {
    const [r, g, b] = s.split("")
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase()
  }
  if (/^[0-9a-fA-F]{6}$/.test(s)) {
    return `#${s.toUpperCase()}`
  }
  return null
}

/**
 * Auto-derive N colors from a primary color by varying lightness via lumMod simulation.
 * lumMod in OOXML: value * 100000; here we use CSS hsl lightness approximation.
 *
 * Strategy: parse hex to HSL, generate N shades by spacing lightness from 30% to 85%.
 * If N=1 returns [primary].
 */
export function autoDeriveColors(primary: string, n: number): string[] {
  if (n <= 1) return [primary]
  const hsl = hexToHsl(primary)
  if (!hsl) return Array(n).fill(primary)

  const [h, s] = hsl
  const colors: string[] = []
  for (let i = 0; i < n; i++) {
    // Spread lightness: first slot = original, subsequent slots lighten progressively
    const l = i === 0 ? hsl[2] : Math.min(85, hsl[2] + (55 * i) / (n - 1))
    colors.push(hslToHex(h, s, l))
  }
  return colors
}

function hexToHsl(hex: string): [number, number, number] | null {
  const norm = normalizeHex(hex)
  if (!norm) return null
  const r = parseInt(norm.slice(1, 3), 16) / 255
  const g = parseInt(norm.slice(3, 5), 16) / 255
  const b = parseInt(norm.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, Math.round(l * 100)]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)]
}

function hslToHex(h: number, s: number, l: number): string {
  const sn = s / 100
  const ln = l / 100
  const a = sn * Math.min(ln, 1 - ln)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = ln - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color).toString(16).padStart(2, "0").toUpperCase()
  }
  return `#${f(0)}${f(8)}${f(4)}`
}
