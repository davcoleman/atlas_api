from sqlalchemy import Column, String, Float, Boolean, Integer, Text, JSON
from database import Base


class PricingEngine(Base):
    """
    Each row is one of the 16 pricing engines (8 air + 8 sea).
    All formula variables live here — no hardcoded rates in code.
    Admins change a value here and the next quote uses it instantly.
    """
    __tablename__ = "pricing_engines"

    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    mode = Column(String(5), nullable=False)   # "air" | "sea"
    formula_type = Column(String(20), nullable=False)  # FLAT | HYBRID | VALUE_BAND | KG | FIXED | CUSTOM
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_manual = Column(Boolean, default=False)  # manual quote → admin queue

    # --- air base variables ---
    rate_per_kg = Column(Float, nullable=True)          # USD/kg base
    vat_rate = Column(Float, default=0.0)               # on shipping charge only
    handling_flat = Column(Float, default=0.0)          # flat handling fee USD
    handling_pct = Column(Float, default=0.0)           # % of base cost
    min_charge = Column(Float, default=0.0)

    # --- sea base variables ---
    rate_per_cubic_ft = Column(Float, nullable=True)
    port_handling_flat = Column(Float, default=0.0)
    processing_fee = Column(Float, default=0.0)
    sea_min_charge = Column(Float, default=35.0)

    # --- value band / hybrid variables (stored as JSON list) ---
    # For FLAT engine: [{"min": 0, "max": 200, "handling": 20}, ...]
    # For VALUE_BAND: [{"min": 0, "max": 500, "rate": 25}, ...]
    # For HYBRID: [{"min": 0, "max": 300, "base_fee": 15}] + hybrid_value_pct
    value_bands = Column(JSON, nullable=True)
    hybrid_value_pct = Column(Float, default=0.0)   # e.g. 0.06 = 6% of declared value

    # --- bulk / volume discount ---
    bulk_discount_tiers = Column(JSON, nullable=True)  # [{"min_kg": 50, "discount_pct": 0.05}, ...]

    # --- profitability cost config (runs in parallel) ---
    cost_carrier_per_kg = Column(Float, default=8.50)
    cost_carrier_per_cubic_ft = Column(Float, default=3.00)
    cost_customs = Column(Float, default=12.00)
    cost_warehouse = Column(Float, default=8.00)
    cost_overhead = Column(Float, default=5.00)
    margin_alert_threshold = Column(Float, default=0.15)  # fire alert if margin < 15%


class EngineConfig(Base):
    """Maps a category (or product_id) to a specific engine per customer type."""
    __tablename__ = "engine_configs"

    id = Column(Integer, primary_key=True)
    engine_id = Column(Integer, nullable=False)
    target_type = Column(String(10), nullable=False)   # "category" | "product"
    target_value = Column(String(200), nullable=False) # category name or product_id
    customer_type = Column(String(20), default="retail")  # retail | bulk | vip | wholesale
    corridor = Column(String(20), default="USA-GH")
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=2)  # 1=product override, 2=category, 3=default
