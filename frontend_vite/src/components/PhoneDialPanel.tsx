// ── components/PhoneDialPanel.tsx ─────────────────────────────────────────
// Panel for initiating outbound Twilio phone calls via the Aria backend.
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { PhoneCall, PhoneOff, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = 'http://localhost:8000'

type DialState = 'idle' | 'calling' | 'success' | 'error'

export function PhoneDialPanel() {
    const [phoneNumber, setPhoneNumber] = useState('')
    const [dialState, setDialState] = useState<DialState>('idle')
    const [callSid, setCallSid] = useState<string | null>(null)
    const [errorMsg, setErrorMsg] = useState<string | null>(null)

    const handleDial = async () => {
        if (!phoneNumber.trim()) return
        setDialState('calling')
        setErrorMsg(null)
        setCallSid(null)

        try {
            const res = await fetch(`${API_BASE}/api/telephony/dialout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ to_number: phoneNumber.trim() }),
            })

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail ?? `HTTP ${res.status}`)
            }

            const data = await res.json()
            setCallSid(data.call_sid)
            setDialState('success')
        } catch (e) {
            setErrorMsg(e instanceof Error ? e.message : 'Unknown error')
            setDialState('error')
        }
    }

    const handleReset = () => {
        setDialState('idle')
        setCallSid(null)
        setErrorMsg(null)
    }

    return (
        <div className="flex flex-col gap-3">
            {/* Header */}
            <p className="text-[10px] uppercase tracking-widest text-[#3d4263] font-medium">
                Phone Call
            </p>
            <p className="text-[11px] text-[#3d4263] leading-relaxed">
                Initiate an outbound call via Twilio. Aria will introduce herself
                and handle the loan inquiry automatically.
            </p>

            {/* Input */}
            <div className="flex flex-col gap-2">
                <input
                    id="phone-number-input"
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleDial()}
                    placeholder="+91 98765 43210"
                    disabled={dialState === 'calling'}
                    className={cn(
                        'w-full rounded-xl border bg-[#0d0f18] px-3 py-2.5 text-[13px] text-[#c8cfe0] placeholder-[#3d4263] outline-none transition-all duration-200',
                        'border-white/8 focus:border-purple-500/50 focus:shadow-[0_0_0_2px_rgba(124,58,237,0.12)]',
                        dialState === 'calling' && 'opacity-50 cursor-not-allowed'
                    )}
                />

                <AnimatePresence mode="wait">
                    {dialState === 'idle' || dialState === 'calling' ? (
                        <motion.button
                            key="dial"
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                            onClick={handleDial}
                            disabled={!phoneNumber.trim() || dialState === 'calling'}
                            id="btn-initiate-phone-call"
                            className={cn(
                                'w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-[12px] font-semibold transition-all duration-200',
                                !phoneNumber.trim() || dialState === 'calling'
                                    ? 'bg-white/5 text-[#3d4263] cursor-not-allowed'
                                    : 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.3)] hover:shadow-[0_0_28px_rgba(37,99,235,0.45)] hover:scale-[1.02] active:scale-100'
                            )}
                        >
                            {dialState === 'calling' ? (
                                <>
                                    <Loader2 size={13} className="animate-spin" />
                                    Connecting…
                                </>
                            ) : (
                                <>
                                    <PhoneCall size={13} />
                                    Call Now
                                </>
                            )}
                        </motion.button>
                    ) : dialState === 'success' ? (
                        <motion.div
                            key="success"
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                            className="flex flex-col gap-2"
                        >
                            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
                                <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-[11px] text-emerald-300 font-medium">Call initiated!</p>
                                    {callSid && (
                                        <p className="text-[10px] text-emerald-400/60 font-mono truncate">
                                            {callSid}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={handleReset}
                                className="w-full flex items-center justify-center gap-2 rounded-xl py-2 text-[11px] font-medium text-[#8892b0] bg-white/5 hover:bg-white/8 transition-all"
                            >
                                <PhoneOff size={11} />
                                New Call
                            </button>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="error"
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                            className="flex flex-col gap-2"
                        >
                            <div className="flex items-start gap-2 rounded-xl bg-red-500/10 border border-red-500/20 px-3 py-2">
                                <AlertCircle size={13} className="text-red-400 mt-0.5 shrink-0" />
                                <p className="text-[11px] text-red-300 leading-relaxed">
                                    {errorMsg ?? 'Failed to initiate call'}
                                </p>
                            </div>
                            <button
                                onClick={handleReset}
                                className="w-full flex items-center justify-center gap-2 rounded-xl py-2 text-[11px] font-medium text-[#8892b0] bg-white/5 hover:bg-white/8 transition-all"
                            >
                                Try Again
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Note */}
            <p className="text-[10px] text-[#3d4263] leading-relaxed">
                ⓘ Requires PUBLIC_URL (ngrok) to be set and Twilio credentials configured.
            </p>
        </div>
    )
}
