"""
Pipecat pipeline factory (v0.0.102-compatible).

Pipeline:
  SmallWebRTCTransport.input()
    → AudioBufferProcessor (capture user audio, left channel)
    → DeepgramSTTService
    → LLMContextAggregator (user)
    → GroqLLMService
    → DeepgramTTSService
    → AudioBufferProcessor (capture bot audio, right channel)
    → SmallWebRTCTransport.output()
    → LLMContextAggregator (assistant)

VAD note: WebRtcVadAnalyzer was removed in pipecat 0.0.100+. We now use
          SileroVADAnalyzer (ONNX-based, no PyTorch/DLL required on Windows).

Deepgram keepalive: We set keepalive=True and a short endpointing window so
          the STT WebSocket never idles out with code 1011.

Recording: AudioBufferProcessor captures both channels then merges them into
          a stereo WAV (user left, bot right) on pipeline end.
"""

import asyncio
import struct

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.base_transport import TransportParams
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
