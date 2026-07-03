from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class UserType(str, enum.Enum):
    personal = "personal"
    business = "business"


class UserRole(str, enum.Enum):
    customer = "customer"
    staff = "staff"
    finance_admin = "finance_admin"
    crm_agent = "crm_agent"
    super_admin = "super_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # null for OAuth-only users
    google_id = Column(String(100), unique=True, nullable=True, index=True)
    facebook_id = Column(String(100), unique=True, nullable=True, index=True)

    user_type = Column(SAEnum(UserType), default=UserType.personal, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.customer, nullable=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    referral_code = Column(String(20), unique=True, nullable=True, index=True)
    loyalty_points = Column(Integer, default=0)

    terms_accepted_at = Column(DateTime, nullable=True)
    terms_acceptance_signature = Column(String(200), nullable=True)

    kyc_status = Column(String(50), nullable=True)         # Didit status literal
    kyc_session_id = Column(String(100), nullable=True)    # Didit session_id
    kyc_verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class DiditWebhookEvent(Base):
    """Idempotency table — one row per Didit event_id so duplicate deliveries are safe."""
    __tablename__ = "didit_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True)
    vendor_data = Column(String(100), nullable=True)
    processed_at = Column(DateTime, server_default=func.now())


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)

    business_name = Column(String(300), nullable=True)
    business_type = Column(String(100), nullable=True)  # Online Seller, Retail Shop, Importer, etc.
    contact_number = Column(String(30), nullable=True)
    business_address = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    business_id = Column(String(100), nullable=True)
    tax_number = Column(String(100), nullable=True)

    # Auto-tagging
    discount_eligible = Column(Boolean, default=False)
    profile_completeness = Column(Integer, default=0)  # 0-100

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
