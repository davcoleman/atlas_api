from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.loyalty import LoyaltyTransaction, LoyaltyTransactionType, Referral, ReferralStatus
from models.users import User


POINTS_PER_GHS = 1       # 1 point per ₵100 → ₵100 = 1 point; so 1 GHS = 0.01 points
GHS_PER_100 = 100.0      # earn 1 point per ₵100 spent


def _tier(points: int) -> str:
    if points >= 5000:
        return "Platinum"
    if points >= 2000:
        return "Gold"
    if points >= 500:
        return "Silver"
    return "Bronze"


def earn_points(
    db: Session,
    user_id: int,
    ghs_spent: float,
    reference_type: str,
    reference_id: str,
    description: str = "",
) -> LoyaltyTransaction:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    points = int(ghs_spent / GHS_PER_100)
    if points <= 0:
        return None

    new_balance = user.loyalty_points + points
    txn = LoyaltyTransaction(
        user_id=user_id,
        transaction_type=LoyaltyTransactionType.earn,
        points=points,
        points_balance=new_balance,
        description=description or f"Earned {points} pts for spend of ₵{ghs_spent:.2f}",
        reference_type=reference_type,
        reference_id=reference_id,
        ghs_value=float(points),
    )
    user.loyalty_points = new_balance
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def redeem_points(db: Session, user_id: int, points: int, description: str = "") -> LoyaltyTransaction:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.loyalty_points < points:
        raise HTTPException(status_code=400, detail="Insufficient loyalty points")

    new_balance = user.loyalty_points - points
    txn = LoyaltyTransaction(
        user_id=user_id,
        transaction_type=LoyaltyTransactionType.redeem,
        points=-points,
        points_balance=new_balance,
        description=description or f"Redeemed {points} points",
        ghs_value=float(points),
    )
    user.loyalty_points = new_balance
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def add_bonus_points(db: Session, user_id: int, points: int, description: str) -> LoyaltyTransaction:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    new_balance = user.loyalty_points + points
    txn = LoyaltyTransaction(
        user_id=user_id,
        transaction_type=LoyaltyTransactionType.bonus,
        points=points,
        points_balance=new_balance,
        description=description,
        ghs_value=float(points),
    )
    user.loyalty_points = new_balance
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def get_loyalty_summary(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    txns = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.user_id == user_id
    ).order_by(LoyaltyTransaction.created_at.desc()).all()

    return {
        "user_id": user_id,
        "total_points": user.loyalty_points,
        "redeemable_points": user.loyalty_points,
        "ghs_value": float(user.loyalty_points),
        "tier": _tier(user.loyalty_points),
        "transactions": txns,
    }


def apply_referral(db: Session, new_user_id: int, referral_code: str) -> bool:
    referrer = db.query(User).filter(User.referral_code == referral_code).first()
    if not referrer or referrer.id == new_user_id:
        return False

    existing = db.query(Referral).filter(Referral.referee_id == new_user_id).first()
    if existing:
        return False

    referral = Referral(
        referrer_id=referrer.id,
        referee_id=new_user_id,
        referral_code=referral_code,
        status=ReferralStatus.pending,
    )
    db.add(referral)
    db.commit()
    return True


def complete_referral(db: Session, referee_id: int):
    from datetime import datetime
    referral = db.query(Referral).filter(
        Referral.referee_id == referee_id,
        Referral.status == ReferralStatus.pending,
    ).first()
    if not referral:
        return

    referral.status = ReferralStatus.rewarded

    # Credit referrer wallet bonus (₵50)
    from services.wallet_service import credit_bonus
    credit_bonus(db, referral.referrer_id, referral.referrer_bonus,
                 f"Referral bonus for inviting user #{referee_id}")
    referral.referrer_rewarded_at = datetime.utcnow()

    # Credit referee wallet discount (₵20)
    credit_bonus(db, referral.referee_id, referral.referee_discount,
                 "Welcome discount from referral signup")
    referral.referee_rewarded_at = datetime.utcnow()

    db.commit()
