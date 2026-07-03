from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.loyalty import (
    LoyaltySummary, LoyaltyTransactionOut, RedeemPointsRequest,
    ReferralOut, ReferralStats,
)
from dependencies import get_current_user
from models.users import User
from models.loyalty import Referral, LoyaltyTransaction
from services.loyalty_service import (
    get_loyalty_summary, redeem_points, apply_referral, complete_referral,
)

router = APIRouter(prefix="/loyalty", tags=["Loyalty & Referrals"])


@router.get("/", response_model=LoyaltySummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_loyalty_summary(db, current_user.id)


@router.post("/redeem", response_model=LoyaltyTransactionOut)
def redeem(
    body: RedeemPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = redeem_points(db, current_user.id, body.points, body.description)
    if not txn:
        raise HTTPException(status_code=400, detail="Redemption failed")
    # Credit GHS value to wallet
    from services.wallet_service import credit_bonus
    credit_bonus(db, current_user.id, float(body.points), f"Points redeemed: {body.points} pts")
    return txn


@router.get("/referrals", response_model=ReferralStats)
def get_referral_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    referrals = db.query(Referral).filter(Referral.referrer_id == current_user.id).all()
    total_bonus = sum(r.referrer_bonus for r in referrals if r.referrer_rewarded_at)
    return {
        "referral_code": current_user.referral_code or "",
        "total_referrals": len(referrals),
        "completed_referrals": sum(1 for r in referrals if r.referrer_rewarded_at),
        "total_bonus_earned": total_bonus,
        "referrals": referrals,
    }


@router.post("/referrals/apply")
def apply_referral_code(
    referral_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    applied = apply_referral(db, current_user.id, referral_code.upper())
    if not applied:
        raise HTTPException(status_code=400, detail="Invalid referral code or already applied")
    complete_referral(db, current_user.id)
    return {"message": f"Referral code applied. Bonuses have been credited to both accounts."}


@router.get("/transactions", response_model=List[LoyaltyTransactionOut])
def get_transactions(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.user_id == current_user.id
    ).order_by(LoyaltyTransaction.created_at.desc()).offset(skip).limit(limit).all()
