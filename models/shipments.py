from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class ShipmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    in_transit = "in_transit"
    arrived = "arrived"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    on_hold = "on_hold"


class ShippingMode(str, enum.Enum):
    air = "air"
    sea = "sea"


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String(30), unique=True, nullable=False, index=True)  # ATL-YYYYMMDD-XXXXXX
    user_id = Column(Integer, nullable=False, index=True)
    quote_reference = Column(String(20), nullable=True)  # linked saved_quote reference_id

    # Item info
    item_name = Column(String(300), nullable=False)
    product_id = Column(String(20), nullable=True)
    category = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)
    weight_kg = Column(Float, nullable=False)
    declared_value_usd = Column(Float, nullable=False)
    dim_l = Column(Float, nullable=True)
    dim_w = Column(Float, nullable=True)
    dim_h = Column(Float, nullable=True)

    # Route
    origin_country = Column(String(100), default="USA")
    destination_country = Column(String(100), default="Ghana")
    origin_address = Column(Text, nullable=True)
    destination_address = Column(Text, nullable=True)
    shipping_mode = Column(SAEnum(ShippingMode), nullable=False)

    # Pricing
    engine_code = Column(String(30), nullable=True)
    base_shipping = Column(Float, default=0.0)
    vat_amount = Column(Float, default=0.0)
    handling_fee = Column(Float, default=0.0)
    insurance_premium = Column(Float, default=0.0)
    insurance_tier = Column(String(20), default="none")
    duty_estimate = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(5), default="USD")

    # Status
    status = Column(SAEnum(ShipmentStatus), default=ShipmentStatus.pending)
    payment_status = Column(String(20), default="unpaid")  # unpaid, paid, refunded

    # Live tracking (map + progress bar, admin-updated)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    current_location_label = Column(String(200), nullable=True)
    progress_percent = Column(Integer, default=0)

    # Timestamps
    estimated_arrival = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)
    assigned_staff_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ShipmentStatusHistory(Base):
    __tablename__ = "shipment_status_history"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False, index=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    changed_by = Column(Integer, nullable=True)  # user_id
    created_at = Column(DateTime, server_default=func.now())
