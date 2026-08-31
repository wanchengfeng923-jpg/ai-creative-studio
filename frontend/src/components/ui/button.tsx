import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all outline-none disabled:pointer-events-none disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-violet-500/35 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-violet-600 text-white shadow-sm hover:bg-violet-700 hover:shadow-md",
        secondary: "border border-zinc-200 bg-white text-zinc-800 shadow-sm hover:bg-zinc-50",
        ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950",
        dark: "bg-white text-zinc-950 hover:bg-zinc-100",
        outlineDark: "border border-white/15 bg-white/5 text-white hover:bg-white/10",
        destructive: "bg-red-600 text-white hover:bg-red-700",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 px-5",
        icon: "size-10 p-0",
        iconSm: "size-8 rounded-md p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button"
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />
}

export { buttonVariants }
