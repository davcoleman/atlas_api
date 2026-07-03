from sqlalchemy import Column, String, Float, Boolean, Integer, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum
from database import Base


class ShippingMode(str, enum.Enum):
    air = "air"
    sea = "sea"
    both = "both"


class FragilityLevel(str, enum.Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    extreme = "Extreme"


class DetectionTierHint(str, enum.Enum):
    budget = "BUDGET"
    mid = "MID"
    high = "HIGH"
    premium = "PREMIUM"
    flagship = "FLAGSHIP"
    high_value = "HIGH_VALUE"
    low_value = "LOW_VALUE"
    value_band = "VALUE_BAND"
    tablet_std = "TABLET_STD"
    tablet_air = "TABLET_AIR"
    tablet_pro = "TABLET_PRO"
    tablet_basic = "TABLET_BASIC"
    sea_fixed = "SEA_FIXED"
    custom = "CUSTOM"
    kg = "KG"


class DefaultEngineHint(str, enum.Enum):
    flat = "FLAT"
    hybrid = "HYBRID"
    value_band = "VALUE_BAND"
    kg = "KG"
    sea_fixed = "FIXED"
    custom = "CUSTOM"


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(20), unique=True, index=True, nullable=False)
    item_name = Column(String(200), nullable=False, index=True)
    brand = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    product_category = Column(String(100), nullable=False)

    avg_weight_kg = Column(Float, nullable=False, default=1.0)
    dim_l_inches = Column(Float, nullable=True)
    dim_w_inches = Column(Float, nullable=True)
    dim_h_inches = Column(Float, nullable=True)

    shipping_mode = Column(String(10), nullable=False, default="air")
    status = Column(String(10), nullable=False, default="active")
    custom_quote_flag = Column(Boolean, default=False)
    contains_lithium_battery = Column(Boolean, default=False)
    fragility_level = Column(String(20), default="Low")

    search_keywords = Column(Text, nullable=True)
    detection_priority = Column(Integer, default=50)
    detection_tier_hint = Column(String(30), nullable=True)
    default_engine_hint = Column(String(20), nullable=True)

    image_url = Column(String(300), nullable=True)
    aliases = Column(Text, nullable=True)

    @property
    def volume_cubic_feet(self) -> float | None:
        if self.dim_l_inches and self.dim_w_inches and self.dim_h_inches:
            return (self.dim_l_inches * self.dim_w_inches * self.dim_h_inches) / 1728
        return None
