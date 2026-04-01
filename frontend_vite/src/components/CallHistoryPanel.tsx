// ── components/CallHistoryPanel.tsx ───────────────────────────────────────
// Displays all call sessions (web + phone) from the unified backend DB.
// Source is shown as a coloured badge: 🌐 Web | 📞 Phone
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    PhoneCall,
    Globe,
    Loader2,
    RefreshCw,
    Clock,
    CheckCircle2,
    XCircle,
    AlertCircle,
    ChevronDown,
    ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = 'http://localhost:8000'

interface CallRecord {
    id: string
    source: 'web' | 'phone'
    call_sid?: string
    status: string
    start_time?: string
    end_time?: string
    analysis?: {
        summary?: string
        sentiment?: string
        is_interested?: boolean
        key_topics?: string[]
    }
    transcript?: unknown[]
}

function formatDate(iso?: string): string {
    if (!iso) return 'Unknown'
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })
}

function formatDuration(start?: string, end?: string): string {
    if (!start || !end) return '—'
    const ms = new Date(end).getTime() - new Date(start).getTime()
    if (isNaN(ms) || ms <= 0) return '—'
    const s = Math.floor(ms / 1000)
    const m = Math.floor(s / 60)
    const sec = s % 60
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

function StatusIcon({ status }: { status: string }) {
    if (status === 'completed')
        return <CheckCircle2 size={10} className="text-emerald-400" />
    if (status === 'started')
        return <Clock size={10} className="text-amber-400 animate-pulse" />
    return <XCircle size={10} className="text-red-400" />
}

function SentimentDot({ sentiment }: { sentiment?: string }) {
    const map: Record<string, string> = {
        positive: 'bg-emerald-400',
        neutral: 'bg-amber-400',
        negative: 'bg-red-400',
    }
    const color = map[sentiment ?? ''] ?? 'bg-white/20'
    return <span className={cn('w-2 h-2 rounded-full inline-block', color)} />
}

// ── Single Call Row ──────────────────────────────────────────────────────────
function CallRow({ rec }: { rec: CallRecord }) {
    const [expanded, setExpanded] = useState(false)
    const isPhone = rec.source === 'phone'

    return (
        <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                'rounded-xl border transition-all duration-200 overflow-hidden',
                expanded
                    ? 'bg-[#151821] border-purple-500/20'
                    : 'bg-[#151821] border-white/5 hover:border-purple-500/15'
            )}
        >
            {/* Header row */}
            <button
                onClick={() => setExpanded((v) => !v)}
                className="w-full px-3 py-2.5 flex items-center gap-2 text-left"
            >
                {/* Source badge */}
                <span
                    className={cn(
                        'shrink-0 flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider',
                        isPhone
                            ? 'bg-blue-500/15 text-blue-300'
                            : 'bg-violet-500/15 text-violet-300'
                    )}
                >
                    {isPhone ? <PhoneCall size={8} /> : <Globe size={8} />}
                    {isPhone ? 'Phone' : 'Web'}
                </span>

                {/* Status */}
                <StatusIcon status={rec.status} />

                {/* Date */}
                <span className="flex-1 text-[11px] text-[#8892b0] truncate">
                    {formatDate(rec.start_time)}
                </span>

                {/* Duration */}
                <span className="text-[10px] text-[#3d4263] shrink-0">
                    {formatDuration(rec.start_time, rec.end_time)}
                </span>

                {/* Expand chevron */}
                {expanded ? (
                    <ChevronDown size={11} className="text-[#3d4263] shrink-0" />
                ) : (
                    <ChevronRight size={11} className="text-[#3d4263] shrink-0" />
                )}
            </button>

            {/* Expanded analysis */}
            <AnimatePresence>
                {expanded && rec.analysis && (
                    <motion.div
                        key="details"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="px-3 pb-3 flex flex-col gap-2 border-t border-white/5 pt-2"
                    >
                        {rec.analysis.summary && (
                            <p className="text-[11px] text-[#8892b0] leading-relaxed">
                                {rec.analysis.summary}
                            </p>
                        )}

                        <div className="flex items-center gap-3 flex-wrap">
                            {rec.analysis.sentiment && (
                                <span className="flex items-center gap-1.5 text-[10px] text-[#3d4263]">
                                    <SentimentDot sentiment={rec.analysis.sentiment} />
                                    {rec.analysis.sentiment}
                                </span>
                            )}
                            {rec.analysis.is_interested && (
                                <span className="text-[10px] text-emerald-400 font-medium">
                                    💰 Interested
                                </span>
                            )}
                        </div>

                        {rec.analysis.key_topics && rec.analysis.key_topics.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                {rec.analysis.key_topics.slice(0, 4).map((t) => (
                                    <span
                                        key={t}
                                        className="text-[9px] bg-white/5 text-[#8892b0] rounded-md px-1.5 py-0.5"
                                    >
                                        {t}
                                    </span>
                                ))}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    )
}


// ── CallHistoryPanel ─────────────────────────────────────────────────────────
export function CallHistoryPanel() {
    const [calls, setCalls] = useState<CallRecord[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [filter, setFilter] = useState<'all' | 'web' | 'phone'>('all')

    const fetchCalls = async () => {
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`${API_BASE}/api/telephony/calls?limit=30`)
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data: CallRecord[] = await res.json()
            setCalls(data)
        } catch {
            setError('Could not load call history')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchCalls() }, [])

    const filtered = filter === 'all' ? calls : calls.filter((c) => c.source === filter)

    return (
        <div className="flex flex-col gap-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <p className="text-[10px] uppercase tracking-widest text-[#3d4263] font-medium">
                    Call History
                </p>
                <button
                    onClick={fetchCalls}
                    disabled={loading}
                    className="w-6 h-6 flex items-center justify-center text-[#3d4263] hover:text-purple-400 transition-colors rounded-lg hover:bg-purple-600/10"
                    title="Refresh"
                >
                    <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {/* Filter pills */}
            <div className="flex gap-1">
                {(['all', 'web', 'phone'] as const).map((f) => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={cn(
                            'flex-1 py-1 text-[10px] rounded-lg font-medium transition-all duration-150 capitalize',
                            filter === f
                                ? 'bg-[#7c3aed] text-white'
                                : 'bg-white/5 text-[#8892b0] hover:bg-white/10'
                        )}
                    >
                        {f}
                    </button>
                ))}
            </div>

            {/* Content */}
            <AnimatePresence mode="wait">
                {loading && (
                    <motion.div
                        key="loading"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex items-center justify-center py-6 text-[#3d4263]"
                    >
                        <Loader2 size={16} className="animate-spin" />
                    </motion.div>
                )}

                {!loading && error && (
                    <motion.div
                        key="error"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex flex-col items-center gap-1.5 py-4 text-[#3d4263]"
                    >
                        <AlertCircle size={16} className="text-red-400/60" />
                        <p className="text-[11px] text-red-400/70 text-center">{error}</p>
                    </motion.div>
                )}

                {!loading && !error && filtered.length === 0 && (
                    <motion.div
                        key="empty"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex flex-col items-center gap-2 py-6 text-[#3d4263]"
                    >
                        <PhoneCall size={20} className="opacity-30" />
                        <p className="text-[11px] text-center leading-relaxed">
                            No calls yet.<br />Start a web or phone call.
                        </p>
                    </motion.div>
                )}

                {!loading && !error && filtered.length > 0 && (
                    <motion.div
                        key="list"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex flex-col gap-2 max-h-[420px] overflow-y-auto pr-0.5"
                    >
                        {filtered.map((c) => (
                            <CallRow key={c.id} rec={c} />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
