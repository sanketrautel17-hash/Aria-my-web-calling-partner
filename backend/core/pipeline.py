"""
Pipecat pipeline factory (v0.0.102-compatible).

Pipeline:
  SmallWebRTCTransport.input()
    → DeepgramSTTService
    → LLMContextAggregator (user)
    → GroqLLMService
    → DeepgramTTSService
    → SmallWebRTCTransport.output()
    → LLMContextAggregator (assistant)

VAD note: Silero is broken on Windows (DLL issue). We use the built-in
          WebRTC VAD available via TransportParams (vad_enabled=True) which
          requires no external native libs.
"""

from pipecat.frames.frames import TTSSpeakFrame, InputAudioRawFrame, AudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.base_transport import TransportParams

from core.config import settings
from core.prompt import SYSTEM_PROMPT
from commons.logger import logger

log = logger(__name__)

# Greeting the bot speaks the moment the call connects
GREETING = "Hi there! I'm Aria (Restored), your AI assistant. How can I help you today?"


class SecureDeepgramSTTService(DeepgramSTTService):
    """Deepgram STT that strictly enforces no-passthrough for audio input."""

    async def process_frame(self, frame, direction: FrameDirection):
        # Strictly block InputAudioRawFrame/AudioRawFrame if passthrough is disabled
        if isinstance(frame, (InputAudioRawFrame, AudioRawFrame)):
            if not self._audio_passthrough:
                # We still need to process it for STT!
                # Call process_audio_frame which generates text but doesn't push audio.
                await self.process_audio_frame(frame, direction)
                return

        await super().process_frame(frame, direction)


async def create_pipeline(
    webrtc_connection: SmallWebRTCConnection,
) -> tuple[PipelineRunner, PipelineTask]:
    """
    Instantiate all AI services and wire the Pipecat pipeline for one call session.

    Returns:
        (PipelineRunner, PipelineTask) — caller must call runner.run(task).
    """
    log.info(f"Building pipeline for connection {webrtc_connection.pc_id}")

    # ── Transport ─────────────────────────────────────────────────────────────
    # ── Transport ─────────────────────────────────────────────────────────────
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            # Built-in VAD — no Silero/torch DLL required on Windows
            vad_enabled=True,
        ),
    )

    # ── STT (Deepgram Nova-2) ─────────────────────────────────────────────────
    stt = SecureDeepgramSTTService(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_STT_MODEL,
        language="en-US",
        audio_passthrough=False,  # Block user audio from reaching output
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
    context = OpenAILLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    context_aggregator = llm.create_context_aggregator(context)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    pipeline = Pipeline(
        [
            transport.input(),  # WebRTC mic audio in
            stt,  # Audio → text (Deepgram)
            context_aggregator.user(),  # Accumulate user speech turn
            llm,  # Text → LLM response (Groq)
            context_aggregator.assistant(),  # Record assistant response
            tts,  # LLM text → audio (Deepgram)
            transport.output(),  # Audio → WebRTC speaker out
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

    runner = PipelineRunner(handle_sigint=False)

    log.info("Pipeline ready.")
    return runner, task
