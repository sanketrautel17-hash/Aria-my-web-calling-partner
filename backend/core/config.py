"""
Application configuration using pydantic-settings.
All values come from the .env file or environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── API Keys ──────────────────────────────────────────────────────────────
    DEEPGRAM_API_KEY: str
    GROQ_API_KEY: str

    # ── LLM ───────────────────────────────────────────────────────────────────
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # ── Deepgram ──────────────────────────────────────────────────────────────
    DEEPGRAM_STT_MODEL: str = "nova-2"
    DEEPGRAM_TTS_MODEL: str = "aura-asteria-en"  # Natural female voice

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
