from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class QuoteRequest(BaseModel):
    # Item identification (at least one required)
    product_id: Optional[str] = None
    item_name: Optional[str] = None
    category: Optional[str] = None

    # Shipping params
    shipping_mode: str  # "air" | "sea"
    weight_kg: float
    declared_value_usd: float
    quantity: int = 1

    # Dimensions (required for sea, optional for air)
    dim_l_inches: Optional[float] = None
    dim_w_inches: Optional[float] = None
    dim_h_inches: Optional[float] = None

    # Insurance
    insurance_tier: str = "none"  # none | basic | standard | premium

    # Customer type affects engine selection
    customer_type: str = "retail"

    @field_validator("shipping_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("air", "sea"):
            raise ValueError("shipping_mode must be 'air' or 'sea'")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("weight_kg must be positive")
        return v

    @field_validator("declared_value_usd")
    @classmethod
    def validate_value(cls, v: float) -> float:
        if v < 0:
            raise ValueError("declared_value_usd cannot be negative")
        return v


class QuoteBreakdown(BaseModel):
    base_shipping: float
    vat_amount: float
    handling_fee: float
    insurance_premium: float
    duty_estimate: float
    subtotal: float
    # profitability (admin-visible only, hidden from customer response by default)
    total_cost: Optional[float] = None
    gross_margin: Optional[float] = None
    margin_pct: Optional[float] = None
    margin_alert: bool = False


class QuoteOut(BaseModel):
    reference_id: str
    item_name: str
    shipping_mode: str
    weight_kg: float
    declared_value_usd: float
    engine_code: str
    insurance_tier: str
    breakdown: QuoteBreakdown
    is_manual: bool = False
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class SaveQuoteRequest(BaseModel):
    quote: QuoteOut
    # In production this would carry the authenticated user's ID
    customer_ref: Optional[str] = None
