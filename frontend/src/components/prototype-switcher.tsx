import { ChevronLeft, ChevronRight, FlaskConical } from "lucide-react"
import type { StudioState } from "../app"

export type VariantKey = "A" | "B" | "C"
const labels: Record<VariantKey, string> = { A: "会话流", B: "素材审阅", C: "专注对比" }

export function PrototypeSwitcher({ variant, setVariant, state }: { variant: VariantKey; setVariant: (variant: VariantKey) => void; state: StudioState }) {
  const order: VariantKey[] = ["A", "B", "C"]
  const index = order.indexOf(variant)
  const move = (offset: number) => setVariant(order[(index + offset + order.length) % order.length])
  return (
    <aside className="prototype-switcher" aria-label="原型方案切换器">
      <button onClick={() => move(-1)} aria-label="上一个方案"><ChevronLeft className="size-4" /></button>
      <div className="prototype-switcher__label">
        <span><FlaskConical className="size-3.5" /> 原型 {variant}</span>
        <strong>{labels[variant]}</strong>
      </div>
      <div className="prototype-switcher__dots">
        {order.map((key) => <button key={key} className={key === variant ? "active" : ""} onClick={() => setVariant(key)} aria-label={`切换到${labels[key]}`} />)}
      </div>
      <button onClick={() => move(1)} aria-label="下一个方案"><ChevronRight className="size-4" /></button>
      <div className="prototype-state">项目 {state.projectId} · 方案 {state.selectedConceptId} · {state.ratio} · {state.adoptedConceptId ? `已采用 ${state.adoptedConceptId}` : "未采用"}</div>
    </aside>
  )
}
