import * as React from "react"
import * as SheetPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { cn } from "../../lib/utils"

export const Sheet = SheetPrimitive.Root
export const SheetTrigger = SheetPrimitive.Trigger
export const SheetClose = SheetPrimitive.Close

export function SheetContent({ className, children, ...props }: React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content>) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-zinc-950/30 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=closed]:animate-out" />
      <SheetPrimitive.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-[420px] flex-col border-l border-zinc-200 bg-white shadow-2xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out",
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="absolute right-4 top-4 grid size-9 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 focus-visible:ring-2 focus-visible:ring-violet-500/35">
          <X className="size-4" />
          <span className="sr-only">关闭</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  )
}

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-zinc-200 px-6 py-5", className)} {...props} />
}

export function SheetTitle({ className, ...props }: React.ComponentPropsWithoutRef<typeof SheetPrimitive.Title>) {
  return <SheetPrimitive.Title className={cn("text-lg font-semibold tracking-tight text-zinc-950", className)} {...props} />
}

export function SheetDescription({ className, ...props }: React.ComponentPropsWithoutRef<typeof SheetPrimitive.Description>) {
  return <SheetPrimitive.Description className={cn("mt-1 text-sm leading-5 text-zinc-500", className)} {...props} />
}
