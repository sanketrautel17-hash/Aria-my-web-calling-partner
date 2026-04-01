"""
Aria — Unified Pipecat pipeline factory.

Supports two transport channels, both  using the same AI stack:

  Web Call  (WebRTC):
    SmallWebRTCTransport  → STT → LLM → TTS → SmallWebRTCTransport

  Phone Call (Twilio/Telephony):
    FastAPIWebsocketTransport → STT → LLM → TTS → FastAPIWebsocketTransport

Both channels:
  - Use the identical Loan Assistant system prompt (core/prompt.py)
  - Use the same Deepgram STT/TTS and Groq LLM configuration
  - Register the same three LLM tools (get_loan_information, search_web, end_call)
  - Save call records to Aria's unified MongoDB `calls` collection
    distinguished by source: 'web' | 'phone'

VAD: SileroVADAnalyzer (ONNX, no PyTorch DLL required on Windows)
Recording: stereo WAV saved to backend/recordings/ (web calls only)
"""

import asyncio
import struct
import os
from datetime import datetime

from pipecat.frames.frames import TTSSpeakFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer

from core.config import settings
from core.prompt import SYSTEM_PROMPT
from core.recordings import generate_filename, save_wav
from commons.logger import logger

log = logger(__name__)

# Greeting the bot speaks the moment the call connects
GREETING = "Hi there! I'm Aria, your AI assistant. How can I help you today?"

# Audio recording parameters (must match transport + STT)
SAMPLE_RATE = 16_000
NUM_CHANNELS = 1  # mono per channel before merge


def _interleave_to_stereo(left: bytes, right: bytes) -> bytes:
    """
    Merge two mono PCM16 byte streams into one stereo interleaved stream.
    If they differ in length, the shorter one is zero-padded.
    Result: [L0, R0, L1, R1, ...]
    """
    # Pad shorter to same length (2 bytes per sample)
    max_len = max(len(left), len(right))
    # Align to 2-byte boundary
    max_len = max_len + (max_len % 2)
    left = left.ljust(max_len, b"\x00")
    right = right.ljust(max_len, b"\x00")

    stereo = bytearray()
    for i in range(0, max_len, 2):
        stereo += left[i: i + 2]   # left sample
        stereo += right[i: i + 2]  # right sample
    return bytes(stereo)


# ── Simple audio accumulator (replaces AudioBufferProcessor if not available) ─
class _AudioAccumulator:
    """Accumulates raw PCM bytes passed to it from event callbacks."""

    def __init__(self):
        self._buf = bytearray()

    def append(self, chunk: bytes):
        self._buf += chunk

    def get_bytes(self) -> bytes:
        return bytes(self._buf)


