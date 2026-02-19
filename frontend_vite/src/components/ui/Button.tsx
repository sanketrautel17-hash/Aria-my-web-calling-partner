// ── components/ui/Button.tsx ──────────────────────────────────────────────
import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
    'inline-flex items-center justify-center gap-2 rounded-xl font-medium text-sm transition-all duration-200 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed select-none',
    {
        variants: {
            variant: {
                primary: 'bg-[#7c3aed] text-white hover:bg-[#6d28d9] hover:shadow-[0_0_20px_rgba(124,58,237,0.35)]',
                danger: 'bg-[#ef4444] text-white hover:brightness-110',
                ghost: 'bg-white/5 text-[#f0f2ff] border border-white/8 hover:bg-white/10',
                outline: 'border border-[#7c3aed]/50 text-[#a78bfa] hover:bg-[#7c3aed]/10',
                muted: 'bg-[#151821] text-[#8892b0] border border-white/6 hover:bg-[#1e2232]',
            },
            size: {
                sm: 'h-8  px-3 text-xs',
                md: 'h-10 px-4',
                lg: 'h-12 px-6 text-base',
                icon: 'h-10 w-10',
                'icon-lg': 'h-14 w-14 rounded-full',
                'icon-xl': 'h-20 w-20 rounded-full text-2xl',
            },
        },
        defaultVariants: { variant: 'ghost', size: 'md' },
    }
)

interface ButtonProps
    extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> { }

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, ...props }, ref) => (
        <button
            ref={ref}
            className={cn(buttonVariants({ variant, size }), className)}
            {...props}
        />
    )
)
Button.displayName = 'Button'

export { Button, buttonVariants }
