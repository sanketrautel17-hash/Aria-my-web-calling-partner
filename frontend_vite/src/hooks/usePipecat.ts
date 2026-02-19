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

    const partialIdRef = useRef<string | null>(null)

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
                    onTrackStarted: (track) => {
                        if (track.kind === 'audio') {
                            const stream = new MediaStream([track])
                            audioEl.srcObject = stream
                            audioEl.play().catch(console.error)
                        }
                    },

                    // ── Connection ───────────────────────────────────────────────
                    onConnected: () => {
                        setStatus('connected')
                        addMessage({ role: 'assistant', text: "Hi! I'm Aria. Ready to help — speak or type!", mode: 'text' })
                    },
                    onDisconnected: () => {
                        setStatus('idle')
                        setPcId(null)
                        setPipecatClient(null)
                        partialIdRef.current = null
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
                    onBotStartedSpeaking: () => setBotSpeaking(true),
                    onBotStoppedSpeaking: () => setBotSpeaking(false),
                    onBotOutput: (data: { text: string }) => {
                        if (data.text) addMessage({ role: 'assistant', text: data.text, mode: 'voice' })
                    },

                    // ── Text channel ──────────────────────────────────────────────
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    onMessage: (msg: any) => {
                        if (msg?.text) addMessage({ role: 'assistant', text: msg.text, mode: 'text' })
                    },

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
                    headers: new Headers({ 'Content-Type': 'application/json' }),
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