async def create_pipeline(
    webrtc_connection: SmallWebRTCConnection,
) -> tuple[PipelineRunner, PipelineTask]:
    """
    Instantiate all AI services and wire the Pipecat pipeline for one call session.

    Returns:
        (PipelineRunner, PipelineTask) — caller must call runner.run(task).
    """
    log.info(f"Building pipeline for connection {webrtc_connection.pc_id}")

    user_audio = _AudioAccumulator()
    bot_audio = _AudioAccumulator()

    # ── Transport ─────────────────────────────────────────────────────────────
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            # Silero VAD via ONNX runtime — no PyTorch DLL required on Windows
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(sample_rate=16000),
        ),
    )

    # ── STT (Deepgram Nova-2) ─────────────────────────────────────────────────
    # keepalive=True prevents Deepgram from closing the WebSocket after inactivity
    # (avoids code 1011 "keepalive ping timeout" after ~3 min of silence).
    # endpointing=300ms tells Deepgram how long to wait after speech before
    # finalising a transcript — keeps the socket active between utterances.
    stt = DeepgramSTTService(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_STT_MODEL,
        language="en-US",
        audio_passthrough=True,  # Pass audio through for recording
        live_options=LiveOptions(
            model=settings.DEEPGRAM_STT_MODEL,
            language="en-US",
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            endpointing=300,
            interim_results=True,
            smart_format=True,
            utterance_end_ms="1000",
        ),
        keepalive=True,
    )

    # ── LLM (Groq Llama 3) ───────────────────────────────────────────────────
    llm = GroqLLMService(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
    )

    # ── TTS (Deepgram Aura) ───────────────────────────────────────────────────
    tts = DeepgramTTSService(
        api_key=settings.DEEPGRAM_API_KEY,
        voice=settings.DEEPGRAM_TTS_MODEL,
    )

    # ── LLM Context ───────────────────────────────────────────────────────────
    context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    context_aggregator = LLMContextAggregatorPair(context)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    # IMPORTANT: context_aggregator.assistant() must come AFTER transport.output()
    # so it captures the complete assistant turn after audio is delivered.
    pipeline = Pipeline(
        [
            transport.input(),  # WebRTC mic audio in
            stt,  # Audio → text (Deepgram)
            context_aggregator.user(),  # Accumulate user speech turn
            llm,  # Text → LLM response (Groq)
            tts,  # LLM text → audio (Deepgram)
            transport.output(),  # Audio → WebRTC speaker out
            context_aggregator.assistant(),  # Record the full assistant turn
        ]
    )

    # ── Task ──────────────────────────────────────────────────────────────────
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,  # barge-in: user can interrupt bot
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # ── Audio capture via frame events ────────────────────────────────────────
    # We listen for InputAudioRawFrame (user mic) and OutputAudioRawFrame (bot TTS)
    # and accumulate their PCM bytes for the stereo recording.
    try:
        from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame

        @task.event_handler("on_frame")
        async def _capture_audio(frame):
            if isinstance(frame, InputAudioRawFrame):
                user_audio.append(frame.audio)
            elif isinstance(frame, OutputAudioRawFrame):
                bot_audio.append(frame.audio)

        log.info("Audio frame capture handlers registered.")
    except (ImportError, AttributeError) as e:
        log.warning(f"Could not register audio frame handlers: {e}. Recording may be empty.")

    # ── Greeting on connect ───────────────────────────────────────────────────
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        """Send greeting TTS the moment the browser connects."""
        log.info("Client connected — sending greeting")
        try:
            await task.queue_frames([TTSSpeakFrame(text=GREETING)])
            log.info("Greeting queued successfully")
        except Exception as e:
            log.error(f"Failed to queue greeting: {e}", exc_info=True)

    # ── Save recording when session ends ──────────────────────────────────────
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        """Merge user + bot audio into a stereo WAV and save it."""
        log.info(f"Client disconnected — saving recording for {webrtc_connection.pc_id}")
        _save_recording(webrtc_connection.pc_id, user_audio, bot_audio)

    runner = PipelineRunner(handle_sigint=False)

    log.info("Pipeline ready.")
    return runner, task


def _save_recording(pc_id: str, user_audio: _AudioAccumulator, bot_audio: _AudioAccumulator):
    """Merge mono channels into stereo WAV and persist to disk."""
    try:
        user_bytes = user_audio.get_bytes()
        bot_bytes = bot_audio.get_bytes()

        if not user_bytes and not bot_bytes:
            log.warning(f"No audio captured for session {pc_id}, skipping recording.")
            return

        stereo = _interleave_to_stereo(user_bytes, bot_bytes)
        filename = generate_filename(pc_id)
        path = save_wav(filename, stereo, sample_rate=SAMPLE_RATE, channels=2)
        log.info(f"Recording saved: {path}")
    except Exception as e:
        log.error(f"Failed to save recording for {pc_id}: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PHONE CALL PIPELINE  (Twilio Media Streams / Telephony)
# ═══════════════════════════════════════════════════════════════════════════════

async def _analyze_transcript(transcript: list) -> dict:
    """
    Post-call analysis: ask Groq to extract sentiment and interest level
    from the conversation transcript and return structured JSON.
    """
    try:
        import json
        from groq import AsyncGroq

        transcript_str = str(transcript)[:10_000]
        prompt = f"""Analyze this call transcript and respond with a JSON object containing:
- summary (string): 1-2 sentence summary of the call
- sentiment (string): positive | neutral | negative
- is_interested (bool): true if the caller showed genuine interest in a loan
- key_topics (list of strings): main topics discussed

Transcript:
{transcript_str}"""

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        completion = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = completion.choices[0].message.content.strip()
        # Strip markdown fences if present
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text)
    except Exception as e:
        log.error(f"Post-call analysis failed: {e}")
        return {"error": str(e), "is_interested": False}


