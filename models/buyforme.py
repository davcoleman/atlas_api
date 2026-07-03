from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class BuyForMeStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    purchased = "purchased"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class BuyForMePaymentOption(str, enum.Enum):
    wallet = "wallet"
    topup = "topup"
    deferred = "deferred"


class BuyForMeRequest(Base):
    __tablename__ = "buyforme_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_number = Column(String(20), unique=True, nullable=False, index=True)  # BFM-YYYY-XXXXXX

    customer_id = Column(Integer, nullable=False, index=True)
    assigned_admin_id = Column(Integer, nullable=True)

    # Product info
    product_name = Column(String(500), nullable=False)
    product_url = Column(Text, nullable=True)
    product_description = Column(Text, nullable=True)
    quantity = Column(Integer, default=1, nullable=False)

    # Pricing
    cost_estimate = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    shipping_cost = Column(Float, nullable=True)
    service_fee = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    currency = Column(String(5), default="USD")

    # Payment
    payment_option = Column(SAEnum(BuyForMePaymentOption), default=BuyForMePaymentOption.wallet)
    payment_status = Column(String(30), default="unpaid")

    shipping_method = Column(String(10), default="air")  # air | sea
    status = Column(SAEnum(BuyForMeStatus), default=BuyForMeStatus.pending)

    # Admin workflow
    admin_notes = Column(Text, nullable=True)
    receipt_url = Column(String(500), nullable=True)
    product_photo_url = Column(String(500), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Linked shipment once shipped
    shipment_id = Column(Integer, nullable=True)

    approved_at = Column(DateTime, nullable=True)
    purchased_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
