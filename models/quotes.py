from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base


class SavedQuote(Base):
    __tablename__ = "saved_quotes"

    id = Column(Integer, primary_key=True)
    reference_id = Column(String(20), unique=True, nullable=False, index=True)  # AFL-2026-XXXXXX

    # Item info
    product_id = Column(String(20), nullable=True)
    item_name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)

    # Shipping params
    shipping_mode = Column(String(5), nullable=False)   # air | sea
    weight_kg = Column(Float, nullable=False)
    declared_value_usd = Column(Float, nullable=False)
    dim_l = Column(Float, nullable=True)
    dim_w = Column(Float, nullable=True)
    dim_h = Column(Float, nullable=True)

    # Engine used
    engine_code = Column(String(30), nullable=True)

    # Quote breakdown
    base_shipping = Column(Float, nullable=False)
    vat_amount = Column(Float, default=0.0)
    handling_fee = Column(Float, default=0.0)
    insurance_premium = Column(Float, default=0.0)
    insurance_tier = Column(String(20), default="none")
    duty_estimate = Column(Float, default=0.0)
    subtotal = Column(Float, nullable=False)

    # Profitability
    total_cost = Column(Float, nullable=True)
    gross_margin = Column(Float, nullable=True)
    margin_pct = Column(Float, nullable=True)
    margin_alert = Column(Boolean, default=False)

    # Meta
    currency = Column(String(5), default="USD")
    expires_at = Column(DateTime, nullable=True)
    is_manual = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
