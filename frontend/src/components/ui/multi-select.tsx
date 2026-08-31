import * as React from "react"
import * as PopoverPrimitive from "@radix-ui/react-popover"
import { Check, ChevronsUpDown, X } from "lucide-react"
import { cn } from "../../lib/utils"
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "./command"

type MultiSelectProps = {
  label: string
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  max?: number
}

export function MultiSelect({ label, options, value, onChange, max = 3 }: MultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const toggle = (option: string) => {
    if (value.includes(option)) onChange(value.filter((item) => item !== option))
    else if (value.length < max) onChange([...value, option])
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-zinc-700">{label}</label>
        <span className="text-[10px] text-zinc-400">{value.length}/{max}</span>
      </div>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
        <PopoverPrimitive.Trigger asChild>
          <button className="flex min-h-11 w-full items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-left text-sm shadow-sm outline-none hover:border-zinc-300 focus-visible:ring-2 focus-visible:ring-violet-500/25">
            <span className="flex min-w-0 flex-1 flex-wrap gap-1.5">
              {value.length ? value.map((item) => (
                <span key={item} className="inline-flex h-6 items-center gap-1 rounded-md bg-violet-50 px-2 text-[11px] font-medium text-violet-700">
                  {item}
                  <span role="button" aria-label={`移除${item}`} onClick={(event) => { event.stopPropagation(); toggle(item) }}><X className="size-3" /></span>
                </span>
              )) : <span className="text-zinc-400">选择或搜索…</span>}
            </span>
            <ChevronsUpDown className="size-4 text-zinc-400" />
          </button>
        </PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content sideOffset={6} align="start" className="z-[70] w-[var(--radix-popover-trigger-width)] rounded-xl border border-zinc-200 bg-white p-0 shadow-xl outline-none">
            <Command>
              <CommandInput placeholder={`搜索${label}`} />
              <CommandList>
                <CommandEmpty>没有匹配选项</CommandEmpty>
                {options.map((option) => {
                  const selected = value.includes(option)
                  const disabled = !selected && value.length >= max
                  return <CommandItem key={option} disabled={disabled} onSelect={() => toggle(option)} className={cn(disabled && "opacity-40")}>
                    <span className={cn("grid size-4 place-items-center rounded border", selected ? "border-violet-600 bg-violet-600 text-white" : "border-zinc-300")}>
                      {selected && <Check className="size-3" />}
                    </span>
                    {option}
                  </CommandItem>
                })}
              </CommandList>
            </Command>
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
    </div>
  )
}
