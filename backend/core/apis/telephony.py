"""
Aria — Telephony Router  (Phase 4: Telephony Bridge)

Endpoints:
  POST /api/telephony/dialout         → Initiate an outbound Twilio call
  POST /api/telephony/twiml           → Return TwiML to connect call to WebSocket
  WS   /api/telephony/ws              → Twilio Media Streams WebSocket (phone AI pipeline)
  GET  /api/telephony/calls           → List all call sessions (web + phone)
  POST /api/telephony/submit-lead     → Submit a lead form

All phone call audio is routed through the same AI pipeline as web calls
(Deepgram STT → Groq LLM → Deepgram TTS), using the unified Loan Assistant
persona defined in core/prompt.py.

Call records are stored in Aria's MongoDB `calls` collection and distinguished
from web call records by the `source: "phone"` field.
"""

import json

from fastapi import APIRouter, Request, Response, WebSocket, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

from core.config import settings
from core.pipeline import phone_bot
from core.db.database import get_database
from commons.logger import logger

log = logger(__name__)

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/telephony", tags=["Telephony"])

# ── Twilio client (lazy — only fails if keys are missing at call time) ────────
def _twilio_client() -> Client:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Twilio credentials not configured in .env",
        )
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _stream_url() -> str:
    """Build the WSS URL Twilio will connect to for Media Streams."""
    if not settings.PUBLIC_URL:
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_URL not set in .env — required for Twilio webhooks",
        )
    base = settings.PUBLIC_URL.replace("https://", "").replace("http://", "")
    return f"wss://{base}/api/telephony/ws"


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class DialoutRequest(BaseModel):
    to_number: str


class DialoutResponse(BaseModel):
    call_sid: str
    status: str
    to_number: str


class LeadSubmission(BaseModel):
    firstName: str = Field(..., description="First name of the lead")
    lastName: str = Field(..., description="Last name of the lead")
    phone: str = Field(..., description="Phone number of the lead")
    email: str = Field(..., description="Email address of the lead")


# ── Helper ────────────────────────────────────────────────────────────────────
def _serialize_doc(doc: dict) -> dict:
    """Convert MongoDB ObjectId to string for JSON serialisation."""
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/dialout", response_model=DialoutResponse)
async def dialout(request: DialoutRequest):
    """
    Initiate an outbound Twilio call to `to_number`.
    Twilio will GET/POST /api/telephony/twiml to get the call instructions,
    which will connect the call to /api/telephony/ws for real-time audio.
    """
    stream_url = _stream_url()
    client = _twilio_client()

    # Build TwiML inline so we avoid an extra HTTP round-trip
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=stream_url)
    stream.parameter(name="to_number", value=request.to_number)
    response.append(connect)

    log.info(f"Initiating outbound call to {request.to_number} | stream={stream_url}")

    try:
        call = client.calls.create(
            to=request.to_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            twiml=str(response),
        )
    except Exception as e:
        log.error(f"Twilio call initiation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {e}")

    log.info(f"Call initiated: call_sid={call.sid}")
    return DialoutResponse(
        call_sid=call.sid,
        status="call_initiated",
        to_number=request.to_number,
    )


@router.post("/twiml")
async def get_twiml():
    """
    Return TwiML instructions to Twilio when it connects the phone call.
    Twilio will connect the call audio to /api/telephony/ws.
    """
    stream_url = _stream_url()
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/ws")
async def telephony_websocket(websocket: WebSocket):
    """
    Twilio Media Streams WebSocket endpoint.

    Flow:
      1. Accept connection
      2. Wait for Twilio's 'connected' then 'start' events to get stream/call SIDs
      3. Hand off to phone_bot() — the Pipecat AI pipeline
    """
    await websocket.accept()
    log.info("📞 Twilio Media Streams WebSocket connected")

    stream_sid: str = ""
    call_sid: str = ""

    try:
        # Step 1 — Wait for Twilio's handshake events
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event", "")

            if event == "connected":
                log.info("Twilio: received 'connected' event")
                continue
            elif event == "start":
                start = msg["start"]
                stream_sid = start["streamSid"]
                call_sid = start["callSid"]
                custom_params = start.get("customParameters", {})
                log.info(
                    f"Twilio: stream started | stream_sid={stream_sid} "
                    f"call_sid={call_sid} params={custom_params}"
                )
                break
            else:
                log.warning(f"Unexpected Twilio event before start: {event}")

        # Step 2 — Hand off to the AI pipeline
        await phone_bot(websocket, stream_sid, call_sid)

    except Exception as e:
        log.error(f"Telephony WebSocket error: {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        log.info(f"📞 Telephony WebSocket closed | call_sid={call_sid}")


@router.get("/calls")
async def list_calls(limit: int = 50):
    """
    Return recent call sessions (web + phone) from Aria's unified DB,
    most recent first.  Each record includes a `source` field ('web' | 'phone').
    """
    db = get_database()
    cursor = db["calls"].find().sort("start_time", -1).limit(limit)
    calls = await cursor.to_list(length=limit)
    return [_serialize_doc(call) for call in calls]


@router.post("/submit-lead")
async def submit_lead(lead: LeadSubmission):
    """Save a manually-submitted lead form to Aria's `leads` collection."""
    try:
        db = get_database()
        result = await db["leads"].insert_one(lead.dict())
        return {
            "status": "success",
            "message": "Lead submitted successfully",
            "id": str(result.inserted_id),
        }
    except Exception as e:
        log.error(f"Failed to submit lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to save lead")
