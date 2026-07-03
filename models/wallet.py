from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    deduction = "deduction"
    refund = "refund"
    bonus = "bonus"
    reversal = "reversal"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    mobile_money = "mobile_money"
    visa_mastercard = "visa_mastercard"
    bank_transfer = "bank_transfer"
    wallet = "wallet"
    manual = "manual"


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    balance = Column(Float, default=0.0, nullable=False)
    currency = Column(String(5), default="GHS")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    transaction_type = Column(SAEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(5), default="GHS")
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)

    status = Column(SAEnum(TransactionStatus), default=TransactionStatus.pending)
    payment_method = Column(SAEnum(PaymentMethod), nullable=True)

    reference = Column(String(100), unique=True, nullable=True, index=True)
    external_reference = Column(String(200), nullable=True)  # Paystack/Flutterwave ref

    description = Column(Text, nullable=True)
    shipment_id = Column(Integer, nullable=True)  # linked shipment if deduction
    approved_by = Column(Integer, nullable=True)  # admin user_id

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
