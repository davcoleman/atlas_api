from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from models.users import UserType, UserRole


class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    user_type: UserType = UserType.personal

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    user_type: UserType = UserType.personal


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    user_type: UserType
    role: UserRole
    is_active: bool
    is_verified: bool
    referral_code: Optional[str] = None
    loyalty_points: int
    kyc_status: Optional[str] = None
    kyc_session_id: Optional[str] = None
    kyc_verified_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KycSessionOut(BaseModel):
    url: str
    session_id: str
    kyc_status: Optional[str] = None


class KycStatusOut(BaseModel):
    kyc_status: Optional[str] = None
    kyc_session_id: Optional[str] = None
    kyc_verified_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class BusinessProfileCreate(BaseModel):
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    contact_number: Optional[str] = None
    business_address: Optional[str] = None
    logo_url: Optional[str] = None
    business_id: Optional[str] = None
    tax_number: Optional[str] = None


class BusinessProfileOut(BaseModel):
    id: int
    user_id: int
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    contact_number: Optional[str] = None
    business_address: Optional[str] = None
    logo_url: Optional[str] = None
    business_id: Optional[str] = None
    tax_number: Optional[str] = None
    discount_eligible: bool
    profile_completeness: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    user_type: Optional[UserType] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class AdminRoleUpdate(BaseModel):
    role: UserRole


class OTPSendResponse(BaseModel):
    message: str
    email: str


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str


class OTPResendRequest(BaseModel):
    email: EmailStr


class AcceptTermsRequest(BaseModel):
    signature: str
