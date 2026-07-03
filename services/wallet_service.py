import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.wallet import Wallet, WalletTransaction, TransactionType, TransactionStatus, PaymentMethod


def get_or_create_wallet(db: Session, user_id: int) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        wallet = Wallet(user_id=user_id, balance=0.0, currency="GHS")
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def _generate_ref() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


def deposit(
    db: Session,
    user_id: int,
    amount: float,
    payment_method: PaymentMethod,
    external_reference: Optional[str] = None,
    description: Optional[str] = None,
    auto_approve: bool = False,
) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    wallet = get_or_create_wallet(db, user_id)
    status = TransactionStatus.completed if auto_approve else TransactionStatus.pending
    balance_after = wallet.balance + amount if auto_approve else wallet.balance

    txn = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type=TransactionType.deposit,
        amount=amount,
        currency=wallet.currency,
        balance_before=wallet.balance,
        balance_after=balance_after,
        status=status,
        payment_method=payment_method,
        reference=_generate_ref(),
        external_reference=external_reference,
        description=description or "Wallet deposit",
    )
    if auto_approve:
        wallet.balance = balance_after

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def approve_deposit(db: Session, transaction_id: int, admin_id: int) -> WalletTransaction:
    txn = db.query(WalletTransaction).filter(
        WalletTransaction.id == transaction_id,
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Pending deposit transaction not found")

    wallet = db.query(Wallet).filter(Wallet.id == txn.wallet_id).first()
    wallet.balance += txn.amount
    txn.balance_after = wallet.balance
    txn.status = TransactionStatus.completed
    txn.approved_by = admin_id

    db.commit()
    db.refresh(txn)
    return txn


def reject_deposit(db: Session, transaction_id: int, admin_id: int) -> WalletTransaction:
    txn = db.query(WalletTransaction).filter(
        WalletTransaction.id == transaction_id,
        WalletTransaction.status == TransactionStatus.pending,
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    txn.status = TransactionStatus.cancelled
    txn.approved_by = admin_id
    db.commit()
    db.refresh(txn)
    return txn


def deduct(
    db: Session,
    user_id: int,
    amount: float,
    description: str,
    shipment_id: Optional[int] = None,
) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    wallet = get_or_create_wallet(db, user_id)
    if wallet.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    balance_after = wallet.balance - amount
    txn = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type=TransactionType.deduction,
        amount=amount,
        currency=wallet.currency,
        balance_before=wallet.balance,
        balance_after=balance_after,
        status=TransactionStatus.completed,
        payment_method=PaymentMethod.wallet,
        reference=_generate_ref(),
        description=description,
        shipment_id=shipment_id,
    )
    wallet.balance = balance_after
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def refund(
    db: Session,
    user_id: int,
    amount: float,
    description: str,
    admin_id: Optional[int] = None,
) -> WalletTransaction:
    wallet = get_or_create_wallet(db, user_id)
    balance_after = wallet.balance + amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type=TransactionType.refund,
        amount=amount,
        currency=wallet.currency,
        balance_before=wallet.balance,
        balance_after=balance_after,
        status=TransactionStatus.completed,
        payment_method=PaymentMethod.manual,
        reference=_generate_ref(),
        description=description,
        approved_by=admin_id,
    )
    wallet.balance = balance_after
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def credit_bonus(db: Session, user_id: int, amount: float, description: str) -> WalletTransaction:
    wallet = get_or_create_wallet(db, user_id)
    balance_after = wallet.balance + amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type=TransactionType.bonus,
        amount=amount,
        currency=wallet.currency,
        balance_before=wallet.balance,
        balance_after=balance_after,
        status=TransactionStatus.completed,
        payment_method=PaymentMethod.manual,
        reference=_generate_ref(),
        description=description,
    )
    wallet.balance = balance_after
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def get_wallet_summary(db: Session, user_id: int) -> dict:
    from sqlalchemy import func
    wallet = get_or_create_wallet(db, user_id)
    txns = db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id)

    total_deposits = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == user_id,
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.completed,
    ).scalar() or 0.0

    total_deductions = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == user_id,
        WalletTransaction.transaction_type == TransactionType.deduction,
        WalletTransaction.status == TransactionStatus.completed,
    ).scalar() or 0.0

    total_refunds = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == user_id,
        WalletTransaction.transaction_type == TransactionType.refund,
        WalletTransaction.status == TransactionStatus.completed,
    ).scalar() or 0.0

    pending_deposits = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == user_id,
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).scalar() or 0.0

    recent = txns.order_by(WalletTransaction.created_at.desc()).limit(10).all()

    return {
        "wallet": wallet,
        "total_deposits": total_deposits,
        "total_deductions": total_deductions,
        "total_refunds": total_refunds,
        "pending_deposits": pending_deposits,
        "recent_transactions": recent,
    }
