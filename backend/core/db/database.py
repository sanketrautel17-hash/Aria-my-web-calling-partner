"""
Aria — MongoDB connection layer.

Uses Aria's Atlas connection string (MONGO_DB from .env).
Both web calls and phone calls write to the same collections,
distinguished only by a 'source' field ('web' | 'phone').

Collections:
  - calls          : all call sessions (web + phone)
  - loan_interests : flagged interested leads from phone calls
  - leads          : manually submitted lead forms
"""

from motor.motor_asyncio import AsyncIOMotorClient
from commons.logger import logger
from core.config import settings

log = logger(__name__)

# ── Shared client state ───────────────────────────────────────────────────────


class _Database:
    client: AsyncIOMotorClient = None


_db = _Database()

# ── Lifecycle ─────────────────────────────────────────────────────────────────


async def connect_to_mongo():
    """Open the MongoDB connection. Call on app startup."""
    try:
        _db.client = AsyncIOMotorClient(settings.MONGO_DB)
        # Verify connection with a lightweight ping
        await _db.client.admin.command("ping")
        log.info("✅ Connected to MongoDB Atlas (Aria DB)")
    except Exception as e:
        log.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close the MongoDB connection. Call on app shutdown."""
    try:
        if _db.client:
            _db.client.close()
            log.info("🔌 MongoDB connection closed")
    except Exception as e:
        log.error(f"Error closing MongoDB connection: {e}")


# ── Accessor ──────────────────────────────────────────────────────────────────


def get_database():
    """
    Return the Aria database instance.
    Database name is derived from the Atlas connection string app name.
    Falls back to 'aria_db' if not determinable.
    """
    if _db.client is None:
        raise RuntimeError(
            "MongoDB is not connected. Ensure connect_to_mongo() was called at startup."
        )
    return _db.client["aria_db"]
