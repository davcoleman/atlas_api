from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from database import get_db
from schemas.users import (
    UserRegister, UserLogin, GoogleAuthRequest, TokenResponse,
    RefreshRequest, UserOut,
    OTPSendResponse, OTPVerifyRequest, OTPResendRequest, AcceptTermsRequest,
)
from services import auth_service
from services.email_service import send_otp_email
from services.notification_service import notify_welcome
from services.loyalty_service import apply_referral
from dependencies import get_current_user
from models.users import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=OTPSendResponse, status_code=201)
def register(body: UserRegister, db: Session = Depends(get_db)):
    """Create account (unverified) and send OTP email."""
    user = auth_service.register_user(db, body.full_name, body.email, body.password, body.user_type)
    notify_welcome(db, user.id, user.full_name)
    otp_code = auth_service.generate_otp(db, body.email)
    send_otp_email(body.email, body.full_name, otp_code)
    return {"message": "Verification code sent to your email", "email": body.email}


@router.post("/register-with-referral", response_model=OTPSendResponse, status_code=201)
def register_with_referral(
    body: UserRegister,
    referral_code: str,
    db: Session = Depends(get_db),
):
    user = auth_service.register_user(db, body.full_name, body.email, body.password, body.user_type)
    notify_welcome(db, user.id, user.full_name)
    applied = apply_referral(db, user.id, referral_code.upper())
    if applied:
        from services.loyalty_service import complete_referral
        complete_referral(db, user.id)
    otp_code = auth_service.generate_otp(db, body.email)
    send_otp_email(body.email, body.full_name, otp_code)
    return {"message": "Verification code sent to your email", "email": body.email}


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(body: OTPVerifyRequest, db: Session = Depends(get_db)):
    """Verify the OTP; on success return JWT tokens."""
    auth_service.verify_otp(db, body.email, body.otp_code)
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    tokens = auth_service.build_tokens(user)
    return {**tokens, "user": user}


@router.post("/resend-otp", response_model=OTPSendResponse)
def resend_otp(body: OTPResendRequest, db: Session = Depends(get_db)):
    """Resend OTP (rate-limited to once per 60 s)."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account with that email")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    if not auth_service.can_resend_otp(db, body.email):
        raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting a new code")
    otp_code = auth_service.generate_otp(db, body.email)
    send_otp_email(body.email, user.full_name, otp_code)
    return {"message": "A new verification code has been sent", "email": body.email}


@router.patch("/accept-terms", response_model=UserOut)
def accept_terms(
    body: AcceptTermsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record terms acceptance with the customer's typed signature."""
    if not body.signature.strip():
        raise HTTPException(status_code=400, detail="Signature cannot be empty")
    current_user.terms_accepted_at = datetime.utcnow()
    current_user.terms_acceptance_signature = body.signature.strip()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, body.email, body.password)
    tokens = auth_service.build_tokens(user)
    return {**tokens, "user": user}


@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Exchange a Google ID token from the frontend for Atlas JWT tokens."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": body.id_token},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            data = resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Could not verify Google token")

    google_id = data.get("sub")
    email = data.get("email")
    full_name = data.get("name", email)

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Missing fields in Google token")

    user = auth_service.register_google_user(db, google_id, email, full_name, body.user_type)
    tokens = auth_service.build_tokens(user)
    return {**tokens, "user": user}


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = auth_service.decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Not a refresh token")
    user_id = int(payload["sub"])
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tokens = auth_service.build_tokens(user)
    return {**tokens, "user": user}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
