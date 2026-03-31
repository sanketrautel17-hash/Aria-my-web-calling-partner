// ── components/RecordingsPanel.tsx ────────────────────────────────────────
// Lists, plays, and downloads saved call recordings from the backend
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, Play, Pause, Loader2, Disc3, RefreshCw, Clock, HardDrive } from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = 'http://localhost:8000'

interface Recording {
    filename: string
    size_bytes: number
    created_at: string
    duration_seconds: number | null
}

function formatBytes(b: number): string {
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
    return `${(b / (1024 * 1024)).toFixed(2)} MB`
}

function formatDuration(s: number | null): string {
    if (s === null) return '--'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${String(sec).padStart(2, '0')}`
}

function formatDate(iso: string): string {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
    })
}

// ── Single Recording row ────────────────────────────────────────────────────
function RecordingRow({ rec }: { rec: Recording }) {
    const [isPlaying, setIsPlaying] = useState(false)
    const [progress, setProgress] = useState(0)
    const audioRef = useRef<HTMLAudioElement | null>(null)
    const url = `${API_BASE}/api/recordings/${encodeURIComponent(rec.filename)}`

    const togglePlay = () => {
        if (!audioRef.current) {
            audioRef.current = new Audio(url)
            audioRef.current.addEventListener('ended', () => {
                setIsPlaying(false)
                setProgress(0)
            })
            audioRef.current.addEventListener('timeupdate', () => {
                const a = audioRef.current
                if (!a || !a.duration) return
                setProgress(a.currentTime / a.duration)
            })
        }

        if (isPlaying) {
            audioRef.current.pause()
            setIsPlaying(false)
        } else {
            audioRef.current.play()
            setIsPlaying(true)
        }
    }

    const handleDownload = () => {
        const a = document.createElement('a')
        a.href = url
        a.download = rec.filename
        a.click()
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="group relative rounded-xl bg-[#151821] border border-white/5 px-3.5 py-3 flex flex-col gap-2 hover:border-purple-500/25 transition-all duration-200"
        >
            {/* Header row */}
            <div className="flex items-center gap-2">
                {/* Play/Pause */}
                <button
                    onClick={togglePlay}
                    className={cn(
                        'w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-all duration-150',
                        isPlaying
                            ? 'bg-purple-600 text-white shadow-[0_0_12px_rgba(124,58,237,0.4)]'
                            : 'bg-white/6 text-[#8892b0] hover:bg-purple-600/20 hover:text-purple-400'
                    )}
                    title={isPlaying ? 'Pause' : 'Play'}
                >
                    {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                </button>

                {/* Filename */}
                <span className="flex-1 text-[11px] text-[#c8cfe0] font-mono truncate">
                    {rec.filename.replace('session_', '').replace('.wav', '')}
                </span>

                {/* Download */}
                <button
                    onClick={handleDownload}
                    className="opacity-0 group-hover:opacity-100 w-7 h-7 rounded-lg flex items-center justify-center text-[#8892b0] hover:text-purple-400 hover:bg-purple-600/10 transition-all duration-150"
                    title="Download WAV"
                >
                    <Download size={12} />
                </button>
            </div>

            {/* Progress bar */}
            {isPlaying && (
                <div className="h-0.5 w-full bg-white/8 rounded-full overflow-hidden">
                    <motion.div
                        className="h-full bg-gradient-to-r from-purple-500 to-violet-400 rounded-full"
                        style={{ width: `${progress * 100}%` }}
                    />
                </div>
            )}

            {/* Meta row */}
            <div className="flex items-center gap-3 text-[10px] text-[#3d4263]">
                <span className="flex items-center gap-1">
                    <Clock size={9} />
                    {formatDuration(rec.duration_seconds)}
                </span>
                <span className="flex items-center gap-1">
                    <HardDrive size={9} />
                    {formatBytes(rec.size_bytes)}
                </span>
                <span className="ml-auto">{formatDate(rec.created_at)}</span>
            </div>
        </motion.div>
    )
}


// ── RecordingsPanel ─────────────────────────────────────────────────────────
export function RecordingsPanel() {
    const [recordings, setRecordings] = useState<Recording[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchRecordings = async () => {
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`${API_BASE}/api/recordings`)
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const data = await res.json()
            setRecordings(data.recordings ?? [])
        } catch (e) {
            setError('Could not load recordings')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchRecordings() }, [])

    return (
        <div className="flex flex-col gap-3">
            {/* Header */}
            <div className="flex items-center justify-between">
                <p className="text-[10px] uppercase tracking-widest text-[#3d4263] font-medium">
                    Recordings
                </p>
                <button
                    onClick={fetchRecordings}
                    disabled={loading}
                    className="w-6 h-6 flex items-center justify-center text-[#3d4263] hover:text-purple-400 transition-colors rounded-lg hover:bg-purple-600/10"
                    title="Refresh"
                >
                    <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {/* States */}
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
                        className="text-[11px] text-red-400/70 text-center py-4"
                    >
                        {error}
                    </motion.div>
                )}

                {!loading && !error && recordings.length === 0 && (
                    <motion.div
                        key="empty"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex flex-col items-center gap-2 py-6 text-[#3d4263]"
                    >
                        <Disc3 size={20} className="opacity-40" />
                        <p className="text-[11px] text-center leading-relaxed">
                            No recordings yet.<br />Complete a call to save audio.
                        </p>
                    </motion.div>
                )}

                {!loading && !error && recordings.length > 0 && (
                    <motion.div
                        key="list"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="flex flex-col gap-2"
                    >
                        {recordings.map((r) => (
                            <RecordingRow key={r.filename} rec={r} />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
