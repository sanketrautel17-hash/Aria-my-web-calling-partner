// ── hooks/usePipecat.ts ───────────────────────────────────────────────────
// Encapsulates all Pipecat client SDK logic; components just call actions.
import { useCallback, useRef } from 'react'
import { useCallStore } from '@/store/useCallStore'

const API_BASE = '/api'   // proxied by Vite dev server to http://localhost:8000

export function usePipecat() {
    const {
        setStatus, setPcId, setPipecatClient,
        setMuted, setBotSpeaking, setUserSpeaking,
        addMessage, updatePartial, finalizePartial,
        isMuted, pipecatClient, pcId,
    } = useCallStore()

    // ── Refs for user STT partial tracking ───────────────────────────────────
    const partialIdRef = useRef<string | null>(null)

    // ── Refs for bot response accumulation ───────────────────────────────────
    // The Pipecat SDK fires onBotOutput TWICE per chunk:
    //   1. When the LLM emits text (to feed TTS)
    //   2. When TTS completes speaking that chunk (transcript confirmation)
    // We accumulate all chunks into ONE partial message bubble per bot turn
    // and skip consecutive identical chunks to avoid duplication.
    const botPartialIdRef = useRef<string | null>(null)
    const botAccumRef = useRef<string>('')
    const botLastChunkRef = useRef<string>('')

    const connect = useCallback(async () => {
        setStatus('connecting')
        try {
            // Dynamic import — keeps initial bundle small
            const [{ PipecatClient }, { SmallWebRTCTransport }] = await Promise.all([
                import('@pipecat-ai/client-js'),
                import('@pipecat-ai/small-webrtc-transport'),
            ])

            const transport = new SmallWebRTCTransport()

            // Handle incoming audio tracks
            const audioEl = new Audio()
            audioEl.autoplay = true

            const client = new PipecatClient({
                transport,
                enableMic: true,
                enableCam: false,
                callbacks: {
                    // ── Media ────────────────────────────────────────────────────
                    onTrackStarted: (track: MediaStreamTrack) => {
                        if (track.kind === 'audio') {
                            const stream = new MediaStream([track])
                            audioEl.srcObject = stream
                            audioEl.play().catch(console.error)
                        }
                    },

                    // ── Connection ───────────────────────────────────────────────
                    onConnected: () => {
                        // NOTE: Do NOT add a hardcoded welcome message here.
                        // The backend sends a TTSSpeakFrame greeting which arrives via
                        // onBotOutput — adding one here would cause a duplicate.
                        setStatus('connected')
                    },
                    onDisconnected: () => {
                        setStatus('idle')
                        setPcId(null)
                        setPipecatClient(null)
                        partialIdRef.current = null
                        // Reset bot accumulation state
                        botPartialIdRef.current = null
                        botAccumRef.current = ''
                        botLastChunkRef.current = ''
                        // Stop audio
                        audioEl.pause()
                        audioEl.srcObject = null
                    },

                    // ── VAD ──────────────────────────────────────────────────────
                    onUserStartedSpeaking: () => setUserSpeaking(true),
                    onUserStoppedSpeaking: () => setUserSpeaking(false),

                    // ── STT (live + final) ────────────────────────────────────────
                    onUserTranscript: (data: { text: string; final: boolean }) => {
                        if (!data.text) return
                        if (data.final) {
                            if (partialIdRef.current) {
                                finalizePartial(partialIdRef.current, data.text)
                            } else {
                                addMessage({ role: 'user', text: data.text, mode: 'voice' })
                            }
                            partialIdRef.current = null
                        } else {
                            if (partialIdRef.current) {
                                updatePartial(partialIdRef.current, data.text)
                            } else {
                                const id = addMessage({ role: 'user', text: data.text, mode: 'voice', partial: true })
                                partialIdRef.current = id
                            }
                        }
                    },

                    // ── Bot speech ────────────────────────────────────────────────
                    onBotStartedSpeaking: () => {
                        setBotSpeaking(true)
                        // Open a fresh partial bubble for this bot turn
                        botAccumRef.current = ''
                        botLastChunkRef.current = ''
                        const id = addMessage({ role: 'assistant', text: '…', mode: 'voice', partial: true })
                        botPartialIdRef.current = id
                    },

                    onBotStoppedSpeaking: () => {
                        setBotSpeaking(false)
                        // Finalize the accumulated text into the bubble
                        if (botPartialIdRef.current && botAccumRef.current) {
                            finalizePartial(botPartialIdRef.current, botAccumRef.current)
                        }
                        botPartialIdRef.current = null
                        botAccumRef.current = ''
                        botLastChunkRef.current = ''
                    },

                    onBotOutput: (data: { text: string }) => {
                        if (!data.text) return

                        // ── Deduplication ─────────────────────────────────────────
                        // Skip this chunk if it is identical to the previous one.
                        // The Pipecat SDK emits each sentence chunk twice (LLM + TTS
                        // transcript), making every response appear doubled without this.
                        if (data.text === botLastChunkRef.current) return
                        botLastChunkRef.current = data.text

                        // ── Accumulate into the streaming bubble ──────────────────
                        botAccumRef.current += (botAccumRef.current ? ' ' : '') + data.text

                        if (botPartialIdRef.current) {
                            // Update the existing partial bubble with the new accumulated text
                            updatePartial(botPartialIdRef.current, botAccumRef.current)
                        } else {
                            // Fallback: onBotStartedSpeaking didn't fire — create bubble now
                            const id = addMessage({
                                role: 'assistant',
                                text: botAccumRef.current,
                                mode: 'voice',
                                partial: true,
                            })
                            botPartialIdRef.current = id
                        }
                    },

                    // ── Text channel ──────────────────────────────────────────────
                    // NOTE: onMessage is intentionally removed.
                    // The Pipecat SDK fires BOTH onBotOutput AND onMessage for every
                    // bot speech turn (the data channel carries a text transcript of the
                    // same TTS output). Handling both causes identical messages to appear
                    // twice. onBotOutput alone is sufficient for all bot responses.

                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    onError: (message: any) => {
                        console.error('Pipecat error:', message)
                        setStatus('error')
                    },
                },
            } as any)

            await client.connect({
                webrtcRequestParams: {
                    url: `${API_BASE}/offer`,
                    // @ts-ignore - Library requires 'endpoint' property internally
                    endpoint: `${API_BASE}/offer`,
                    // Note: SmallWebRTCTransport already sets Content-Type: application/json
                    // Do NOT add it here — it causes duplication (seen in logs as "application/json, application/json")
                }
            })
            setPipecatClient(client)
        } catch (err) {
            console.error('Connection failed:', err)
            setStatus('error')
        }
    }, [setStatus, setPcId, setPipecatClient, addMessage, updatePartial, finalizePartial, setUserSpeaking, setBotSpeaking])

    const disconnect = useCallback(async () => {
        if (!pipecatClient) return
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await (pipecatClient as any).disconnect()
        setPipecatClient(null)
        setStatus('idle')
    }, [pipecatClient, setPipecatClient, setStatus])

    const toggleMute = useCallback(() => {
        if (!pipecatClient) return
        const next = !isMuted
        setMuted(next)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ; (pipecatClient as any).enableMic(!next)
    }, [pipecatClient, isMuted, setMuted])

    const sendText = useCallback((text: string) => {
        if (!text.trim() || !pipecatClient) return
        addMessage({ role: 'user', text, mode: 'text' })
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ; (pipecatClient as any).sendMessage({ text })
    }, [pipecatClient, addMessage])

    const setVoiceMode = useCallback((m: 'voice' | 'text') => {
        useCallStore.getState().setMode(m)
        if (pipecatClient) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ; (pipecatClient as any).enableMic(m === 'voice' && !isMuted)
        }
    }, [pipecatClient, isMuted])

    return { connect, disconnect, toggleMute, sendText, setVoiceMode, pcId }
}
