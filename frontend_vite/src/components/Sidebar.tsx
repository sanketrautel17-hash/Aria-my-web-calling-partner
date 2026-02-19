// ── components/Sidebar.tsx ────────────────────────────────────────────────
import { motion } from 'framer-motion'
import { Sparkles, Wifi, WifiOff, AlertCircle, Loader2 } from 'lucide-react'
import { useCallStore } from '@/store/useCallStore'
import { InfoBadge } from '@/components/ui/InfoBadge'
import { cn } from '@/lib/utils'

const statusConfig = {
    idle: { color: 'bg-[#3d4263]', label: 'Offline', icon: WifiOff },
    connecting: { color: 'bg-amber-400', label: 'Connecting…', icon: Loader2 },
    connected: { color: 'bg-emerald-400', label: 'Live', icon: Wifi },
    error: { color: 'bg-red-500', label: 'Error', icon: AlertCircle },
}

export function Sidebar() {
    const { status } = useCallStore()
    const cfg = statusConfig[status]
    const StatusIcon = cfg.icon

    return (
        <aside className="w-[260px] shrink-0 flex flex-col border-r border-white/5 bg-[#0e1018] px-5 py-7 gap-6 overflow-y-auto">
            {/* Brand */}
            <div className="flex flex-col gap-1">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-900 flex items-center justify-center shadow-[0_0_20px_rgba(124,58,237,0.35)]">
                        <Sparkles size={16} className="text-white" />
                    </div>
                    <span className="text-lg font-semibold tracking-tight text-gradient">Aria</span>
                </div>
                <p className="text-[11px] text-[#3d4263] pl-12">AI Voice & Chat Agent</p>
            </div>

            {/* Status pill */}
            <motion.div
                key={status}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-2.5 bg-[#151821] border border-white/5 rounded-xl px-3 py-2.5"
            >
                <span className={cn('w-2 h-2 rounded-full', cfg.color, status === 'connecting' && 'animate-pulse')} />
                <StatusIcon
                    size={12}
                    className={cn('text-[#8892b0]', status === 'connecting' && 'animate-spin')}
                />
                <span className="text-xs text-[#8892b0] font-medium">{cfg.label}</span>
            </motion.div>

            {/* Divider */}
            <div className="h-px bg-white/5" />

            {/* Tech stack */}
            <div className="flex flex-col gap-0.5">
                <p className="text-[10px] uppercase tracking-widest text-[#3d4263] mb-2 font-medium">Tech Stack</p>
                <InfoBadge label="STT" value="Deepgram Nova-2" />
                <InfoBadge label="LLM" value="Groq Llama 3" />
                <InfoBadge label="TTS" value="Deepgram Aura" />
                <InfoBadge label="Transport" value="SmallWebRTC" />
                <InfoBadge label="State" value="Zustand" />
                <InfoBadge label="Query" value="TanStack" />
            </div>

            {/* Divider */}
            <div className="h-px bg-white/5" />

            {/* Tips */}
            <div className="flex flex-col gap-2">
                <p className="text-[10px] uppercase tracking-widest text-[#3d4263] font-medium">Tips</p>
                {[
                    '🎙️ Click Start Call to talk',
                    '💬 Switch to Text mode to type',
                    '🤫 Hit Mute to silence mic',
                    '⚡ Interrupt anytime (barge-in)',
                ].map((tip) => (
                    <p key={tip} className="text-[11px] text-[#3d4263] leading-relaxed">{tip}</p>
                ))}
            </div>

            {/* Footer */}
            <div className="mt-auto text-[10px] text-[#3d4263] text-center">
                Powered by Pipecat · Deepgram · Groq
            </div>
        </aside>
    )
}
