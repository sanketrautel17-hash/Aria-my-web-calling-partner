---
name: developing-voice-chat-agent
description: Provides architectural guidance, code templates, and debugging strategies for the Pipecat-based web calling and text chat application. Use when the user asks about Pipecat pipeline setup, SmallWebRTC transport, Deepgram/Groq integration, text chat via data channel, unified chat UI, or voice barge-in handling.
---

# Developing Voice + Chat Agent

Assists with building the dual-mode (voice + text chat) AI agent using **Pipecat**, **SmallWebRTC**, **Deepgram**, and **Groq**.

## Architecture Reference

**Voice Pipeline:** `Input (SmallWebRTC)` → `STT (Deepgram)` → `LLM (Groq)` → `TTS (Deepgram)` → `Output (SmallWebRTC)`

**Text Chat:** Text messages arrive via **WebRTC Data Channel** → injected directly into `LLM Context` (bypassing STT) → LLM response sent back as text + optionally spoken via TTS.

---

## Instructions

### 1. Server-Side: Pipeline Setup

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

transport = SmallWebRTCTransport()

stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
llm = GroqLLMService(api_key=os.getenv("GROQ_API_KEY"), model="llama3-8b-8192")
tts = DeepgramTTSService(api_key=os.getenv("DEEPGRAM_API_KEY"))

context = OpenAILLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
context_aggregator = llm.create_context_aggregator(context)

pipeline = Pipeline([
    transport.input(),
    stt,
    context_aggregator.user(),
    llm,
    tts,
    transport.output(),
    context_aggregator.assistant()
])
```

### 2. Server-Side: Text Chat via Data Channel

Handle incoming text messages from the client's chat input:

```python
@transport.event_handler("on_message_received")
async def on_message(transport, message):
    # message.text contains the user's typed text
    # Inject as a direct user message into the LLM context (skips STT)
    await pipeline_task.queue_frames([
        LLMMessagesFrame([{"role": "user", "content": message.text}])
    ])
```

### 3. Client-Side: Voice + Text Chat Setup

```javascript
import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";

const client = new PipecatClient({
  transport: new SmallWebRTCTransport(),
  media: { audio: true, video: false },
  callbacks: {
    onTranscript: (text, isFinal) => appendToChat("user", text, "voice"),
    onBotTranscript: (text) => appendToChat("bot", text, "voice"),
    onMessage: (msg) => appendToChat("bot", msg.text, "text"),
  },
});

await client.connect({ url: "/api/offer" });

// Send a text chat message
function sendTextMessage(text) {
  client.sendMessage({ text });
  appendToChat("user", text, "text");
}
```

### 4. Unified Chat UI Pattern

Maintain a single array for both voice and text messages:

```javascript
// Chat entry shape: { role: "user"|"bot", text: string, mode: "voice"|"text" }
const chatHistory = [];

function appendToChat(role, text, mode) {
  chatHistory.push({ role, text, mode });
  renderChat(); // Re-render the chat list
}
```

### 5. Debugging Checklist

- **No Audio:** Check `DEEPGRAM_API_KEY`, WebRTC ICE errors in browser console, and ensure `transport.input()`/`transport.output()` are in pipeline.
- **Text messages not arriving:** Verify data channel is open before calling `sendMessage()`; check `on_message_received` handler is registered.
- **LLM not responding to text:** Ensure `LLMMessagesFrame` is queued correctly and the pipeline task is running.
- **High latency:** Use `llama3-8b-8192` (fastest Groq model), Deepgram `nova-2` STT model.
- **Barge-in not working:** Confirm VAD is enabled (default) and `context_aggregator` is correctly placed around the LLM in the pipeline.

---

## Context
- **ADR:** See `backend/ADR.md` for full architectural decisions including text chat data channel design.
- **README:** See `README.md` for setup and installation guide.
