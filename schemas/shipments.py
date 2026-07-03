from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.shipments import ShipmentStatus, ShippingMode


class ShipmentCreate(BaseModel):
    quote_reference: Optional[str] = None
    item_name: str
    product_id: Optional[str] = None
    category: Optional[str] = None
    quantity: int = 1
    weight_kg: float
    declared_value_usd: float
    dim_l: Optional[float] = None
    dim_w: Optional[float] = None
    dim_h: Optional[float] = None
    shipping_mode: ShippingMode
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    insurance_tier: str = "none"
    notes: Optional[str] = None


class ShipmentOut(BaseModel):
    id: int
    tracking_number: str
    user_id: int
    quote_reference: Optional[str] = None
    item_name: str
    product_id: Optional[str] = None
    category: Optional[str] = None
    quantity: int
    weight_kg: float
    declared_value_usd: float
    shipping_mode: ShippingMode
    origin_country: str
    destination_country: str
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    engine_code: Optional[str] = None
    base_shipping: float
    vat_amount: float
    handling_fee: float
    insurance_premium: float
    insurance_tier: str
    duty_estimate: float
    total_amount: float
    currency: str
    status: ShipmentStatus
    payment_status: str
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus
    note: Optional[str] = None
    estimated_arrival: Optional[datetime] = None


class StatusHistoryOut(BaseModel):
    id: int
    shipment_id: int
    previous_status: Optional[str] = None
    new_status: str
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShipmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ShipmentOut]


class AdminShipmentOut(ShipmentOut):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None


class AdminShipmentCreate(ShipmentCreate):
    customer_id: int
    total_amount: Optional[float] = None
