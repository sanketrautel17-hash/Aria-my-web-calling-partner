// ── components/CallScreen.tsx ─────────────────────────────────────────────
// Main call view: orb (top half) + chat transcript (bottom half)
import { motion, AnimatePresence } from 'framer-motion'
import { Phone } from 'lucide-react'
import { AgentOrb } from '@/components/AgentOrb'
import { ChatPanel } from '@/components/ChatPanel'
import { ControlBar } from '@/components/ControlBar'
import { Button } from '@/components/ui/Button'
import { useCallStore } from '@/store/useCallStore'
import { usePipecat } from '@/hooks/usePipecat'

export function CallScreen() {
    const { status, messages } = useCallStore()
    const { connect } = usePipecat()
    const isConnected = status === 'connected'
    const isConnecting = status === 'connecting'
    const hasMessages = messages.length > 0

    return (
        <div className="relative flex flex-col h-full">
            {/* ── Orb Section ──────────────────────────────────────────────── */}
            <div
                className="flex items-center justify-center shrink-0"
                style={{ height: hasMessages ? '240px' : '60%' }}
            >
                <motion.div
                    layout
                    transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                    style={{ scale: hasMessages ? 0.75 : 1 }}
                    className="flex flex-col items-center gap-6"
                >
                    <AgentOrb />

                    {/* Connect button — shown only when idle */}
                    <AnimatePresence>
                        {status === 'idle' && (
                            <motion.div
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -8 }}
                            >
                                <Button
                                    variant="primary"
                                    size="lg"
                                    onClick={connect}
                                    className="shadow-[0_0_24px_rgba(124,58,237,0.3)] px-8"
                                >
                                    <Phone size={16} />
                                    Start Call
                                </Button>
                            </motion.div>
                        )}

                        {isConnecting && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="text-xs text-[#8892b0] flex items-center gap-2"
                            >
                                <span className="inline-block w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
                                Establishing secure connection…
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>
            </div>

            {/* ── Chat Panel ───────────────────────────────────────────────── */}
            <AnimatePresence>
                {hasMessages && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex-1 overflow-hidden flex flex-col border-t border-white/5"
                    >
                        <ChatPanel />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Control Bar ──────────────────────────────────────────────── */}
            <div
                className="border-t shrink-0"
                style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
                <ControlBar />
            </div>

            {/* Connecting overlay shimmer */}
            {isConnecting && (
                <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute inset-0 bg-gradient-to-b from-purple-900/5 to-transparent animate-pulse" />
                </div>
            )}
        </div>
    )
}
