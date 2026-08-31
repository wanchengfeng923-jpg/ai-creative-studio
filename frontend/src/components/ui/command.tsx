import * as React from "react"
import { Command as CommandPrimitive } from "cmdk"
import { Search } from "lucide-react"
import { cn } from "../../lib/utils"

export const Command = React.forwardRef<React.ElementRef<typeof CommandPrimitive>, React.ComponentPropsWithoutRef<typeof CommandPrimitive>>(
  ({ className, ...props }, ref) => <CommandPrimitive ref={ref} className={cn("flex w-full flex-col overflow-hidden rounded-xl bg-white", className)} {...props} />,
)
Command.displayName = "Command"

export const CommandInput = React.forwardRef<React.ElementRef<typeof CommandPrimitive.Input>, React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>>(
  ({ className, ...props }, ref) => (
    <div className="flex h-11 items-center gap-2 border-b border-zinc-200 px-3">
      <Search className="size-4 text-zinc-400" />
      <CommandPrimitive.Input ref={ref} className={cn("h-full w-full bg-transparent text-sm outline-none placeholder:text-zinc-400", className)} {...props} />
    </div>
  ),
)
CommandInput.displayName = "CommandInput"

export const CommandList = React.forwardRef<React.ElementRef<typeof CommandPrimitive.List>, React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>>(
  ({ className, ...props }, ref) => <CommandPrimitive.List ref={ref} className={cn("max-h-72 overflow-y-auto overflow-x-hidden p-1", className)} {...props} />,
)
CommandList.displayName = "CommandList"

export const CommandEmpty = React.forwardRef<React.ElementRef<typeof CommandPrimitive.Empty>, React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>>(
  (props, ref) => <CommandPrimitive.Empty ref={ref} className="py-8 text-center text-sm text-zinc-500" {...props} />,
)
CommandEmpty.displayName = "CommandEmpty"

export const CommandGroup = React.forwardRef<React.ElementRef<typeof CommandPrimitive.Group>, React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>>(
  ({ className, ...props }, ref) => <CommandPrimitive.Group ref={ref} className={cn("overflow-hidden p-1 text-zinc-950 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-zinc-400", className)} {...props} />,
)
CommandGroup.displayName = "CommandGroup"

export const CommandItem = React.forwardRef<React.ElementRef<typeof CommandPrimitive.Item>, React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>>(
  ({ className, ...props }, ref) => <CommandPrimitive.Item ref={ref} className={cn("relative flex cursor-default select-none items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none data-[selected=true]:bg-violet-50 data-[selected=true]:text-violet-800", className)} {...props} />,
)
CommandItem.displayName = "CommandItem"
