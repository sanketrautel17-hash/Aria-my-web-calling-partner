// ── store/useCallStore.ts ─────────────────────────────────────────────────
// Zustand store for global call + chat state
import { create } from 'zustand'

export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error'
export type MessageRole = 'user' | 'assistant'
export type MessageMode = 'voice' | 'text'

export interface ChatMessage {
    id: string
    role: MessageRole
    text: string
    mode: MessageMode
    timestamp: Date
    partial?: boolean   // live STT partial transcript
}

interface CallState {
    // Connection
    status: ConnectionStatus
    pcId: string | null
    pipecatClient: unknown | null

    // UI
    isMuted: boolean
    mode: 'voice' | 'text'
    isBotSpeaking: boolean
    isUserSpeaking: boolean

    // Chat
    messages: ChatMessage[]

    // Actions
    setStatus: (s: ConnectionStatus) => void
    setPcId: (id: string | null) => void
    setPipecatClient: (c: unknown | null) => void
    setMuted: (v: boolean) => void
    setMode: (m: 'voice' | 'text') => void
    setBotSpeaking: (v: boolean) => void
    setUserSpeaking: (v: boolean) => void

    addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => string
    updatePartial: (id: string, text: string) => void
    finalizePartial: (id: string, text: string) => void
    clearMessages: () => void
}

let _idCounter = 0
const genId = () => `msg-${Date.now()}-${_idCounter++}`

export const useCallStore = create<CallState>((set) => ({
    // initial state
    status: 'idle',
    pcId: null,
    pipecatClient: null,
    isMuted: false,
    mode: 'voice',
    isBotSpeaking: false,
    isUserSpeaking: false,
    messages: [],

    // setters
    setStatus: (s) => set({ status: s }),
    setPcId: (id) => set({ pcId: id }),
    setPipecatClient: (c) => set({ pipecatClient: c }),
    setMuted: (v) => set({ isMuted: v }),
    setMode: (m) => set({ mode: m }),
    setBotSpeaking: (v) => set({ isBotSpeaking: v }),
    setUserSpeaking: (v) => set({ isUserSpeaking: v }),

    addMessage: (msg) => {
        const id = genId()
        set((s) => ({
            messages: [
                ...s.messages,
                { ...msg, id, timestamp: new Date() },
            ],
        }))
        return id
    },

    updatePartial: (id, text) =>
        set((s) => ({
            messages: s.messages.map((m) =>
                m.id === id ? { ...m, text, partial: true } : m
            ),
        })),

    finalizePartial: (id, text) =>
        set((s) => ({
            messages: s.messages.map((m) =>
                m.id === id ? { ...m, text, partial: false } : m
            ),
        })),

    clearMessages: () => set({ messages: [] }),
}))
