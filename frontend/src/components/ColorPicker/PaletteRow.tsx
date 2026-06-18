import ColorSwatch from "./ColorSwatch"

interface Props {
  label: string
  colors: string[]
  onSelect(color: string): void
  selectedColor?: string
}

export default function PaletteRow({ label, colors, onSelect, selectedColor }: Props) {
  return (
    <div className="mb-3">
      <div className="text-xs text-neutral-500 mb-1"><span>{label}</span>:</div>
      {colors.length === 0 ? (
        <span className="text-xs text-neutral-600 italic">sin recientes</span>
      ) : (
        <div className="flex gap-1.5 flex-wrap">
          {colors.map((color) => (
            <ColorSwatch
              key={color}
              color={color}
              onSelect={onSelect}
              isSelected={color === selectedColor}
            />
          ))}
        </div>
      )}
    </div>
  )
}
