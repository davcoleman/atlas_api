from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.wallet import TransactionType, TransactionStatus, PaymentMethod


class WalletOut(BaseModel):
    id: int
    user_id: int
    balance: float
    currency: str
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class DepositRequest(BaseModel):
    amount: float
    payment_method: PaymentMethod
    external_reference: Optional[str] = None  # Paystack/Flutterwave ref
    description: Optional[str] = None


class WalletTransactionOut(BaseModel):
    id: int
    wallet_id: int
    user_id: int
    transaction_type: TransactionType
    amount: float
    currency: str
    balance_before: float
    balance_after: float
    status: TransactionStatus
    payment_method: Optional[PaymentMethod] = None
    reference: Optional[str] = None
    external_reference: Optional[str] = None
    description: Optional[str] = None
    shipment_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WalletSummary(BaseModel):
    wallet: WalletOut
    total_deposits: float
    total_deductions: float
    total_refunds: float
    pending_deposits: float
    recent_transactions: List[WalletTransactionOut]


class AdminDepositApproval(BaseModel):
    transaction_id: int
    action: str  # approve | reject
    notes: Optional[str] = None


class AdminBalanceAdjust(BaseModel):
    user_id: int
    amount: float
    transaction_type: TransactionType
    description: str


class StripeSessionRequest(BaseModel):
    amount: float  # GHS amount to top up


class StripeSessionOut(BaseModel):
    session_id: str
    session_url: str
    transaction_id: int


class AdminWalletTransactionOut(WalletTransactionOut):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None


class AdminWalletStats(BaseModel):
    total_deposits: float
    total_deductions: float
    total_refunds: float
    pending_count: int
    pending_amount: float
    total_wallet_balance: float
    deposits_change_pct: float
