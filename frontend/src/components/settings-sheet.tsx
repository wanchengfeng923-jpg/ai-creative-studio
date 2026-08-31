import { ImagePlus, Info, Sparkles } from "lucide-react"
import { displayOptions, sellingPointOptions, styleOptions } from "../data"
import type { StudioState } from "../app"
import { Button } from "./ui/button"
import { MultiSelect } from "./ui/multi-select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./ui/sheet"

type Props = {
  state: StudioState
  patch: (value: Partial<StudioState>) => void
}

export function SettingsSheet({ state, patch }: Props) {
  return (
    <Sheet open={state.settingsOpen} onOpenChange={(settingsOpen) => patch({ settingsOpen })}>
      <SheetContent>
        <SheetHeader>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-violet-600">
            <Sparkles className="size-3.5" /> Creative brief
          </div>
          <SheetTitle>本轮创意配置</SheetTitle>
          <SheetDescription>只保留会显著改变生成方向的控制项，其他参数交给系统。</SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-zinc-700">任务目标</label>
            <textarea
              className="min-h-28 w-full resize-none rounded-xl border border-zinc-200 bg-white px-3.5 py-3 text-sm leading-6 text-zinc-900 shadow-sm outline-none placeholder:text-zinc-400 focus:border-violet-400 focus:ring-4 focus:ring-violet-500/10"
              value={state.goal}
              onChange={(event) => patch({ goal: event.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="创意模式">
              <select value={state.mode} onChange={(event) => patch({ mode: event.target.value as StudioState["mode"] })} className="field-select">
                <option>展示类</option>
                <option>叙事类</option>
              </select>
            </Field>
            <Field label="画幅">
              <select value={state.ratio} onChange={(event) => patch({ ratio: event.target.value as StudioState["ratio"] })} className="field-select">
                <option>16:9</option>
                <option>4:5</option>
                <option>1:1</option>
              </select>
            </Field>
          </div>

          <MultiSelect label="核心卖点" options={sellingPointOptions} value={state.sellingPoints} onChange={(sellingPoints) => patch({ sellingPoints })} />
          <MultiSelect label="展示内容" options={displayOptions} value={state.displays} onChange={(displays) => patch({ displays })} />
          <MultiSelect label="视觉风格" options={styleOptions} value={state.styles} onChange={(styles) => patch({ styles })} />

          <button className="group flex w-full items-center gap-3 rounded-xl border border-dashed border-zinc-300 bg-zinc-50 p-4 text-left transition hover:border-violet-300 hover:bg-violet-50/50">
            <span className="grid size-10 place-items-center rounded-lg bg-white text-zinc-500 shadow-sm group-hover:text-violet-600"><ImagePlus className="size-4" /></span>
            <span>
              <span className="block text-sm font-medium text-zinc-800">添加视觉参考</span>
              <span className="mt-0.5 block text-xs text-zinc-400">PNG / JPG，最多 4 张</span>
            </span>
          </button>

          <div className="flex gap-2.5 rounded-xl bg-blue-50 p-3 text-xs leading-5 text-blue-700">
            <Info className="mt-0.5 size-4 shrink-0" />
            原型只保存当前页面状态，不会上传文件或调用真实模型。
          </div>
        </div>

        <div className="flex gap-3 border-t border-zinc-200 px-6 py-4">
          <Button variant="secondary" className="flex-1" onClick={() => patch({ settingsOpen: false })}>取消</Button>
          <Button className="flex-1" onClick={() => patch({ settingsOpen: false, notice: "创意配置已更新" })}>应用配置</Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="space-y-2"><span className="block text-xs font-semibold text-zinc-700">{label}</span>{children}</label>
}
