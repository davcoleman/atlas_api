from datetime import datetime, timedelta
from typing import Optional
import random
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import secrets
import string

from database import settings
from models.users import User, BusinessProfile, UserType, UserRole, EmailOTP

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["type"] = "access"
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_referral_code(full_name: str) -> str:
    prefix = "ATLAS"
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}{suffix}"


def compute_profile_completeness(profile: BusinessProfile) -> int:
    fields = [
        profile.business_name,
        profile.business_type,
        profile.contact_number,
        profile.business_address,
        profile.logo_url,
        profile.business_id,
        profile.tax_number,
    ]
    filled = sum(1 for f in fields if f)
    return int((filled / len(fields)) * 100)


def register_user(db: Session, full_name: str, email: str, password: str, user_type: UserType) -> User:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        user_type=user_type,
        role=UserRole.customer,
        referral_code=generate_referral_code(full_name),
        is_verified=False,
    )
    db.add(user)
    db.flush()

    if user_type == UserType.business:
        profile = BusinessProfile(user_id=user.id, profile_completeness=0)
        db.add(profile)

    _create_wallet_for_user(db, user.id)

    db.commit()
    db.refresh(user)
    return user


def register_google_user(db: Session, google_id: str, email: str, full_name: str, user_type: UserType) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.google_id:
            user.google_id = google_id
            db.commit()
        return user

    user = User(
        full_name=full_name,
        email=email,
        google_id=google_id,
        user_type=user_type,
        role=UserRole.customer,
        referral_code=generate_referral_code(full_name),
        is_verified=True,
    )
    db.add(user)
    db.flush()

    if user_type == UserType.business:
        profile = BusinessProfile(user_id=user.id, profile_completeness=0)
        db.add(profile)

    _create_wallet_for_user(db, user.id)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user


def build_tokens(user: User) -> dict:
    data = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    return {
        "access_token": create_access_token(data),
        "refresh_token": create_refresh_token(data),
        "token_type": "bearer",
    }


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _create_wallet_for_user(db: Session, user_id: int):
    from models.wallet import Wallet
    wallet = Wallet(user_id=user_id, balance=0.0, currency="GHS")
    db.add(wallet)


# ── OTP helpers ───────────────────────────────────────────────────────────────

OTP_EXPIRY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60


def generate_otp(db: Session, email: str) -> str:
    """Invalidate any existing unused OTPs for this email and create a fresh one."""
    # Mark old ones as used
    db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.used == False,  # noqa: E712
    ).update({"used": True})

    code = f"{random.randint(0, 999999):06d}"
    otp = EmailOTP(
        email=email,
        otp_code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        used=False,
    )
    db.add(otp)
    db.commit()
    return code


def can_resend_otp(db: Session, email: str) -> bool:
    """True if no OTP was sent in the last 60 seconds."""
    cutoff = datetime.utcnow() - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
    recent = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.created_at >= cutoff,
    ).first()
    return recent is None


def verify_otp(db: Session, email: str, code: str) -> bool:
    """Returns True and marks OTP used if valid; raises HTTPException otherwise."""
    otp = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.otp_code == code,
        EmailOTP.used == False,  # noqa: E712
    ).order_by(EmailOTP.created_at.desc()).first()

    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    if datetime.utcnow() > otp.expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired")

    otp.used = True
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.is_verified = True
        user.email_verified_at = datetime.utcnow()
    db.commit()
    return True
