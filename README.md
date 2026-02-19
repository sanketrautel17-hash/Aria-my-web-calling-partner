# Pipecat Web Calling Application

A real-time **voice + text chat** AI agent application built using **Pipecat**, **SmallWebRTC**, **Deepgram**, and **Groq** — inspired by [Eigi AI](https://eigi.ai).

## 🚀 Features

*   **🎙️ Real-time Voice Conversation:** Low-latency voice interaction via WebRTC.
*   **💬 Text Chat:** Send and receive messages via a live chat interface alongside voice.
*   **🔀 Dual Mode:** Switch between voice and text chat, or use both simultaneously.
*   **⚡ Interruption Handling (Barge-in):** Users can interrupt the bot mid-speech.
*   **🧠 AI Stack:**
    *   **STT:** Deepgram (High accuracy & speed)
    *   **LLM:** Groq (Llama 3 for ultra-low latency inference)
    *   **TTS:** Deepgram (Natural sounding voices)
*   **📜 Chat History:** All voice transcripts and text messages displayed in a unified chat view.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python 3.10+ + Pipecat |
| **Transport** | SmallWebRTC (`pipecat-ai[webrtc]`) |
| **STT** | Deepgram |
| **LLM** | Groq (`llama3-8b-8192`) |
| **TTS** | Deepgram |
| **Frontend Framework** | Vite + React + TypeScript |
| **Styling** | Tailwind CSS v4 + shadcn/ui |
| **Client SDK** | `@pipecat-ai/client-js`, `@pipecat-ai/small-webrtc-transport` |

## 📋 Prerequisites

You will need API keys for the following services:
1.  **Deepgram API Key:** [Get it here](https://console.deepgram.com/)
2.  **Groq API Key:** [Get it here](https://console.groq.com/)

## ⚙️ Setup & Installation

### 1. Backend Setup

1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```

2.  Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure Environment Variables — create a `.env` file in the `backend` folder:
    ```env
    DEEPGRAM_API_KEY=your_deepgram_key
    GROQ_API_KEY=your_groq_key
    ```
    (See `.env.example` for reference)

5.  Run the server:
    ```bash
    python main.py
    ```
    The server will start at `http://localhost:8000`.

### 2. Frontend Setup (Vite)

1.  Navigate to the **frontend_vite** directory:
    ```bash
    cd frontend_vite
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

3.  Start the dev server:
    ```bash
    npm run dev
    ```
    The app will start at `http://localhost:5173`.

## 🏃‍♂️ How it Works

### Voice Pipeline
1. User speaks → microphone captures audio.
2. Audio streams over WebRTC to the server.
3. **Deepgram STT** transcribes audio to text.
4. Transcript sent to **Groq LLM** for a response.
5. Response streamed to **Deepgram TTS** → audio sent back to user.

### Signaling & ICE
- **POST /api/offer**: Exchanges SDP offer/answer to initialize the connection.
- **PATCH /api/offer**: Trickle ICE candidates are sent here to establish P2P or relayed connectivity.

### Unified Chat View
- Both **voice transcripts** (STT output) and **text messages** are shown in a single chat history panel.
- Bot responses appear as text and are read aloud simultaneously.

## 📄 Documentation Links
*   [Pipecat Server Docs — SmallWebRTC](https://docs.pipecat.ai/server/services/transport/small-webrtc)
*   [Pipecat Client SDK Docs — SmallWebRTC](https://docs.pipecat.ai/client/js/transports/small-webrtc)
*   [Deepgram Docs](https://developers.deepgram.com)
*   [Groq Docs](https://console.groq.com/docs)
