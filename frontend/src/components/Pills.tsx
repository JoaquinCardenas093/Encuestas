interface PillProps {
  label: string
  value: string
  ok?: boolean
}

export function Pill({ label, value, ok }: PillProps) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-neutral-900 border border-neutral-700 text-neutral-400">
      {label}: <span className={ok ? "text-green-400" : "text-neutral-300"}>{value}</span>
    </span>
  )
}
