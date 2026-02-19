// ── components/AgentOrb.tsx ───────────────────────────────────────────────
// Large animated orb visualizing the agent's state (idle / listening / speaking)
import { motion, AnimatePresence } from 'framer-motion'
import { useCallStore } from '@/store/useCallStore'

const statusLabel: Record<string, string> = {
    idle: 'Start a call to begin',
    connecting: 'Connecting...',
    connected: 'Listening',
    error: 'Connection error',
}

export function AgentOrb() {
    const { status, isBotSpeaking, isUserSpeaking } = useCallStore()
    const isConnected = status === 'connected'
    const isActive = isConnected && (isBotSpeaking || isUserSpeaking)

    const label = isBotSpeaking
        ? 'Speaking...'
        : isUserSpeaking
            ? 'Listening...'
            : isConnected
                ? 'Ready'
                : statusLabel[status] ?? ''

    return (
        <div className="flex flex-col items-center gap-6 select-none">
            {/* Ripple rings */}
            <div className="relative flex items-center justify-center">
                <AnimatePresence>
                    {isActive && [0, 1, 2].map((i) => (
                        <motion.div
                            key={i}
                            className="absolute rounded-full border border-purple-500/20"
                            initial={{ width: 140, height: 140, opacity: 0.5 }}
                            animate={{ width: 280, height: 280, opacity: 0 }}
                            transition={{
                                duration: 2.2,
                                delay: i * 0.55,
                                repeat: Infinity,
                                ease: 'easeOut',
                            }}
                        />
                    ))}
                </AnimatePresence>

                {/* Orb */}
                <motion.div
                    className="relative z-10 rounded-full flex items-center justify-center cursor-pointer"
                    style={{ width: 140, height: 140 }}
                    animate={isActive
                        ? { scale: [1, 1.05, 1], transition: { duration: 1.8, repeat: Infinity } }
                        : { scale: 1 }
                    }
                >
                    {/* Gradient fill */}
                    <div
                        className="absolute inset-0 rounded-full"
                        style={{
                            background: 'radial-gradient(circle at 35% 35%, #a78bfa, #7c3aed 60%, #4c1d95)',
                            boxShadow: isActive
                                ? '0 0 60px rgba(124, 58, 237, 0.6), 0 0 120px rgba(124, 58, 237, 0.25)'
                                : '0 0 30px rgba(124, 58, 237, 0.3)',
                            transition: 'box-shadow 0.5s ease',
                        }}
                    />

                    {/* Sound bars inside orb */}
                    <div className="relative z-10 flex items-end justify-center gap-[3px] h-8">
                        {[0.4, 0.7, 1, 0.7, 0.4, 0.65, 0.9, 0.5].map((h, i) => (
                            <motion.div
                                key={i}
                                className="w-[3px] rounded-full bg-white/80"
                                animate={isActive
                                    ? {
                                        scaleY: [h, 1, h * 0.5, 1, h],
                                        transition: {
                                            duration: 0.7 + i * 0.05,
                                            repeat: Infinity,
                                            ease: 'easeInOut',
                                            delay: i * 0.07,
                                        },
                                    }
                                    : { scaleY: 0.3 }
                                }
                                style={{ height: '100%', originY: 1 }}
                            />
                        ))}
                    </div>
                </motion.div>
            </div>

            {/* Status label */}
            <motion.div
                key={label}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm font-medium text-[#8892b0] tracking-wide"
            >
                {status === 'connecting' ? (
                    <span className="flex items-center gap-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                        {label}
                    </span>
                ) : isActive ? (
                    <span className="flex items-center gap-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                        {label}
                    </span>
                ) : label}
            </motion.div>
        </div>
    )
}
