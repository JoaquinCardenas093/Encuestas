import { useState, useEffect } from "react"
import PaletteRow from "./PaletteRow"
import HexInput from "./HexInput"
import { useStyleGuideStore } from "../../store/styleGuide"

// Built-in default 11 neutral greys + accent colors (spec Q15-A)
const DEFAULT_COLORS = [
  "#404040", "#595959", "#7F7F7F", "#BFBFBF", "#D9D9D9",
  "#FFC000", "#4472C4", "#C00000", "#70AD47", "#000000", "#FFFFFF",
]

const RECENT_COLORS_ENDPOINT = "/api/config/recent-colors"

interface Props {
  open: boolean
  value: string       // current color; "" means "Auto"
  onChange(color: string): void
  onClose(): void
}

export default function ColorPicker({ open, value, onChange, onClose }: Props) {
  const [pendingColor, setPendingColor] = useState(value)
  const [recentColors, setRecentColors] = useState<string[]>([])

  const styleGuide = useStyleGuideStore((s: { styleGuide: { global: { suggested_palette: string[] } } | null }) => s.styleGuide)
  const suggestedPalette = styleGuide?.global.suggested_palette ?? []

  // Load recent colors from config
  useEffect(() => {
    if (!open) return
    fetch(RECENT_COLORS_ENDPOINT)
      .then((r) => r.ok ? r.json() : { recent_colors: [] })
      .then((data) => setRecentColors(data.recent_colors ?? []))
      .catch(() => setRecentColors([]))
  }, [open])

  // Sync pending when value changes externally
  useEffect(() => {
    setPendingColor(value)
  }, [value])

  if (!open) return null

  const handleSelect = (color: string) => {
    setPendingColor(color)
    onChange(color)
  }

  const handleOK = () => {
    onChange(pendingColor)
    onClose()
  }

  const handleAuto = () => {
    onChange("")
    onClose()
  }

  return (
    <div className="absolute z-50 top-full mt-1 left-0 bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-4 w-72">
      {suggestedPalette.length > 0 && (
        <PaletteRow
          label="Sugeridas del training"
          colors={suggestedPalette}
          onSelect={handleSelect}
          selectedColor={pendingColor}
        />
      )}

      <PaletteRow
        label="Defaults"
        colors={DEFAULT_COLORS}
        onSelect={handleSelect}
        selectedColor={pendingColor}
      />

      <PaletteRow
        label="Recientes"
        colors={recentColors}
        onSelect={handleSelect}
        selectedColor={pendingColor}
      />

      <div className="mb-4">
        <div className="text-xs text-neutral-500 mb-1">Hex:</div>
        <HexInput value={pendingColor} onChange={setPendingColor} />
      </div>

      <div className="flex items-center gap-2 justify-between">
        <button
          type="button"
          onClick={handleAuto}
          aria-label="Auto"
          className="text-xs px-2 py-1.5 rounded bg-neutral-700 hover:bg-neutral-600 flex items-center gap-1"
        >
          Auto
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            aria-label="Cancelar"
            className="text-xs px-3 py-1.5 rounded bg-neutral-700 hover:bg-neutral-600"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleOK}
            aria-label="OK"
            className="text-xs px-3 py-1.5 rounded bg-accent text-neutral-900 font-semibold"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}
