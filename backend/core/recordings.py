"""
Audio recording utilities for Aria.

Captures stereo WAV files (user on left channel, bot on right channel)
using the Pipecat AudioBufferProcessor and saves them to the recordings/
directory.
"""

import asyncio
import os
import wave
import datetime
from pathlib import Path
from typing import Optional

from commons.logger import logger

log = logger(__name__)

# ── Recordings directory ──────────────────────────────────────────────────────
RECORDINGS_DIR = Path(__file__).parent.parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)

SAMPLE_RATE = 16000
CHANNELS = 2  # stereo: left=user, right=bot


def get_recordings_dir() -> Path:
    return RECORDINGS_DIR


def generate_filename(pc_id: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = pc_id.replace("-", "")[:8]
    return f"session_{ts}_{safe_id}.wav"


def save_wav(filename: str, audio_bytes: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> str:
    """Write audio_bytes as a PCM16 WAV file. Returns the full path."""
    filepath = RECORDINGS_DIR / filename
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    log.info(f"Saved recording: {filepath} ({len(audio_bytes)} bytes)")
    return str(filepath)


def list_recordings() -> list[dict]:
    """Return metadata for all saved recordings, newest first."""
    recordings = []
    for f in sorted(RECORDINGS_DIR.glob("*.wav"), reverse=True):
        stat = f.stat()
        recordings.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "duration_seconds": _wav_duration(f),
        })
    return recordings


def _wav_duration(filepath: Path) -> Optional[float]:
    try:
        with wave.open(str(filepath), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return round(frames / rate, 1)
    except Exception:
        return None
