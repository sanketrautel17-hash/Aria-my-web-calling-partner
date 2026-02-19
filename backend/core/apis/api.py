"""
FastAPI application — WebRTC signaling using the official Pipecat SmallWebRTCRequestHandler.

Endpoints:
  GET  /                  → health check
  POST /api/offer         → SDP offer/answer exchange; starts the Pipecat pipeline
  PATCH /api/offer        → trickle ICE candidate delivery (server-side)
  GET  /docs              → FastAPI Swagger UI
"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequestHandler,
    SmallWebRTCRequest,
    SmallWebRTCPatchRequest,
    IceCandidate,
)
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

from core.pipeline import create_pipeline
from commons.logger import logger

log = logger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Aria — Voice & Chat AI Agent",
    description="Real-time voice and text AI agent powered by Pipecat, Deepgram, and Groq.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_headers(request, call_next):
    log.debug(f"Request Headers for {request.url.path}: {dict(request.headers)}")
    response = await call_next(request)
    return response


# ── Exception Handlers ────────────────────────────────────────────────────────
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    log.error(f"Validation Error {request.method} {request.url}: {exc}")

    # Sanitize errors to handle bytes
    sanitized_errors = []
    for e in exc.errors():
        e_copy = e.copy()
        if "input" in e_copy and isinstance(e_copy["input"], bytes):
            try:
                e_copy["input"] = e_copy["input"].decode("utf-8")
            except Exception:
                e_copy["input"] = str(e_copy["input"])
        sanitized_errors.append(e_copy)

    body_str = exc.body.decode() if hasattr(exc, "body") and exc.body else str(exc)

    return JSONResponse(
        status_code=422, content={"detail": sanitized_errors, "body": body_str}
    )


# ── Official Pipecat WebRTC request handler ───────────────────────────────────
_handler = SmallWebRTCRequestHandler()


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class OfferRequest(BaseModel):
    sdp: str
    type: str
    pc_id: Optional[str] = None
    restart_pc: Optional[bool] = None

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class IceCandidateSchema(BaseModel):
    candidate: str
    sdp_mid: str
    sdp_mline_index: int


class PatchRequest(BaseModel):
    pc_id: Optional[str] = None
    candidates: List[IceCandidateSchema]


class AnswerResponse(BaseModel):
    sdp: str
    type: str
    pc_id: str
    pcId: str  # Send both snake_case and camelCase to be safe
    id: str  # Potential alias
    sessionId: str  # Potential alias


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "aria-voice-chat-agent"}


@app.post("/api/offer", response_model=AnswerResponse, tags=["WebRTC"])
async def webrtc_offer(request: Request):
    """
    SDP offer → answer.  The Pipecat pipeline is started here.

    IMPORTANT: The pipeline callback is awaited INLINE (not via create_task).
    This means the connection is fully wired before we return the SDP answer,
    which prevents race conditions during ICE negotiation.
    """
    try:
        data = await request.json()
    except Exception:
        # Fallback if content-type is missing/wrong
        body_bytes = await request.body()
        import json

        data = json.loads(body_bytes)

    body = OfferRequest(**data)

    log.info(f"SDP offer received (pc_id={body.pc_id}, type={body.type})")

    req = SmallWebRTCRequest(
        sdp=body.sdp,
        type=body.type,
        pc_id=body.pc_id,
        restart_pc=body.restart_pc,
    )

    async def on_connection(connection: SmallWebRTCConnection):
        """
        Called by SmallWebRTCRequestHandler after the connection is initialized.
        Starts the Pipecat pipeline as a background task.
        """
        log.info(f"Callback on_connection triggered for {connection.pc_id}")
        log.info(f"Calling create_pipeline for {connection.pc_id}")
        try:
            runner, task = await create_pipeline(connection)
            log.info(f"create_pipeline returned successfully for {connection.pc_id}")

            async def _run():
                try:
                    log.info(f"Starting pipeline runner for {connection.pc_id}")
                    await runner.run(task)
                except Exception as exc:
                    log.error(
                        f"Pipeline error [{connection.pc_id}]: {exc}", exc_info=True
                    )
                finally:
                    log.info(f"Pipeline ended for {connection.pc_id}")

            asyncio.create_task(_run())
            log.info(f"Background task created for {connection.pc_id}")
        except Exception as e:
            log.error(f"Error in on_connection logic: {e}", exc_info=True)
            raise e

    log.info("Calling handle_web_request...")
    answer = await _handler.handle_web_request(req, on_connection)
    log.info("handle_web_request returned.")

    log.info(f"Returning SDP answer for pc_id={answer['pc_id']}")
    return AnswerResponse(
        sdp=answer["sdp"],
        type=answer["type"],
        pc_id=answer["pc_id"],
        pcId=answer["pc_id"],
        id=answer["pc_id"],
        sessionId=answer["pc_id"],
    )


@app.patch("/api/offer", tags=["WebRTC"])
async def webrtc_ice_candidates(request: Request):
    """
    Trickle ICE: browser sends individual ICE candidates after the offer.
    This is required for proper ICE connectivity even on the same machine.
    """
    try:
        data = await request.json()
    except Exception:
        body_bytes = await request.body()
        import json

        data = json.loads(body_bytes)

    body = PatchRequest(**data)

    if not body.pc_id:
        log.warning("ICE candidates received without pc_id, skipping.")
        return {"status": "ignored"}

    log.debug(
        f"ICE candidates received for pc_id={body.pc_id} ({len(body.candidates)} candidates)"
    )

    patch_request = SmallWebRTCPatchRequest(
        pc_id=body.pc_id,
        candidates=[
            IceCandidate(
                candidate=c.candidate,
                sdp_mid=c.sdp_mid,
                sdp_mline_index=c.sdp_mline_index,
            )
            for c in body.candidates
        ],
    )

    await _handler.handle_patch_request(patch_request)
    return {"status": "ok"}


@app.on_event("shutdown")
async def shutdown():
    """Clean up all active WebRTC connections on server shutdown."""
    log.info("Server shutting down — closing all WebRTC connections")
    await _handler.close()
