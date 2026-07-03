from pydantic import BaseModel, ConfigDict
from typing import Optional, List


class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: str
    item_name: str
    brand: str
    category: str
    product_category: str
    avg_weight_kg: float
    dim_l_inches: Optional[float] = None
    dim_w_inches: Optional[float] = None
    dim_h_inches: Optional[float] = None
    shipping_mode: str
    status: str
    custom_quote_flag: bool
    contains_lithium_battery: bool
    fragility_level: str
    search_keywords: Optional[str] = None
    detection_priority: int
    detection_tier_hint: Optional[str] = None
    default_engine_hint: Optional[str] = None
    image_url: Optional[str] = None
    aliases: Optional[str] = None
    volume_cubic_feet: Optional[float] = None


class CatalogItemSearch(BaseModel):
    query: str
    limit: int = 10
    shipping_mode: Optional[str] = None
    category: Optional[str] = None


class CatalogSearchResult(BaseModel):
    items: List[CatalogItemOut]
    total: int
    query: str
    fallback_used: bool = False
