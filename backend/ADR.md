# Architecture Decision Record (ADR) - Web Calling Application

## 1. Context and Problem Statement
The goal is to build a real-time **voice + text chat** AI agent application — similar to Eigi AI. The system must support:
- Low-latency voice interaction with barge-in interruption.
- Text chat input and output alongside voice.
- A unified conversation view that shows both voice transcripts and text messages.
- Integration with modern AI services for STT, LLM inference, and TTS.

---

## 2. Technology Stack & Key Decisions

### 2.1 Core Framework: Pipecat
- **Decision:** Use **Pipecat** for server-side pipeline orchestration and client-side SDK.
- **Reasoning:** Pipecat natively handles the STT → LLM → TTS pipeline, VAD, interruptions, and messaging over the transport data channel. It supports both voice audio frames and text message frames in the same pipeline.

### 2.2 Transport Layer: SmallWebRTC
- **Decision:** Use **SmallWebRTC** (`pipecat-ai[webrtc]` server / `@pipecat-ai/small-webrtc-transport` client).
- **Reasoning:**
    - P2P audio/video without requiring a paid 3rd-party WebRTC provider.
    - Lower latency compared to WebSocket-based audio.
    - The **WebRTC Data Channel** (built-in) is used to carry text chat messages bidirectionally, avoiding a separate WebSocket for chat.

### 2.3 AI Services
- **STT:** **Deepgram** — High accuracy and speed; critical for real-time voice conversations.
- **LLM:** **Groq** (`llama3-8b-8192`) — Ultra-low latency inference.
- **TTS:** **Deepgram** — High-quality, low-latency speech synthesis.

### 2.4 Text Chat Channel
- **Decision:** Use the **WebRTC Data Channel** (via Pipecat's messaging API) for text chat.
- **Reasoning:**
    - Already available within the SmallWebRTC connection — no additional WebSocket needed.
    - The Pipecat client SDK exposes `sendMessage()` which uses the data channel.
    - On the server, text messages are received as `TransportMessageFrame` and injected directly into the LLM context (bypassing STT).
    - LLM responses are sent back as text messages AND optionally also synthesized into audio by TTS.

### 2.5 Unified Chat View
- **Decision:** The frontend will maintain a single chat history array that stores both voice transcripts and text chat messages.
- **Reasoning:** Matching the Eigi AI UX, where a user sees everything in one view regardless of whether they spoke or typed.

### 2.6 Signaling Server
- **Decision:** Use official `SmallWebRTCRequestHandler` with `POST /api/offer` and `PATCH /api/offer`.
- **Reasoning:** 
    - `POST` handles the initial SDP offer/answer exchange.
    - `PATCH` is strictly required for **trickle ICE candidate** exchange. Without this, the browser and server often fail to establish a P2P connection (especially on localhost or restrictive networks).

---

## 3. Architecture Overview

```mermaid
sequenceDiagram
    participant User
    participant Browser (Client)
    participant Server (FastAPI + Pipecat)
    participant Deepgram (STT/TTS)
    participant Groq (LLM)

    User->>Browser: Open App
    Browser->>Server: POST /api/offer (Signaling)
    Server->>Browser: SDP Answer
    Browser->>Server: PATCH /api/offer (Trickle ICE Candidates)
    Server->>Browser: PATCH /api/offer (Trickle ICE Candidates)
    Browser<->Server: WebRTC P2P Connection Established

    alt Voice Mode
        User->>Browser: Speak
        Browser->>Server: Audio Stream (WebRTC)
        Server->>Deepgram: Audio Stream
        Deepgram-->>Server: Transcribed Text
        Server->>Groq: Prompt + History + Transcript
        Groq-->>Server: Token Stream
        Server->>Deepgram: Text Stream
        Deepgram-->>Server: Audio Stream
        Server->>Browser: Audio + Text (WebRTC)
        Browser->>User: Play Audio + Show Chat
    else Text Chat Mode
        User->>Browser: Type Message
        Browser->>Server: Text Message (WebRTC Data Channel)
        Server->>Groq: Prompt + History + Text Input
        Groq-->>Server: Token Stream
        Server->>Browser: Text Response (Data Channel)
        Server->>Deepgram: Text Stream (optional TTS)
        Deepgram-->>Server: Audio (optional)
        Browser->>User: Show Chat + Play Audio (optional)
    end
```

---

## 4. Key Implementation Details

### 4.1 Pipeline Structure
```
TransportInput → DeepgramSTT → LLMContextAggregator(user) → GroqLLM → DeepgramTTS → TransportOutput
                                        ↑
                          Text messages injected here (bypass STT)
                                                              ↓
                                                  LLMContextAggregator(assistant)
```

### 4.2 Text Message Handling
- Server listens for `TransportMessageFrame` events on the data channel.
- Text is added to the LLM context as a user message, then processed by the LLM.
- LLM response is sent back to client as a text frame AND queued for TTS.

### 4.3 Interruption / Barge-in Handling
VAD detects when the user speaks while the bot is talking:
1. VAD detects speech start.
2. Pipeline emits interrupt event.
3. TTS stops, audio buffer cleared.
4. LLM generation cancelled.
5. New user speech is processed from the start.

### 4.4 System Prompt
A directive, concise system prompt ensures:
- Responses are short and conversational for voice.
- The bot can handle both voice and text input identically.
- No hallucination — tool usage enforced for factual queries.
