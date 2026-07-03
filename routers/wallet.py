import stripe
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db, settings
from schemas.wallet import (
    WalletOut, DepositRequest, WalletTransactionOut,
    WalletSummary, AdminDepositApproval, AdminBalanceAdjust,
    StripeSessionRequest, StripeSessionOut,
    AdminWalletTransactionOut, AdminWalletStats,
)
from dependencies import get_current_user, require_admin
from models.users import User
from models.wallet import Wallet, WalletTransaction, TransactionType, TransactionStatus, PaymentMethod
from services import wallet_service
from services.notification_service import notify_payment_completed, notify_deposit_approved

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/", response_model=WalletSummary)
def get_wallet(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    summary = wallet_service.get_wallet_summary(db, current_user.id)
    return summary


@router.get("/balance", response_model=WalletOut)
def get_balance(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return wallet_service.get_or_create_wallet(db, current_user.id)


@router.post("/deposit", response_model=WalletTransactionOut, status_code=201)
def deposit(
    body: DepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = wallet_service.deposit(
        db,
        current_user.id,
        body.amount,
        body.payment_method,
        external_reference=body.external_reference,
        description=body.description,
        auto_approve=False,  # requires admin approval
    )
    return txn


@router.get("/transactions", response_model=List[WalletTransactionOut])
def get_transactions(
    transaction_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(WalletTransaction).filter(WalletTransaction.user_id == current_user.id)
    if transaction_type:
        q = q.filter(WalletTransaction.transaction_type == transaction_type)
    if status:
        q = q.filter(WalletTransaction.status == status)
    return q.order_by(WalletTransaction.created_at.desc()).offset(skip).limit(limit).all()


# Admin endpoints
@router.get("/admin/pending-deposits", response_model=List[AdminWalletTransactionOut])
def list_pending_deposits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rows = db.query(WalletTransaction, User).join(User, User.id == WalletTransaction.user_id).filter(
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).order_by(WalletTransaction.created_at.desc()).all()

    results = []
    for txn, user in rows:
        item = AdminWalletTransactionOut.model_validate(txn)
        item.customer_name = user.full_name
        item.customer_email = user.email
        results.append(item)
    return results


@router.post("/admin/approve-deposit", response_model=WalletTransactionOut)
def approve_deposit(
    body: AdminDepositApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if body.action == "approve":
        txn = wallet_service.approve_deposit(db, body.transaction_id, current_user.id)
        wallet = wallet_service.get_or_create_wallet(db, txn.user_id)
        notify_deposit_approved(db, txn.user_id, txn.amount, wallet.balance)
        notify_payment_completed(db, txn.user_id, txn.amount)
    else:
        txn = wallet_service.reject_deposit(db, body.transaction_id, current_user.id)
    return txn


@router.post("/admin/adjust", response_model=WalletTransactionOut)
def admin_adjust_balance(
    body: AdminBalanceAdjust,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if body.transaction_type == TransactionType.refund:
        txn = wallet_service.refund(db, body.user_id, body.amount, body.description, current_user.id)
    elif body.transaction_type == TransactionType.bonus:
        txn = wallet_service.credit_bonus(db, body.user_id, body.amount, body.description)
    elif body.transaction_type == TransactionType.deduction:
        txn = wallet_service.deduct(db, body.user_id, body.amount, body.description)
    else:
        txn = wallet_service.deposit(db, body.user_id, body.amount,
                                     "manual", description=body.description, auto_approve=True)
    return txn


@router.get("/admin/ledger", response_model=List[AdminWalletTransactionOut])
def admin_ledger(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    transaction_type: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    q = db.query(WalletTransaction, User).join(User, User.id == WalletTransaction.user_id)

    if user_id:
        q = q.filter(WalletTransaction.user_id == user_id)
    if status:
        q = q.filter(WalletTransaction.status == status)
    if transaction_type:
        q = q.filter(WalletTransaction.transaction_type == transaction_type)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            User.full_name.ilike(like),
            User.email.ilike(like),
            WalletTransaction.reference.ilike(like),
        ))

    rows = q.order_by(WalletTransaction.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for txn, user in rows:
        item = AdminWalletTransactionOut.model_validate(txn)
        item.customer_name = user.full_name
        item.customer_email = user.email
        results.append(item)
    return results


@router.get("/admin/stats", response_model=AdminWalletStats)
def admin_wallet_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    def _sum(t_type, t_status=TransactionStatus.completed, start=None, end=None):
        q = db.query(func.sum(WalletTransaction.amount)).filter(
            WalletTransaction.transaction_type == t_type,
            WalletTransaction.status == t_status,
        )
        if start:
            q = q.filter(WalletTransaction.created_at >= start)
        if end:
            q = q.filter(WalletTransaction.created_at < end)
        return q.scalar() or 0.0

    total_deposits = _sum(TransactionType.deposit)
    total_deductions = _sum(TransactionType.deduction)
    total_refunds = _sum(TransactionType.refund)

    pending_count = db.query(func.count(WalletTransaction.id)).filter(
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).scalar() or 0

    pending_amount = _sum(TransactionType.deposit, TransactionStatus.pending)
    total_wallet_balance = db.query(func.sum(Wallet.balance)).scalar() or 0.0

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    deposits_this_month = _sum(TransactionType.deposit, start=month_start)
    deposits_last_month = _sum(TransactionType.deposit, start=prev_month_start, end=month_start)
    deposits_change = (
        (deposits_this_month - deposits_last_month) / deposits_last_month * 100
    ) if deposits_last_month else 0.0

    return AdminWalletStats(
        total_deposits=round(total_deposits, 2),
        total_deductions=round(total_deductions, 2),
        total_refunds=round(total_refunds, 2),
        pending_count=pending_count,
        pending_amount=round(pending_amount, 2),
        total_wallet_balance=round(total_wallet_balance, 2),
        deposits_change_pct=round(deposits_change, 2),
    )


# ── Stripe endpoints ──────────────────────────────────────────────────────────

def _configure_stripe():
    """Set API key + disable SSL verification (dev machine cert issue)."""
    stripe.api_key = settings.stripe_secret_key
    stripe.verify_ssl_certs = False


def _stripe_configured() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_secret_key.startswith("sk_"))


@router.post("/stripe/create-session", response_model=StripeSessionOut)
def create_stripe_session(
    body: StripeSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _stripe_configured():
        raise HTTPException(503, "Stripe is not configured on this server")
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    _configure_stripe()

    # Create a pending deposit transaction to record intent
    txn = wallet_service.deposit(
        db,
        current_user.id,
        body.amount,
        PaymentMethod.visa_mastercard,
        description="Stripe card payment",
        auto_approve=False,
    )

    currency = settings.stripe_currency.lower()
    # Stripe amounts are in smallest currency unit (cents for USD/GBP, pesewas for GHS)
    unit_amount = int(body.amount * 100)

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": currency,
                "product_data": {
                    "name": "Atlas Freight Wallet Top-Up",
                    "description": f"Ref: {txn.reference}",
                },
                "unit_amount": unit_amount,
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata={
            "transaction_id": str(txn.id),
            "user_id": str(current_user.id),
        },
        success_url=(
            f"{settings.frontend_url}/wallet"
            f"?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        cancel_url=f"{settings.frontend_url}/wallet?payment=cancelled",
    )

    return StripeSessionOut(
        session_id=session.id,
        session_url=session.url,
        transaction_id=txn.id,
    )


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Stripe sends POST with raw body + Stripe-Signature header.
    No JWT auth — identity is verified via webhook signature.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Webhook secret not configured")

    try:
        _configure_stripe()
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(400, "Invalid Stripe webhook signature")
    except Exception as exc:
        raise HTTPException(400, f"Webhook error: {exc}")

    if event.type == "checkout.session.completed":
        session_obj = event.data.object
        if session_obj.payment_status != "paid":
            return {"status": "ignored"}

        txn_id = int(session_obj.metadata["transaction_id"])
        txn = db.query(WalletTransaction).filter(WalletTransaction.id == txn_id).first()

        if txn and txn.status == TransactionStatus.pending:
            wallet = wallet_service.get_or_create_wallet(db, txn.user_id)
            wallet.balance += txn.amount
            txn.balance_after = wallet.balance
            txn.status = TransactionStatus.completed
            txn.external_reference = session_obj.id
            db.commit()
            notify_deposit_approved(db, txn.user_id, txn.amount, wallet.balance)

    return {"status": "ok"}


@router.get("/stripe/verify/{session_id}")
def verify_stripe_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Called by the frontend after Stripe redirects back with ?payment=success.
    Acts as a fallback in case the webhook hasn't fired yet.
    """
    if not _stripe_configured():
        raise HTTPException(503, "Stripe is not configured")

    _configure_stripe()
    try:
        session_obj = stripe.checkout.Session.retrieve(session_id)
    except stripe.InvalidRequestError:
        raise HTTPException(404, "Stripe session not found")

    if session_obj.payment_status != "paid":
        return {"status": session_obj.payment_status, "amount": 0}

    txn_id_str = (session_obj.metadata or {}).get("transaction_id")
    if not txn_id_str:
        raise HTTPException(400, "Session missing transaction metadata")

    txn = db.query(WalletTransaction).filter(
        WalletTransaction.id == int(txn_id_str),
        WalletTransaction.user_id == current_user.id,
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")

    # Idempotent: only credit if still pending
    if txn.status == TransactionStatus.pending:
        wallet = wallet_service.get_or_create_wallet(db, txn.user_id)
        wallet.balance += txn.amount
        txn.balance_after = wallet.balance
        txn.status = TransactionStatus.completed
        txn.external_reference = session_obj.id
        db.commit()
        db.refresh(txn)
        notify_deposit_approved(db, txn.user_id, txn.amount, wallet.balance)

    return {"status": "paid", "amount": txn.amount, "currency": txn.currency}
