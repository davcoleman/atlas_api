"""
Didit KYC integration — server-to-server REST, no SDK.

Flow:
  1. POST /kyc/create-session  (auth required) → calls Didit, returns {url, session_id}
  2. Frontend opens session.url → user completes verification → Didit redirects back
  3. POST /kyc/webhook          (no auth, raw body) → verifies HMAC, updates user status
  4. GET  /kyc/status           (auth required) → returns current KYC fields
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, settings
from dependencies import get_current_user
from models.users import DiditWebhookEvent, User
from schemas.users import KycSessionOut, KycStatusOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kyc", tags=["KYC"])

DIDIT_API_BASE = "https://verification.didit.me"
WORKFLOW_ID = "6ee4ccde-b109-42b1-89a1-dab68e8e4c8f"  # "Free KYC" — per-session config, not a secret


# ── HMAC helpers ──────────────────────────────────────────────────────────────

def _shorten_floats(v: Any) -> Any:
    """Recursively convert whole-number floats (1.0) to ints — matches Didit's canonicalisation."""
    if isinstance(v, list):
        return [_shorten_floats(x) for x in v]
    if isinstance(v, dict):
        return {k: _shorten_floats(val) for k, val in v.items()}
    if isinstance(v, float) and v % 1 == 0:
        return int(v)
    return v


def _sort_keys(v: Any) -> Any:
    """Recursively sort dict keys lexicographically; preserve array order."""
    if isinstance(v, list):
        return [_sort_keys(x) for x in v]
    if isinstance(v, dict):
        return {k: _sort_keys(v[k]) for k in sorted(v.keys())}
    return v


def _canonical(parsed: dict) -> str:
    """shortenFloats → sortKeys → compact JSON (unescaped Unicode) — mirrors JS JSON.stringify."""
    processed = _sort_keys(_shorten_floats(parsed))
    return json.dumps(processed, ensure_ascii=False, separators=(",", ":"))


def _verify_signature(raw_body: bytes, sig_header: str, ts_header: str) -> None:
    """Raise HTTPException if signature or timestamp is invalid."""
    # 1. Freshness check (±300 s replay protection)
    try:
        ts = float(ts_header)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Timestamp")
    if abs(time.time() - ts) > 300:
        raise HTTPException(status_code=401, detail="Webhook timestamp too stale")

    # 2. Canonicalise
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    canonical = _canonical(parsed)

    # 3. Constant-time HMAC-SHA256 compare vs X-Signature-V2
    expected = hmac.new(
        settings.didit_webhook_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not sig_header or len(sig_header) != len(expected) or not hmac.compare_digest(sig_header, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create-session", response_model=KycSessionOut)
async def create_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a Didit verification session server-side; return the hosted URL to the client."""
    if not settings.didit_api_key:
        raise HTTPException(status_code=503, detail="KYC service is not configured")

    callback_url = f"{settings.frontend_url}/dashboard/kyc"

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.post(
            f"{DIDIT_API_BASE}/v3/session/",
            headers={
                "x-api-key": settings.didit_api_key,
                "Content-Type": "application/json",
            },
            json={
                "workflow_id": WORKFLOW_ID,
                "vendor_data": str(current_user.id),
                "callback": callback_url,
            },
        )

    if resp.status_code not in (200, 201):
        detail = resp.text[:300]
        logger.error(f"Didit create-session failed {resp.status_code}: {detail}")
        raise HTTPException(status_code=502, detail="Could not create verification session")

    session = resp.json()
    session_id = session.get("session_id", "")
    url = session.get("url", "")
    didit_status = session.get("status", "Not Started")

    # Persist the session_id and initial status on the user
    current_user.kyc_session_id = session_id
    current_user.kyc_status = didit_status
    db.commit()

    return KycSessionOut(url=url, session_id=session_id, kyc_status=didit_status)


@router.get("/status", response_model=KycStatusOut)
def kyc_status(current_user: User = Depends(get_current_user)):
    """Return the user's current KYC status fields."""
    return KycStatusOut(
        kyc_status=current_user.kyc_status,
        kyc_session_id=current_user.kyc_session_id,
        kyc_verified_at=current_user.kyc_verified_at,
    )


@router.post("/webhook")
async def didit_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive Didit status webhooks.
    Verified with X-Signature-V2 (HMAC-SHA256 over canonical JSON body).
    """
    raw_body = await request.body()
    sig = request.headers.get("x-signature-v2", "")
    ts = request.headers.get("x-timestamp", "")

    # Skip signature check if webhook secret not configured (dev mode)
    if settings.didit_webhook_secret:
        _verify_signature(raw_body, sig, ts)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = payload.get("event_id", "")
    session_id = payload.get("session_id", "")
    status = payload.get("status", "")
    vendor_data = payload.get("vendor_data", "")

    # Idempotency — skip already-processed events
    if event_id and db.query(DiditWebhookEvent).filter(DiditWebhookEvent.event_id == event_id).first():
        return {"ok": True, "note": "already_processed"}

    # Record the event
    if event_id:
        db.add(DiditWebhookEvent(
            event_id=event_id,
            session_id=session_id,
            status=status,
            vendor_data=vendor_data,
        ))

    # Update user by vendor_data (our internal user id)
    user: User | None = None
    if vendor_data:
        try:
            user = db.query(User).filter(User.id == int(vendor_data)).first()
        except (ValueError, TypeError):
            pass

    if user:
        user.kyc_status = status
        user.kyc_session_id = session_id

        # State machine
        if status == "Approved":
            user.kyc_verified_at = datetime.utcnow()
        elif status == "Kyc Expired":
            user.kyc_verified_at = None

    db.commit()

    logger.info(f"Didit webhook processed: event_id={event_id} status={status} vendor={vendor_data}")
    return {"ok": True}
