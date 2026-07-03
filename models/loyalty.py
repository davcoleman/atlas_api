from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class LoyaltyTransactionType(str, enum.Enum):
    earn = "earn"
    redeem = "redeem"
    bonus = "bonus"
    referral_reward = "referral_reward"
    expiry = "expiry"


class ReferralStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    rewarded = "rewarded"
    cancelled = "cancelled"


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    transaction_type = Column(SAEnum(LoyaltyTransactionType), nullable=False)
    points = Column(Integer, nullable=False)  # positive = earn, negative = redeem
    points_balance = Column(Integer, nullable=False)  # balance after transaction

    description = Column(String(500), nullable=True)
    reference_type = Column(String(50), nullable=True)  # shipment, buyforme, referral
    reference_id = Column(String(100), nullable=True)

    # Monetary equivalent in GHS (1 point ≈ ₵1)
    ghs_value = Column(Float, nullable=True)

    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, nullable=False, index=True)  # user who shared code
    referee_id = Column(Integer, nullable=True, index=True)   # user who signed up
    referral_code = Column(String(20), nullable=False, index=True)

    status = Column(SAEnum(ReferralStatus), default=ReferralStatus.pending)

    # Bonuses (in GHS)
    referrer_bonus = Column(Float, default=50.0)   # ₵50 for referrer
    referee_discount = Column(Float, default=20.0)  # ₵20 discount for referee

    referrer_rewarded_at = Column(DateTime, nullable=True)
    referee_rewarded_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
