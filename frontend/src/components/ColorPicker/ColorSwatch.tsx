interface Props {
  color: string
  onSelect(color: string): void
  isSelected?: boolean
  size?: "sm" | "md"
}

export default function ColorSwatch({ color, onSelect, isSelected = false, size = "md" }: Props) {
  const dim = size === "sm" ? "w-5 h-5" : "w-6 h-6"
  return (
    <button
      type="button"
      onClick={() => onSelect(color)}
      aria-label={`Seleccionar color ${color}`}
      className={`rounded border border-neutral-600 hover:scale-110 transition-transform focus:outline-none ${
        isSelected ? "ring-2 ring-white ring-offset-1 ring-offset-neutral-900" : ""
      }`}
    >
      <div
        className={`${dim} rounded`}
        style={{ backgroundColor: color }}
      />
    </button>
  )
}
