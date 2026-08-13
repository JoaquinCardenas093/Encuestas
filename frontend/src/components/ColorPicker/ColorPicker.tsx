import { useState, useEffect, useRef } from "react"
import { createPortal } from "react-dom"
import PaletteRow from "./PaletteRow"
import HexInput from "./HexInput"
import { useStyleGuideStore } from "../../store/styleGuide"
import { sessionHeader } from "../../api/session"

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
  anchorRef?: React.RefObject<HTMLElement | null>  // optional anchor for portal positioning
}

export default function ColorPicker({ open, value, onChange, onClose, anchorRef }: Props) {
  const [pendingColor, setPendingColor] = useState(value)
  const [recentColors, setRecentColors] = useState<string[]>([])
  const internalAnchorRef = useRef<HTMLDivElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)

  const styleGuide = useStyleGuideStore((s: { styleGuide: { global: { suggested_palette: string[] } } | null }) => s.styleGuide)
  const suggestedPalette = styleGuide?.global.suggested_palette ?? []

  useEffect(() => {
    if (!open) return
    fetch(RECENT_COLORS_ENDPOINT, { headers: { ...sessionHeader() } })
      .then((r) => r.ok ? r.json() : { recent_colors: [] })
      .then((data) => setRecentColors(data.recent_colors ?? []))
      .catch(() => setRecentColors([]))
  }, [open])

  useEffect(() => {
    setPendingColor(value)
  }, [value])

  // Compute portal coords from anchor (or sentinel) on open + scroll/resize
  useEffect(() => {
    if (!open) return
    const recompute = () => {
      const anchorEl = anchorRef?.current ?? internalAnchorRef.current
      if (!anchorEl) return
      const r = anchorEl.getBoundingClientRect()
      const POPOVER_W = 288  // matches w-72
      const POPOVER_H = 360  // approx
      let top = r.bottom + 4
      let left = r.right - POPOVER_W
      // Clamp inside viewport
      if (left < 8) left = 8
      if (top + POPOVER_H > window.innerHeight - 8) top = window.innerHeight - POPOVER_H - 8
      if (top < 8) top = 8
      setCoords({ top, left })
    }
    recompute()
    window.addEventListener("scroll", recompute, true)
    window.addEventListener("resize", recompute)
    return () => {
      window.removeEventListener("scroll", recompute, true)
      window.removeEventListener("resize", recompute)
    }
  }, [open, anchorRef])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (popoverRef.current?.contains(target)) return
      const anchorEl = anchorRef?.current ?? internalAnchorRef.current
      if (anchorEl?.contains(target)) return
      onClose()
    }
    window.addEventListener("mousedown", handler)
    return () => window.removeEventListener("mousedown", handler)
  }, [open, anchorRef, onClose])

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

  // Sentinel div (when no anchorRef passed) — caller wraps button next to this
  if (!anchorRef) {
    return (
      <>
        <div ref={internalAnchorRef} className="absolute inset-0 pointer-events-none" />
        {coords ? createPortal(
          <ColorPickerPanel
            popoverRef={popoverRef}
            coords={coords}
            suggestedPalette={suggestedPalette}
            pendingColor={pendingColor}
            setPendingColor={setPendingColor}
            recentColors={recentColors}
            handleSelect={handleSelect}
            handleOK={handleOK}
            handleAuto={handleAuto}
            onClose={onClose}
          />, document.body) : null}
      </>
    )
  }

  if (!coords) return null
  return createPortal(
    <ColorPickerPanel
      popoverRef={popoverRef}
      coords={coords}
      suggestedPalette={suggestedPalette}
      pendingColor={pendingColor}
      setPendingColor={setPendingColor}
      recentColors={recentColors}
      handleSelect={handleSelect}
      handleOK={handleOK}
      handleAuto={handleAuto}
      onClose={onClose}
    />, document.body)
}

interface PanelProps {
  popoverRef: React.MutableRefObject<HTMLDivElement | null>
  coords: { top: number; left: number }
  suggestedPalette: string[]
  pendingColor: string
  setPendingColor: (c: string) => void
  recentColors: string[]
  handleSelect: (c: string) => void
  handleOK: () => void
  handleAuto: () => void
  onClose: () => void
}

function ColorPickerPanel({
  popoverRef, coords, suggestedPalette, pendingColor, setPendingColor,
  recentColors, handleSelect, handleOK, handleAuto, onClose,
}: PanelProps) {
  return (
    <div
      ref={popoverRef}
      style={{ position: "fixed", top: coords.top, left: coords.left, zIndex: 9999 }}
      className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-4 w-72 max-w-[calc(100vw-2rem)]"
    >
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
