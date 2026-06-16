import { ReactNode, useEffect } from "react"
import { X } from "lucide-react"

interface ModalProps {
  open: boolean
  onClose(): void
  title: string
  children: ReactNode
  footer?: ReactNode
  maxWidth?: string
}

export default function Modal({ open, onClose, title, children, footer, maxWidth = "max-w-lg" }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className={`bg-neutral-800 rounded-lg shadow-xl border border-neutral-700 w-full ${maxWidth} mx-4`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-3 border-b border-neutral-700">
          <h3 className="text-sm font-semibold text-neutral-100">{title}</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X size={16} />
          </button>
        </header>
        <div className="p-5">{children}</div>
        {footer && <footer className="px-5 py-3 border-t border-neutral-700 flex justify-end gap-2">{footer}</footer>}
      </div>
    </div>
  )
}