async def _run_phone_bot(
    transport: FastAPIWebsocketTransport,
    stream_sid: str,
    call_sid: str,
) -> None:
    """
    Core phone-call AI loop.  Runs inside phone_bot() after the transport
    is configured.  Mirrors create_pipeline() but uses 8 kHz audio rates
    required by Twilio Media Streams.
    """
    from core.db.database import get_database
    from core.tools.manager import ToolManager

    # ── Services ──────────────────────────────────────────────────────────────
    stt = DeepgramSTTService(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_STT_MODEL,
        language="en-US",
        live_options=LiveOptions(
            model=settings.DEEPGRAM_STT_MODEL,
            language="en-US",
            encoding="mulaw",       # Twilio uses mulaw 8-bit
            sample_rate=8000,
            channels=1,
            endpointing=300,
            interim_results=True,
            smart_format=True,
            utterance_end_ms="1000",
        ),
        keepalive=True,
    )

    llm = GroqLLMService(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
    )

    tts = DeepgramTTSService(
        api_key=settings.DEEPGRAM_API_KEY,
        voice=settings.DEEPGRAM_TTS_MODEL,
        sample_rate=8000,           # Match Twilio's 8 kHz output
    )

    # ── Context ───────────────────────────────────────────────────────────────
    context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    context_aggregator = LLMContextAggregatorPair(context)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
        ),
    )

    # ── Tools ─────────────────────────────────────────────────────────────────
    tool_manager = ToolManager(task=task, call_sid=call_sid, source="phone")
    for fn in (
        tool_manager.get_loan_information,
        tool_manager.search_web,
        tool_manager.end_call,
    ):
        llm.register_direct_function(fn)
        log.info(f"✅ Registered tool: {fn.__name__}")

    runner = PipelineRunner(handle_sigint=False)

    # ── Greeting ──────────────────────────────────────────────────────────────
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        log.info("📞 Phone call connected — sending greeting")
        try:
            await asyncio.sleep(1.0)   # brief pause before greeting
            await task.queue_frames(
                [TextFrame(text="Hello! I'm Aria, your loan assistant. How can I help you today?")]
            )
        except Exception as e:
            log.error(f"Greeting failed: {e}", exc_info=True)

    # ── Save call start record ─────────────────────────────────────────────────
    db = None
    try:
        db = get_database()
        await db["calls"].insert_one(
            {
                "source": "phone",
                "call_sid": call_sid,
                "stream_sid": stream_sid,
                "status": "started",
                "start_time": datetime.utcnow(),
            }
        )
        log.info(f"📝 Call record created for call_sid={call_sid}")
    except Exception as e:
        log.error(f"Failed to insert call start record: {e}")

    # ── Run ───────────────────────────────────────────────────────────────────
    try:
        log.info(f"▶️  Running phone pipeline for call_sid={call_sid}")
        await runner.run(task)
    except Exception as e:
        log.error(f"❌ Phone pipeline error: {e}", exc_info=True)

    # ── Post-call: save transcript + analysis ─────────────────────────────────
    def _serialize(obj):
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_serialize(i) for i in obj]
        elif hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return _serialize(obj.__dict__)
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)

    transcript = [_serialize(m) for m in context.messages]
    log.info("📊 Analyzing phone call transcript...")
    analysis = await _analyze_transcript(transcript)
    log.info(f"Analysis: {analysis}")

    if db is not None:
        try:
            await db["calls"].update_one(
                {"call_sid": call_sid},
                {
                    "$set": {
                        "status": "completed",
                        "end_time": datetime.utcnow(),
                        "transcript": transcript,
                        "analysis": analysis,
                    }
                },
            )

            if analysis.get("is_interested"):
                log.info("💰 Interested lead detected — saving to loan_interests")
                await db["loan_interests"].insert_one(
                    {
                        "source": "phone",
                        "call_sid": call_sid,
                        "analysis": analysis,
                        "timestamp": datetime.utcnow(),
                    }
                )
        except Exception as e:
            log.error(f"Failed to update call record: {e}")


async def phone_bot(websocket, stream_sid: str, call_sid: str) -> None:
    """
    Entry point for an inbound Twilio Media Streams WebSocket connection.

    Configures FastAPIWebsocketTransport with TwilioFrameSerializer
    (handles mulaw encode/decode + Twilio message framing), then delegates
    to the AI pipeline loop in _run_phone_bot().

    Called from the telephony router in core/apis/telephony.py.
    """
    try:
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
        )

        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=serializer,
            ),
        )

        await _run_phone_bot(transport, stream_sid, call_sid)
    except Exception as e:
        log.error(f"❌ phone_bot error: {e}", exc_info=True)
