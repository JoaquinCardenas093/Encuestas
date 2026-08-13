import { useState } from "react"
import { DndContext, closestCenter, DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core"
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { Plus, X } from "lucide-react"
import { useProjectStore } from "../../store/project"
import AddSeparatorModal from "./modals/AddSeparatorModal"

interface Props {
  selectedId: string | null
  onSelect(id: string): void
  onDelete(id: string): void
}

export default function SlideRail({ selectedId, onSelect, onDelete }: Props) {
  const slides = useProjectStore((s) => s.state?.slides ?? [])
  const addSeparator = useProjectStore((s) => s.addSeparator)
  const addShell = useProjectStore((s) => s.addShell)
  const reorderSlide = useProjectStore((s) => s.reorderSlide)
  const [sepOpen, setSepOpen] = useState(false)

  const hasSeparator = slides.some((s) => s.type === "separator")
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  function handleDragEnd(ev: DragEndEvent) {
    const { active, over } = ev
    if (over && active.id !== over.id) {
      const fromIdx = slides.findIndex((s) => s.id === active.id)
      const toIdx = slides.findIndex((s) => s.id === over.id)
      reorderSlide(fromIdx, toIdx)
    }
  }

  return (
    <aside className="bg-neutral-900 border-r border-neutral-700 p-2 flex flex-col gap-1 overflow-y-auto">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={slides.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {slides.map((slide, idx) => (
            <SortableThumb
              key={slide.id}
              slide={slide}
              index={idx}
              selected={selectedId === slide.id}
              onClick={() => onSelect(slide.id)}
              onDelete={() => onDelete(slide.id)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <div className="mt-auto flex flex-col gap-1 pt-2">
        <button
          onClick={() => setSepOpen(true)}
          className="text-xs bg-neutral-800 hover:bg-neutral-700 border border-dashed border-neutral-600 py-1.5 rounded flex items-center justify-center gap-1"
        >
          <Plus size={12} /> Separador
        </button>
        <button
          disabled={!hasSeparator}
          onClick={() => addShell()}
          className="text-xs bg-neutral-800 hover:bg-neutral-700 border border-dashed border-neutral-600 py-1.5 rounded flex items-center justify-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
          title={hasSeparator ? "" : "Agregá un separador primero"}
        >
          <Plus size={12} /> Slide
        </button>
      </div>

      <AddSeparatorModal
        open={sepOpen}
        onClose={() => setSepOpen(false)}
        onCreate={(t) => addSeparator(t)}
      />
    </aside>
  )
}

function SortableThumb({
  slide,
  index,
  selected,
  onClick,
  onDelete,
}: {
  slide: any
  index: number
  selected: boolean
  onClick(): void
  onDelete(): void
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: slide.id })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const isSep = slide.type === "separator"
  return (
    <div
      ref={setNodeRef}
      data-testid={`thumb-${slide.id}`}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`group relative aspect-[16/9] bg-white rounded cursor-pointer border-2 ${selected ? "border-amber-400" : isSep ? "border-accent" : "border-transparent"} ${isSep ? "bg-neutral-200" : ""}`}
    >
      <button
        data-testid={`delete-slide-${slide.id}`}
        aria-label="eliminar slide"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          if (window.confirm("¿Eliminar esta slide?")) onDelete()
        }}
        className="absolute -top-2 -right-2 z-10 bg-neutral-800 hover:bg-red-700 text-neutral-300 hover:text-white rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X size={10} />
      </button>
      <span className="absolute -top-2 -left-2 bg-neutral-800 text-accent text-[10px] px-1.5 rounded">
        {index + 1}
      </span>
      <span className="absolute inset-0 flex items-center justify-center text-[8px] text-neutral-500 px-1 text-center">
        {isSep ? `▸ ${slide.title || ""}` : slide.title || "sin título"}
      </span>
    </div>
  )
}
