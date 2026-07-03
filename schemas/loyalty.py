from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.loyalty import LoyaltyTransactionType, ReferralStatus


class LoyaltyTransactionOut(BaseModel):
    id: int
    user_id: int
    transaction_type: LoyaltyTransactionType
    points: int
    points_balance: int
    description: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    ghs_value: Optional[float] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltySummary(BaseModel):
    user_id: int
    total_points: int
    redeemable_points: int
    ghs_value: float
    tier: str  # Bronze, Silver, Gold, Platinum
    transactions: List[LoyaltyTransactionOut]


class RedeemPointsRequest(BaseModel):
    points: int
    description: Optional[str] = None


class ReferralOut(BaseModel):
    id: int
    referrer_id: int
    referee_id: Optional[int] = None
    referral_code: str
    status: ReferralStatus
    referrer_bonus: float
    referee_discount: float
    referrer_rewarded_at: Optional[datetime] = None
    referee_rewarded_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralStats(BaseModel):
    referral_code: str
    total_referrals: int
    completed_referrals: int
    total_bonus_earned: float
    referrals: List[ReferralOut]
