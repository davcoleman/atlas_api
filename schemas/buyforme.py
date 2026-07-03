from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from models.buyforme import BuyForMeStatus, BuyForMePaymentOption


class ScrapeRequest(BaseModel):
    url: str


class ScrapedProductOut(BaseModel):
    url: str
    asin: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    description: Optional[str] = None
    availability: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    scrape_success: bool
    error: Optional[str] = None


class BuyForMeCreate(BaseModel):
    product_name: str
    product_url: Optional[str] = None
    product_description: Optional[str] = None
    product_photo_url: Optional[str] = None
    quantity: int = 1
    cost_estimate: Optional[float] = None
    shipping_method: str = "air"
    payment_option: BuyForMePaymentOption = BuyForMePaymentOption.wallet


class BuyForMeOut(BaseModel):
    id: int
    request_number: str
    customer_id: int
    assigned_admin_id: Optional[int] = None
    product_name: str
    product_url: Optional[str] = None
    product_description: Optional[str] = None
    quantity: int
    cost_estimate: Optional[float] = None
    actual_cost: Optional[float] = None
    shipping_cost: Optional[float] = None
    service_fee: Optional[float] = None
    total_cost: Optional[float] = None
    currency: str
    payment_option: BuyForMePaymentOption
    payment_status: str
    shipping_method: str
    status: BuyForMeStatus
    admin_notes: Optional[str] = None
    receipt_url: Optional[str] = None
    product_photo_url: Optional[str] = None
    rejection_reason: Optional[str] = None
    shipment_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    purchased_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminBuyForMeUpdate(BaseModel):
    status: Optional[BuyForMeStatus] = None
    actual_cost: Optional[float] = None
    shipping_cost: Optional[float] = None
    service_fee: Optional[float] = None
    admin_notes: Optional[str] = None
    receipt_url: Optional[str] = None
    product_photo_url: Optional[str] = None
    rejection_reason: Optional[str] = None
    shipment_id: Optional[int] = None


class BuyForMeListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[BuyForMeOut]


class AdminBuyForMeOut(BuyForMeOut):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
