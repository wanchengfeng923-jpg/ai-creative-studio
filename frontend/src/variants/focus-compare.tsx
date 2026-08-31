import { ArrowLeft, Check, ChevronDown, Columns3, Maximize2, MessageSquareText, MoreHorizontal, RotateCcw, Settings2, Sparkles } from "lucide-react"
import type { VariantProps } from "../app"
import { concepts } from "../data"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

export function FocusCompare({ state, patch, project, onGenerate, showNotice }: VariantProps) {
  const items = concepts.filter((concept) => concept.batch === 2)
  return (
    <div className="focus-shell">
      <header className="focus-header">
        <div className="flex items-center gap-3"><button className="dark-icon-button"><ArrowLeft className="size-4" /></button><span className="h-5 w-px bg-white/10" /><div><span className="block text-[10px] uppercase tracking-[0.15em] text-zinc-500">Compare batch 02</span><button className="mt-0.5 flex items-center gap-2 text-sm font-medium text-white">{project.name}<ChevronDown className="size-3.5 text-zinc-500" /></button></div></div>
        <div className="focus-progress"><span className="active" /><span /><span /><small>选择一个方向</small></div>
        <div className="flex items-center gap-2"><Button variant="outlineDark" size="sm" onClick={() => showNotice("已重置本轮选择")}><RotateCcw className="size-3.5" />重置</Button><button className="dark-icon-button"><MoreHorizontal className="size-4" /></button></div>
      </header>

      <main className="focus-main">
        <div className="focus-intro"><div><span className="focus-kicker"><Columns3 className="size-3.5" />三向对比</span><h1>哪一个最像这次版本的“第一眼”？</h1></div><p>同一目标、三种策略。先凭直觉选择，再查看创意依据。</p></div>
        <div className="compare-grid">
          {items.map((concept, index) => {
            const selected = state.selectedConceptId === concept.id
            const adopted = state.adoptedConceptId === concept.id
            return (
              <article key={concept.id} className={cn("compare-card", selected && "selected", adopted && "adopted")} onClick={() => patch({ selectedConceptId: concept.id })}>
                <div className="compare-card__image"><img src={concept.image} alt={concept.title} /><div className="focus-gradient" /><span className="compare-letter">{String.fromCharCode(65 + index)}</span><button className="expand-button" onClick={(event) => { event.stopPropagation(); showNotice(`已全屏预览「${concept.title}」`) }}><Maximize2 className="size-4" /></button>{selected && <span className="selected-pill"><Check className="size-3" />当前选择</span>}</div>
                <div className="compare-card__content">
                  <div className="flex items-start justify-between"><div><span className="focus-kicker">{concept.strategy}</span><h2>{concept.title}</h2></div><div className="score-ring"><strong>{concept.score}</strong><small>match</small></div></div>
                  <p>{concept.summary}</p>
                  <div className="compare-tags">{concept.tags.map((tag) => <Badge key={tag} variant="dark">{tag}</Badge>)}</div>
                  <div className="compare-bars"><Metric label="视觉冲击" value={concept.id === 1 ? 96 : concept.id === 2 ? 82 : 78} /><Metric label="信息承载" value={concept.id === 1 ? 84 : concept.id === 2 ? 94 : 90} /><Metric label="实机可信" value={concept.id === 1 ? 78 : concept.id === 2 ? 74 : 96} /></div>
                  <Button variant={adopted ? "dark" : "outlineDark"} className="mt-auto w-full" onClick={(event) => { event.stopPropagation(); patch({ selectedConceptId: concept.id, adoptedConceptId: concept.id, notice: `已采用「${concept.title}」` }) }}>{adopted ? <><Check className="size-4" />已采用此方向</> : "选择此方向"}</Button>
                </div>
              </article>
            )
          })}
        </div>
      </main>

      <div className="focus-composer">
        <div className="focus-composer__text"><MessageSquareText className="size-4 text-zinc-500" /><input value={state.goal} onChange={(event) => patch({ goal: event.target.value })} aria-label="补充下一轮要求" /></div>
        <span className="h-5 w-px bg-white/10" />
        <button onClick={() => patch({ settingsOpen: true })}><Settings2 className="size-4" />{state.mode} · {state.ratio}</button>
        <Button variant="dark" onClick={onGenerate} disabled={state.generating}><Sparkles className={cn("size-4", state.generating && "animate-spin")} />基于选择继续生成</Button>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><div><span>{label}</span><strong>{value}</strong></div><span><i style={{ width: `${value}%` }} /></span></div>
}
