import { useEffect, useMemo, useState } from "react"
import { concepts, projects } from "./data"
import { SettingsSheet } from "./components/settings-sheet"
import { PrototypeSwitcher, type VariantKey } from "./components/prototype-switcher"
import { SessionFeed } from "./variants/session-feed"
import { LibraryReview } from "./variants/library-review"
import { FocusCompare } from "./variants/focus-compare"

export type StudioState = {
  projectId: number
  selectedConceptId: number
  adoptedConceptId: number | null
  mode: "展示类" | "叙事类"
  ratio: "16:9" | "4:5" | "1:1"
  goal: string
  sellingPoints: string[]
  displays: string[]
  styles: string[]
  settingsOpen: boolean
  generating: boolean
  notice: string | null
}

function readVariant(): VariantKey {
  const value = new URLSearchParams(window.location.search).get("variant")?.toUpperCase()
  return value === "B" || value === "C" ? value : "A"
}

export function App() {
  const [variant, setVariantState] = useState<VariantKey>(readVariant)
  const [state, setState] = useState<StudioState>({
    projectId: 1,
    selectedConceptId: 1,
    adoptedConceptId: null,
    mode: "展示类",
    ratio: "16:9",
    goal: "突出新职业的压迫感和版本内容量，画面要有一眼能懂的强冲突。",
    sellingPoints: ["新职业登场", "门派对抗"],
    displays: ["职业技能", "门派群像"],
    styles: ["东方奇观", "电影感"],
    settingsOpen: false,
    generating: false,
    notice: null,
  })

  const patch = (value: Partial<StudioState>) => setState((current) => ({ ...current, ...value }))
  const currentProject = useMemo(() => projects.find((project) => project.id === state.projectId) ?? projects[0], [state.projectId])
  const selectedConcept = useMemo(() => concepts.find((concept) => concept.id === state.selectedConceptId) ?? concepts[0], [state.selectedConceptId])

  const setVariant = (next: VariantKey) => {
    const url = new URL(window.location.href)
    url.searchParams.set("variant", next)
    window.history.replaceState({}, "", url)
    setVariantState(next)
  }

  const showNotice = (notice: string) => {
    patch({ notice })
    window.setTimeout(() => setState((current) => ({ ...current, notice: null })), 2400)
  }

  const generate = () => {
    patch({ generating: true, notice: "正在模拟生成 3 个新方向…" })
    window.setTimeout(() => patch({ generating: false, notice: "新一轮方案已加入会话（原型演示）" }), 1400)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable) return
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return
      const order: VariantKey[] = ["A", "B", "C"]
      const offset = event.key === "ArrowRight" ? 1 : -1
      setVariant(order[(order.indexOf(variant) + offset + order.length) % order.length])
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [variant])

  const props = {
    state,
    patch,
    project: currentProject,
    selectedConcept,
    onGenerate: generate,
    showNotice,
  }

  return (
    <div className={variant === "C" ? "theme-dark" : "theme-light"}>
      {variant === "A" && <SessionFeed {...props} />}
      {variant === "B" && <LibraryReview {...props} />}
      {variant === "C" && <FocusCompare {...props} />}

      <SettingsSheet state={state} patch={patch} />
      <PrototypeSwitcher variant={variant} setVariant={setVariant} state={state} />

      {state.notice && (
        <div className="prototype-toast" role="status">
          <span className="size-2 rounded-full bg-violet-500" />
          {state.notice}
        </div>
      )}
    </div>
  )
}

export type VariantProps = {
  state: StudioState
  patch: (value: Partial<StudioState>) => void
  project: (typeof projects)[number]
  selectedConcept: (typeof concepts)[number]
  onGenerate: () => void
  showNotice: (notice: string) => void
}
