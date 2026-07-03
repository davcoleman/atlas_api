from pydantic import BaseModel, ConfigDict
from typing import Optional, Any


class PricingEngineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    mode: str
    formula_type: str
    description: Optional[str] = None
    is_active: bool
    is_manual: bool
    rate_per_kg: Optional[float] = None
    vat_rate: float
    handling_flat: float
    handling_pct: float
    min_charge: float
    rate_per_cubic_ft: Optional[float] = None
    port_handling_flat: float
    processing_fee: float
    sea_min_charge: float
    value_bands: Optional[Any] = None
    hybrid_value_pct: float
    bulk_discount_tiers: Optional[Any] = None


class EngineConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    engine_id: int
    target_type: str
    target_value: str
    customer_type: str
    corridor: str
    is_active: bool
    priority: int
