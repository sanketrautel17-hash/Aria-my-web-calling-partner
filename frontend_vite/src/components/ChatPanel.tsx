// ── components/ChatPanel.tsx ──────────────────────────────────────────────
// Scrollable chat transcript panel with user + assistant bubbles
import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MessageSquare } from 'lucide-react'
import { useCallStore, type ChatMessage } from '@/store/useCallStore'
import { cn } from '@/lib/utils'

function MessageBubble({ msg }: { msg: ChatMessage }) {
    const isUser = msg.role === 'user'
    const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className={cn('flex gap-3 max-w-[80%]', isUser ? 'self-end flex-row-reverse' : 'self-start')}
        >
            {/* Avatar */}
            <div
                className={cn(
                    'w-8 h-8 min-w-8 rounded-full flex items-center justify-center text-xs font-semibold',
                    isUser
                        ? 'bg-gradient-to-br from-blue-500 to-violet-600'
                        : 'bg-gradient-to-br from-violet-600 to-purple-900'
                )}
            >
                {isUser ? 'U' : 'A'}
            </div>

            {/* Bubble */}
            <div className="flex flex-col gap-1">
                <div
                    className={cn(
                        'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                        isUser
                            ? 'bg-gradient-to-br from-[#7c3aed] to-[#6d28d9] text-white rounded-br-sm'
                            : 'bg-[#151821] border border-white/6 text-[#f0f2ff] rounded-bl-sm',
                        msg.partial && 'opacity-60 italic'
                    )}
                >
                    {msg.text}
                </div>
                <div className={cn('flex items-center gap-1 text-[10px] text-[#3d4263]', isUser && 'justify-end')}>
                    {msg.mode === 'voice'
                        ? <Mic size={9} />
                        : <MessageSquare size={9} />
                    }
                    {time}
                </div>
            </div>
        </motion.div>
    )
}

function TypingIndicator() {
    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex gap-3 self-start"
        >
            <div className="w-8 h-8 min-w-8 rounded-full bg-gradient-to-br from-violet-600 to-purple-900 flex items-center justify-center text-xs font-semibold">
                A
            </div>
            <div className="bg-[#151821] border border-white/6 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
                {[0, 0.2, 0.4].map((d) => (
                    <motion.span
                        key={d}
                        className="block w-1.5 h-1.5 rounded-full bg-[#7c3aed]"
                        animate={{ y: [0, -4, 0] }}
                        transition={{ duration: 0.8, delay: d, repeat: Infinity, ease: 'easeInOut' }}
                    />
                ))}
            </div>
        </motion.div>
    )
}

export function ChatPanel() {
    const { messages, isBotSpeaking } = useCallStore()
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const showTyping = isBotSpeaking && messages[messages.length - 1]?.role !== 'assistant'

    return (
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-3">
            <AnimatePresence initial={false}>
                {messages.map((msg) => (
                    <MessageBubble key={msg.id} msg={msg} />
                ))}
                {showTyping && <TypingIndicator key="typing" />}
            </AnimatePresence>
            <div ref={bottomRef} />
        </div>
    )
}
