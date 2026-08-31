import { Archive, ChevronDown, CirclePlus, Clock3, Command, FolderKanban, History, LayoutGrid, MoreHorizontal, PanelLeftClose, Settings2, Sparkles, WandSparkles } from "lucide-react"
import type { VariantProps } from "../app"
import { concepts, projects } from "../data"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

export function SessionFeed({ state, patch, project, onGenerate, showNotice }: VariantProps) {
  const newest = concepts.filter((concept) => concept.batch === 2)
  const previous = concepts.filter((concept) => concept.batch === 1)

  return (
    <div className="session-shell">
      <aside className="session-sidebar">
        <div className="flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <div className="brand-mark"><Sparkles className="size-4" /></div>
            <div><strong className="block text-sm tracking-tight text-zinc-950">Creative Studio</strong><span className="block text-[10px] text-zinc-400">AI 创意工作台</span></div>
          </div>
          <button className="icon-button"><PanelLeftClose className="size-4" /></button>
        </div>

        <div className="px-3 py-2">
          <Button className="w-full justify-start" onClick={() => showNotice("已创建空白创意会话（原型演示）")}><CirclePlus className="size-4" />新建创意</Button>
        </div>

        <nav className="space-y-1 px-3 py-3 text-sm">
          <a className="side-link active" href="#workspace"><WandSparkles className="size-4" />创意工作区</a>
          <a className="side-link" href="#projects"><FolderKanban className="size-4" />全部项目<span className="ml-auto text-xs text-zinc-400">12</span></a>
          <a className="side-link" href="#library"><LayoutGrid className="size-4" />素材库</a>
          <a className="side-link" href="#history"><History className="size-4" />生成记录</a>
        </nav>

        <div className="mt-1 flex items-center justify-between px-5 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-400">最近项目</span>
          <MoreHorizontal className="size-4 text-zinc-400" />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3">
          {projects.slice(0, 4).map((item) => (
            <button key={item.id} onClick={() => patch({ projectId: item.id, mode: item.type })} className={cn("project-link", item.id === state.projectId && "active")}>
              <span className="project-thumb" />
              <span className="min-w-0 flex-1"><strong>{item.name}</strong><small>{item.updated} · {item.status}</small></span>
            </button>
          ))}
        </div>

        <div className="border-t border-zinc-200 p-3">
          <button className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-zinc-100">
            <span className="grid size-8 place-items-center rounded-full bg-zinc-950 text-xs font-semibold text-white">创</span>
            <span className="min-w-0 flex-1"><strong className="block text-xs text-zinc-800">本地创意空间</strong><small className="text-[10px] text-zinc-400">仅当前设备</small></span>
            <ChevronDown className="size-4 text-zinc-400" />
          </button>
        </div>
      </aside>

      <main className="session-main" id="workspace">
        <header className="session-header">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2 text-xs text-zinc-400"><span>创意工作区</span><span>/</span><span className="truncate">{project.name}</span></div>
            <div className="flex items-center gap-3"><h1>{project.name}</h1><Badge variant="neutral">{state.mode}</Badge></div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => showNotice("项目已归档（原型演示）")}><Archive className="size-3.5" />归档</Button>
            <Button variant="ghost" size="iconSm"><MoreHorizontal className="size-4" /></Button>
          </div>
        </header>

        <div className="session-scroll">
          <section className="brief-note">
            <div className="brief-note__icon"><Command className="size-4" /></div>
            <div className="min-w-0 flex-1"><div className="mb-1 flex items-center gap-2"><strong>本轮目标</strong><span>今天 14:32</span></div><p>{state.goal}</p></div>
            <Button variant="ghost" size="sm" onClick={() => patch({ settingsOpen: true })}>编辑</Button>
          </section>

          <BatchHeader batch="02" title="强化版本首曝的视觉冲击" subtitle="基于上一轮反馈，提高人物尺度和实机证据" current />
          <div className="concept-triptych">
            {newest.map((concept, index) => (
              <article key={concept.id} className={cn("feed-concept-card", state.selectedConceptId === concept.id && "selected")} onClick={() => patch({ selectedConceptId: concept.id })}>
                <div className="feed-concept-card__image">
                  <img src={concept.image} alt={concept.title} />
                  <div className="image-shade" />
                  <span className="concept-index">0{index + 1}</span>
                  <span className="concept-score">匹配 {concept.score}%</span>
                </div>
                <div className="p-4">
                  <div className="mb-2 flex items-start justify-between gap-3"><div><span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.15em] text-violet-600">{concept.strategy}</span><h3>{concept.title}</h3></div><button className="icon-button shrink-0"><MoreHorizontal className="size-4" /></button></div>
                  <p className="line-clamp-2 text-xs leading-5 text-zinc-500">{concept.summary}</p>
                  <div className="mt-4 flex flex-wrap gap-1.5">{concept.tags.slice(0, 2).map((tag) => <Badge key={tag} variant="neutral">{tag}</Badge>)}</div>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <Button variant="secondary" size="sm" onClick={(event) => { event.stopPropagation(); showNotice(`已打开「${concept.title}」详情`) }}>查看详情</Button>
                    <Button size="sm" onClick={(event) => { event.stopPropagation(); patch({ adoptedConceptId: concept.id, notice: `已采用「${concept.title}」` }) }}>{state.adoptedConceptId === concept.id ? "已采用" : "采用方向"}</Button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="batch-divider"><span>上一轮 · 14:18</span></div>
          <BatchHeader batch="01" title="建立新职业的第一印象" subtitle="初始探索 · 3 个不同创意策略" />
          <div className="previous-row">
            {previous.map((concept) => (
              <button key={concept.id} className="previous-card" onClick={() => patch({ selectedConceptId: concept.id })}>
                <img src={concept.image} alt="" />
                <span><strong>{concept.title}</strong><small>{concept.strategy} · {concept.score}%</small></span>
              </button>
            ))}
          </div>
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <div className="composer__top">
              <textarea value={state.goal} onChange={(event) => patch({ goal: event.target.value })} aria-label="本轮生成目标" />
              <Button size="icon" onClick={onGenerate} disabled={state.generating}><Sparkles className={cn("size-4", state.generating && "animate-spin")} /></Button>
            </div>
            <div className="composer__bottom">
              <button onClick={() => patch({ mode: state.mode === "展示类" ? "叙事类" : "展示类" })}>{state.mode}<ChevronDown className="size-3" /></button>
              <button onClick={() => patch({ ratio: state.ratio === "16:9" ? "4:5" : state.ratio === "4:5" ? "1:1" : "16:9" })}>{state.ratio}</button>
              <span className="h-4 w-px bg-zinc-200" />
              <span>{state.sellingPoints.length} 个卖点 · {state.styles.length} 种风格</span>
              <button className="ml-auto" onClick={() => patch({ settingsOpen: true })}><Settings2 className="size-3.5" />完整配置</button>
            </div>
          </div>
          <div className="mt-2 flex justify-center gap-1 text-[10px] text-zinc-400"><Clock3 className="size-3" />原型不会触发真实生成</div>
        </div>
      </main>
    </div>
  )
}

function BatchHeader({ batch, title, subtitle, current = false }: { batch: string; title: string; subtitle: string; current?: boolean }) {
  return <div className="batch-header"><span className="batch-number">{batch}</span><div><div className="flex items-center gap-2"><h2>{title}</h2>{current && <Badge variant="success">最新</Badge>}</div><p>{subtitle}</p></div></div>
}
