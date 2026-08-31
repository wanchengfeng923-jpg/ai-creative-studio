import { useState } from "react"
import { ArrowLeft, Check, ChevronDown, Columns3, Grid2X2, Images, ListFilter, MoreHorizontal, Search, Settings2, SlidersHorizontal, Sparkles, Star } from "lucide-react"
import type { VariantProps } from "../app"
import { concepts, projects } from "../data"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

export function LibraryReview({ state, patch, project, selectedConcept, showNotice }: VariantProps) {
  const [selectedTileId, setSelectedTileId] = useState(state.selectedConceptId)
  const visualConcepts = [...concepts, ...concepts.slice(0, 3).map((concept, index) => ({ ...concept, id: concept.id + 10, title: ["风起名门", "万剑归宗", "踏月赴约"][index], score: concept.score - 7 }))]
  return (
    <div className="library-shell">
      <header className="library-topbar">
        <div className="flex items-center gap-3"><div className="brand-mark"><Sparkles className="size-4" /></div><strong className="text-sm">Creative Studio</strong><span className="h-5 w-px bg-zinc-200" /><button className="flex items-center gap-2 text-sm text-zinc-600"><span className="max-w-60 truncate">{project.name}</span><ChevronDown className="size-3.5" /></button></div>
        <div className="library-search"><Search className="size-4" /><input placeholder="搜索标题、策略或标签" /><kbd>⌘ K</kbd></div>
        <div className="flex items-center gap-2"><Button variant="secondary" size="sm" onClick={() => patch({ settingsOpen: true })}><Settings2 className="size-3.5" />创意配置</Button><Button size="sm" onClick={() => showNotice("已进入新一轮生成（原型演示）")}><Sparkles className="size-3.5" />继续生成</Button></div>
      </header>

      <div className="library-body">
        <aside className="collections-panel">
          <button className="mb-5 flex items-center gap-2 text-xs font-medium text-zinc-500 hover:text-zinc-900"><ArrowLeft className="size-3.5" />返回项目</button>
          <div className="mb-2 flex items-center justify-between px-2"><span className="panel-kicker">Collections</span><MoreHorizontal className="size-4 text-zinc-400" /></div>
          <nav className="space-y-1">
            <button className="collection-link active"><Images className="size-4" />全部素材<span>9</span></button>
            <button className="collection-link"><Star className="size-4" />已收藏<span>3</span></button>
            <button className="collection-link"><Check className="size-4" />已采用<span>{state.adoptedConceptId ? 1 : 0}</span></button>
          </nav>
          <div className="my-5 h-px bg-zinc-200" />
          <div className="mb-2 px-2"><span className="panel-kicker">Projects</span></div>
          <nav className="space-y-1">
            {projects.slice(0, 4).map((item) => <button key={item.id} className={cn("collection-link text-left", item.id === state.projectId && "active")} onClick={() => patch({ projectId: item.id, mode: item.type })}><span className="size-2 rounded-full bg-violet-400" /><span className="min-w-0 flex-1 truncate">{item.name}</span><span>{item.id === 1 ? 9 : 4}</span></button>)}
          </nav>
          <div className="collection-stat"><span>本月生成额度</span><strong>68 / 100</strong><div><i /></div></div>
        </aside>

        <main className="library-canvas">
          <div className="library-heading">
            <div><span className="panel-kicker">Creative library</span><h1>全部创意素材</h1><p>9 个方向，按最新生成排序</p></div>
            <div className="flex items-center gap-2"><button className="filter-button"><ListFilter className="size-3.5" />所有批次<ChevronDown className="size-3" /></button><button className="filter-button"><SlidersHorizontal className="size-3.5" />筛选</button><div className="view-toggle"><button className="active"><Grid2X2 className="size-3.5" /></button><button><Columns3 className="size-3.5" /></button></div></div>
          </div>
          <div className="library-grid">
            {visualConcepts.map((concept, index) => (
              <button key={concept.id} className={cn("library-tile", selectedTileId === concept.id && "selected", index % 4 === 1 && "tall")} onClick={() => { setSelectedTileId(concept.id); patch({ selectedConceptId: concept.id > 6 ? concept.id - 10 : concept.id }) }}>
                <img src={concept.image} alt={concept.title} />
                <span className="library-tile__top"><Badge variant="dark">BATCH {concept.batch.toString().padStart(2, "0")}</Badge><span className="tile-score">{concept.score}</span></span>
                <span className="library-tile__meta"><small>{concept.strategy}</small><strong>{concept.title}</strong><span>{concept.tags.slice(0, 2).join(" · ")}</span></span>
                {selectedTileId === concept.id && <span className="tile-check"><Check className="size-4" /></span>}
              </button>
            ))}
          </div>
        </main>

        <aside className="inspector-panel">
          <div className="inspector-hero"><img src={selectedConcept.image} alt={selectedConcept.title} /><div className="image-shade" /><span className="concept-score">匹配 {selectedConcept.score}%</span></div>
          <div className="inspector-content">
            <div className="flex items-start justify-between gap-3"><div><span className="panel-kicker text-violet-600">{selectedConcept.strategy}</span><h2>{selectedConcept.title}</h2></div><button className="icon-button"><MoreHorizontal className="size-4" /></button></div>
            <p>{selectedConcept.summary}</p>
            <div className="flex flex-wrap gap-1.5">{selectedConcept.tags.map((tag) => <Badge key={tag} variant="neutral">{tag}</Badge>)}</div>
            <dl className="inspector-list"><div><dt>生成批次</dt><dd>第 {selectedConcept.batch} 轮</dd></div><div><dt>创意模式</dt><dd>{state.mode}</dd></div><div><dt>画面比例</dt><dd>{state.ratio}</dd></div><div><dt>生成时间</dt><dd>今天 14:32</dd></div></dl>
            <div className="inspector-rationale"><strong>为什么值得采用</strong><p>视觉焦点清楚，首屏能同时传达角色力量与版本规模，适合作为首曝主画面。</p></div>
          </div>
          <div className="mt-auto grid grid-cols-2 gap-2 border-t border-zinc-200 p-4"><Button variant="secondary" onClick={() => showNotice(`已收藏「${selectedConcept.title}」`)}><Star className="size-4" />收藏</Button><Button onClick={() => patch({ adoptedConceptId: selectedConcept.id, notice: `已采用「${selectedConcept.title}」` })}>{state.adoptedConceptId === selectedConcept.id ? <><Check className="size-4" />已采用</> : "采用方向"}</Button></div>
        </aside>
      </div>
    </div>
  )
}
