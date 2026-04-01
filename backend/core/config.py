"""
Application configuration using pydantic-settings.
All values come from the .env file or environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── API Keys ──────────────────────────────────────────────────────────────
    DEEPGRAM_API_KEY: str
    GROQ_API_KEY: str

    # ── LLM ───────────────────────────────────────────────────────────────────
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Deepgram ──────────────────────────────────────────────────────────────
    DEEPGRAM_STT_MODEL: str = "nova-2"
    DEEPGRAM_TTS_MODEL: str = "aura-asteria-en"  # Single shared TTS voice

    # ── Database (MongoDB Atlas) ───────────────────────────────────────────────
    MONGO_DB: str  # Aria's Atlas connection string

    # ── Twilio ────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    PHONE_NO: Optional[str] = None

    # ── Public URL (ngrok / deployed server) ──────────────────────────────────
    PUBLIC_URL: Optional[str] = None

    # ── External API Keys (optional) ──────────────────────────────────────────
    TAVILY_API_KEY: Optional[str] = None
    LLAMA_CLOUD_API_KEY: Optional[str] = None

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
