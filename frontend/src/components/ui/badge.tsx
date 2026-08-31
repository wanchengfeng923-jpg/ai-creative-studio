import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva(
  "inline-flex h-6 items-center rounded-md border px-2 text-[11px] font-medium",
  {
    variants: {
      variant: {
        default: "border-violet-200 bg-violet-50 text-violet-700",
        neutral: "border-zinc-200 bg-zinc-50 text-zinc-600",
        success: "border-emerald-200 bg-emerald-50 text-emerald-700",
        dark: "border-white/10 bg-white/8 text-zinc-200",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
