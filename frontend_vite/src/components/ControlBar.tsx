// ── components/ControlBar.tsx ─────────────────────────────────────────────
// Bottom action bar: mic mute, end call, mode toggle, text input
import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, PhoneOff, MessageSquare, Send } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useCallStore } from '@/store/useCallStore'
import { usePipecat } from '@/hooks/usePipecat'
import { cn } from '@/lib/utils'

export function ControlBar() {
    const { status, isMuted, mode } = useCallStore()
    const { toggleMute, disconnect, sendText, setVoiceMode } = usePipecat()
    const [inputText, setInputText] = useState('')
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const isConnected = status === 'connected'

    // Auto-resize textarea
    useEffect(() => {
        const ta = textareaRef.current
        if (!ta) return
        ta.style.height = 'auto'
        ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'
    }, [inputText])

    const handleSend = () => {
        const text = inputText.trim()
        if (!text || !isConnected) return
        sendText(text)
        setInputText('')
    }

    const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="flex flex-col gap-3 px-6 pb-6 pt-3">
            {/* Mode toggle */}
            {isConnected && (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-center"
                >
                    <div className="inline-flex bg-[#0e1018] border border-white/6 rounded-xl p-1 gap-1">
                        {(['voice', 'text'] as const).map((m) => (
                            <button
                                key={m}
                                onClick={() => setVoiceMode(m)}
                                className={cn(
                                    'flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
                                    mode === m
                                        ? 'bg-[#7c3aed] text-white'
                                        : 'text-[#8892b0] hover:text-white hover:bg-white/5'
                                )}
                            >
                                {m === 'voice' ? <Mic size={12} /> : <MessageSquare size={12} />}
                                {m.charAt(0).toUpperCase() + m.slice(1)}
                            </button>
                        ))}
                    </div>
                </motion.div>
            )}

            {/* Input row */}
            <div className="flex items-end gap-3">
                {/* Mute button */}
                <AnimatePresence>
                    {isConnected && (
                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                            <Button
                                variant={isMuted ? 'danger' : 'muted'}
                                size="icon"
                                onClick={toggleMute}
                                title={isMuted ? 'Unmute mic' : 'Mute mic'}
                            >
                                {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
                            </Button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Text input */}
                <div
                    className={cn(
                        'flex-1 flex items-end gap-2 rounded-2xl border px-4 py-2.5 transition-all duration-200',
                        'bg-[#0e1018] border-white/6',
                        isConnected && 'focus-within:border-purple-500/50 focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.1)]'
                    )}
                >
                    <textarea
                        ref={textareaRef}
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={handleKey}
                        disabled={!isConnected}
                        placeholder={isConnected ? 'Type a message… (or use voice)' : 'Start a call to chat'}
                        rows={1}
                        className="flex-1 bg-transparent outline-none resize-none text-sm text-[#f0f2ff] placeholder:text-[#3d4263] disabled:cursor-not-allowed leading-relaxed max-h-[140px] overflow-y-auto"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!isConnected || !inputText.trim()}
                        className="w-8 h-8 rounded-xl flex items-center justify-center bg-[#7c3aed] text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-[#6d28d9] transition-all duration-200 hover:shadow-[0_0_16px_rgba(124,58,237,0.4)] shrink-0"
                    >
                        <Send size={14} />
                    </button>
                </div>

                {/* End call */}
                <AnimatePresence>
                    {isConnected && (
                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                            <Button
                                variant="danger"
                                size="icon"
                                onClick={disconnect}
                                title="End call"
                            >
                                <PhoneOff size={16} />
                            </Button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}
