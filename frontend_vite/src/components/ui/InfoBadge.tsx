// ── components/InfoBadge.tsx ──────────────────────────────────────────────
import { cn } from '@/lib/utils'

interface InfoBadgeProps {
    label: string
    value: string
    className?: string
}

export function InfoBadge({ label, value, className }: InfoBadgeProps) {
    return (
        <div className={cn('flex items-center justify-between text-xs py-1.5', className)}>
            <span className="text-[#3d4263]">{label}</span>
            <span className="px-2 py-0.5 rounded-full bg-[#151821] border border-white/5 text-[#8892b0] text-[10px]">
                {value}
            </span>
        </div>
    )
}
