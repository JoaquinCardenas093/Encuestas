import { useState, useEffect } from "react"
import { normalizeHex } from "../../utils/colorUtils"

interface Props {
  value: string
  onChange(hex: string): void
}

export default function HexInput({ value, onChange }: Props) {
  const initRaw = value.replace(/^#/, "")
  const [raw, setRaw] = useState(initRaw)
  const [isInvalid, setIsInvalid] = useState(() => initRaw.length > 0 && normalizeHex(initRaw) === null)

  // Sync external value changes
  useEffect(() => {
    const newRaw = value.replace(/^#/, "")
    setRaw(newRaw)
    setIsInvalid(newRaw.length > 0 && normalizeHex(newRaw) === null)
  }, [value])

  const handleChange = (text: string) => {
    setRaw(text)
    const normalized = normalizeHex(text)
    if (normalized) {
      setIsInvalid(false)
      onChange(normalized)
    } else if (text.length > 0) {
      setIsInvalid(true)
    } else {
      setIsInvalid(false)
    }
  }

  const normalized = normalizeHex(raw)

  return (
    <div className="flex items-center gap-2">
      {normalized && (
        <div
          className="w-5 h-5 rounded border border-neutral-600 flex-shrink-0"
          style={{ backgroundColor: normalized }}
        />
      )}
      <div className="relative">
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-500 text-xs">#</span>
        <input
          type="text"
          role="textbox"
          value={raw}
          onChange={(e) => handleChange(e.target.value)}
          maxLength={6}
          placeholder="#AABBCC"
          className={`pl-5 pr-2 py-1.5 text-xs bg-neutral-950 border rounded w-28 focus:outline-none ${
            isInvalid
              ? "border-red-500 text-red-300"
              : "border-neutral-700 focus:border-neutral-500"
          }`}
        />
      </div>
    </div>
  )
}
