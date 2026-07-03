"""Seed the 16 pricing engines (8 air + 8 sea) into the DB."""
from sqlalchemy.orm import Session
from models.engines import PricingEngine, EngineConfig

AIR_ENGINES = [
    # Engine 1 — Fixed Value (phones, tablets)
    dict(
        code="AIR_FLAT", name="Fixed Value Engine", mode="air", formula_type="FLAT",
        description="iPhones, Samsung, Google Pixel, Tablets — fixed handling fee by declared value band.",
        rate_per_kg=15.0, vat_rate=0.0, min_charge=10.0,
        handling_flat=0.0, handling_pct=0.0,
        value_bands=[
            {"min": 0,    "max": 200,  "handling": 15},
            {"min": 200,  "max": 400,  "handling": 20},
            {"min": 400,  "max": 700,  "handling": 25},
            {"min": 700,  "max": 1000, "handling": 35},
            {"min": 1000, "max": 9999, "handling": 50},
        ],
        cost_carrier_per_kg=8.50, cost_customs=12.0, cost_warehouse=8.0, cost_overhead=5.0,
    ),
    # Engine 2 — Value Band Laptop
    dict(
        code="AIR_VALUE_BAND", name="Value Band Laptop Engine", mode="air", formula_type="VALUE_BAND",
        description="Standard Laptops, MacBooks, Gaming Laptops — value band + semi-hybrid for premium units.",
        rate_per_kg=15.0, vat_rate=0.0, min_charge=25.0,
        handling_flat=0.0, handling_pct=0.0, hybrid_value_pct=0.02,
        value_bands=[
            {"min": 0,    "max": 400,  "rate": 20},
            {"min": 400,  "max": 800,  "rate": 30},
            {"min": 800,  "max": 1500, "rate": 40},
            {"min": 1500, "max": 3000, "rate": 55},
            {"min": 3000, "max": 9999, "rate": 80},
        ],
        cost_carrier_per_kg=8.50, cost_customs=15.0, cost_warehouse=10.0, cost_overhead=6.0,
    ),
    # Engine 3 — Hybrid Electronics (GPUs, CPUs, SSDs)
    dict(
        code="AIR_HYBRID", name="Hybrid Electronics Engine", mode="air", formula_type="HYBRID",
        description="GPUs, CPUs, SSDs, Servers, AI Accelerators — tiered base fee + 6% of declared value.",
        rate_per_kg=15.0, vat_rate=0.10, min_charge=20.0,
        handling_flat=0.0, handling_pct=0.0, hybrid_value_pct=0.06,
        value_bands=[
            {"min": 0,    "max": 299,  "base_fee": 10},
            {"min": 300,  "max": 999,  "base_fee": 15},
            {"min": 1000, "max": 9999, "base_fee": 30},
        ],
        cost_carrier_per_kg=8.50, cost_customs=12.0, cost_warehouse=8.0, cost_overhead=5.0,
    ),
    # Engine 4 — Flat KG + Handling (headsets, keyboards, chargers)
    dict(
        code="AIR_FLAT_KG", name="Flat KG + Handling Engine", mode="air", formula_type="FLAT",
        description="Headsets, Keyboards, Chargers, Power Banks — standard $15/kg + flat category handling.",
        rate_per_kg=15.0, vat_rate=0.0, min_charge=8.0,
        handling_flat=12.0, handling_pct=0.0,
        cost_carrier_per_kg=8.50, cost_customs=10.0, cost_warehouse=7.0, cost_overhead=4.0,
    ),
    # Engine 5 — Pure KG (clothes, shoes, bags, general goods)
    dict(
        code="AIR_PURE_KG", name="Pure KG Engine", mode="air", formula_type="KG",
        description="Clothes, Shoes, Bags, General Goods — category-specific KG rate (not $15 base).",
        rate_per_kg=8.0, vat_rate=0.0, min_charge=5.0,
        handling_flat=3.0, handling_pct=0.05,
        cost_carrier_per_kg=4.00, cost_customs=6.0, cost_warehouse=4.0, cost_overhead=3.0,
    ),
    # Engine 6 — Premium Protection (luxury watches, medical, cameras)
    dict(
        code="AIR_PREMIUM", name="Premium Protection Engine", mode="air", formula_type="FLAT",
        description="Luxury Watches, Medical Electronics, Cameras — premium handling + mandatory minimum insurance.",
        rate_per_kg=15.0, vat_rate=0.0, min_charge=30.0,
        handling_flat=25.0, handling_pct=0.03,
        cost_carrier_per_kg=8.50, cost_customs=18.0, cost_warehouse=12.0, cost_overhead=6.0,
    ),
    # Engine 7 — Bulk/Wholesale
    dict(
        code="AIR_BULK", name="Bulk / Wholesale Engine", mode="air", formula_type="FLAT",
        description="Resellers, Commercial Importers — standard total minus volume discount tier.",
        rate_per_kg=15.0, vat_rate=0.0, min_charge=10.0,
        handling_flat=10.0, handling_pct=0.0,
        bulk_discount_tiers=[
            {"min_kg": 20,  "discount_pct": 0.05},
            {"min_kg": 50,  "discount_pct": 0.08},
            {"min_kg": 100, "discount_pct": 0.12},
            {"min_kg": 200, "discount_pct": 0.15},
        ],
        cost_carrier_per_kg=7.00, cost_customs=10.0, cost_warehouse=7.0, cost_overhead=4.0,
    ),
    # Engine 8 — Manual Quote (industrial equipment, commercial servers)
    dict(
        code="AIR_MANUAL", name="Manual Quote Engine (Air)", mode="air", formula_type="CUSTOM",
        description="Industrial Equipment, Commercial Servers — auto-escalated to admin review queue.",
        is_manual=True,
        rate_per_kg=0.0, vat_rate=0.0, min_charge=0.0, handling_flat=0.0,
    ),
]

SEA_ENGINES = [
    # Sea Engine 1 — Fixed Item (TVs, fridges, sofas)
    dict(
        code="SEA_FIXED", name="Fixed Item Engine", mode="sea", formula_type="FIXED",
        description="TVs, Fridges, Sofas, Beds, Sound Systems — pre-defined fixed sea freight per item type.",
        rate_per_cubic_ft=0.0, port_handling_flat=35.0, processing_fee=15.0, sea_min_charge=35.0,
        value_bands=[
            {"min": 0,    "max": 200,  "handling": 80},
            {"min": 200,  "max": 500,  "handling": 120},
            {"min": 500,  "max": 1000, "handling": 180},
            {"min": 1000, "max": 9999, "handling": 250},
        ],
        cost_carrier_per_cubic_ft=3.0, cost_customs=20.0, cost_warehouse=15.0, cost_overhead=8.0,
    ),
    # Sea Engine 2 — Pure Cubic Feet (boxes, household)
    dict(
        code="SEA_PURE_CUBIC", name="Pure Cubic Feet Engine", mode="sea", formula_type="KG",
        description="Boxes, Household Items, Mixed Goods — category rate per cubic foot.",
        rate_per_cubic_ft=4.0, port_handling_flat=20.0, processing_fee=10.0, sea_min_charge=35.0,
        cost_carrier_per_cubic_ft=2.00, cost_customs=12.0, cost_warehouse=8.0, cost_overhead=5.0,
    ),
    # Sea Engine 3 — Category Cubic (electronics, fragile, heavy)
    dict(
        code="SEA_CATEGORY_CUBIC", name="Category Cubic Engine", mode="sea", formula_type="KG",
        description="Electronics, Fragile, Heavy Cargo — category rate per cubic foot + flat handling.",
        rate_per_cubic_ft=5.5, port_handling_flat=30.0, processing_fee=15.0, sea_min_charge=35.0,
        cost_carrier_per_cubic_ft=2.50, cost_customs=15.0, cost_warehouse=10.0, cost_overhead=6.0,
    ),
    # Sea Engine 4 — Hybrid Sea (premium TVs, luxury furniture)
    dict(
        code="SEA_HYBRID", name="Hybrid Sea Engine", mode="sea", formula_type="HYBRID",
        description="Premium TVs, Luxury Furniture, Expensive Items — sea freight + value protection fee (tiered).",
        rate_per_cubic_ft=5.0, port_handling_flat=25.0, processing_fee=12.0, sea_min_charge=35.0,
        hybrid_value_pct=0.04,
        cost_carrier_per_cubic_ft=2.50, cost_customs=18.0, cost_warehouse=12.0, cost_overhead=6.0,
    ),
    # Sea Engine 5 — Box Tier (standard boxes, student cargo)
    dict(
        code="SEA_BOX_TIER", name="Box Tier Engine", mode="sea", formula_type="VALUE_BAND",
        description="Standard Boxes, Personal & Student Cargo — fixed tier price + overweight surcharge.",
        rate_per_cubic_ft=0.0, port_handling_flat=15.0, processing_fee=8.0, sea_min_charge=35.0,
        value_bands=[
            {"min": 0,   "max": 10,  "handling": 45},
            {"min": 10,  "max": 20,  "handling": 65},
            {"min": 20,  "max": 35,  "handling": 90},
            {"min": 35,  "max": 50,  "handling": 120},
            {"min": 50,  "max": 9999,"handling": 160},
        ],
        cost_carrier_per_cubic_ft=1.50, cost_customs=8.0, cost_warehouse=6.0, cost_overhead=4.0,
    ),
    # Sea Engine 6 — Bulk Cargo
    dict(
        code="SEA_BULK", name="Bulk Cargo Engine", mode="sea", formula_type="KG",
        description="Resellers, Commercial Importers — standard total minus cubic footage discount.",
        rate_per_cubic_ft=3.5, port_handling_flat=20.0, processing_fee=10.0, sea_min_charge=35.0,
        bulk_discount_tiers=[
            {"min_kg": 50,  "discount_pct": 0.05},
            {"min_kg": 150, "discount_pct": 0.08},
            {"min_kg": 300, "discount_pct": 0.12},
        ],
        cost_carrier_per_cubic_ft=1.50, cost_customs=10.0, cost_warehouse=7.0, cost_overhead=4.0,
    ),
    # Sea Engine 7 — Pallet & Container → manual
    dict(
        code="SEA_PALLET", name="Pallet & Container Engine", mode="sea", formula_type="CUSTOM",
        description="Pallets, Containers, Industrial Freight — custom quote routed to operations team.",
        is_manual=True,
        rate_per_cubic_ft=0.0, port_handling_flat=0.0, processing_fee=0.0, sea_min_charge=35.0,
    ),
    # Sea Engine 8 — Manual Quote
    dict(
        code="SEA_MANUAL", name="Manual Quote Engine (Sea)", mode="sea", formula_type="CUSTOM",
        description="Oversized, Hazardous, Special Cargo — auto-escalated to admin review queue.",
        is_manual=True,
        rate_per_cubic_ft=0.0, port_handling_flat=0.0, processing_fee=0.0, sea_min_charge=35.0,
    ),
]

# Category → engine code mappings
CATEGORY_MAPPINGS = [
    # Air categories
    ("category", "Phones & Tablets",          "AIR_FLAT",       "retail", "air"),
    ("category", "Laptops & Desktops",         "AIR_VALUE_BAND", "retail", "air"),
    ("category", "PC Parts",                   "AIR_HYBRID",     "retail", "air"),
    ("category", "Monitors & Displays",        "AIR_FLAT_KG",    "retail", "air"),
    ("category", "Gaming Consoles",            "AIR_FLAT",       "retail", "air"),
    ("category", "Wearables & Accessories",    "AIR_FLAT_KG",    "retail", "air"),
    ("category", "Cameras & Photography",      "AIR_PREMIUM",    "retail", "air"),
    ("category", "Smart Home",                 "AIR_FLAT_KG",    "retail", "air"),
    ("category", "Networking & Enterprise",    "AIR_FLAT_KG",    "retail", "air"),
    ("category", "Clothes & Fashion",          "AIR_PURE_KG",    "retail", "air"),
    ("category", "General Goods",              "AIR_PURE_KG",    "retail", "air"),
    # Sea categories
    ("category", "Sea Cargo & Heavy Items",    "SEA_FIXED",      "retail", "sea"),
    ("category", "Clothes & Fashion",          "SEA_PURE_CUBIC", "retail", "sea"),
    ("category", "General Goods",              "SEA_PURE_CUBIC", "retail", "sea"),
    ("category", "Laptops & Desktops",         "SEA_CATEGORY_CUBIC", "retail", "sea"),
    ("category", "Monitors & Displays",        "SEA_CATEGORY_CUBIC", "retail", "sea"),
    # Bulk customer type overrides
    ("category", "Phones & Tablets",           "AIR_BULK",       "bulk",   "air"),
    ("category", "Laptops & Desktops",         "AIR_BULK",       "bulk",   "air"),
]


def _apply_engine_data(engine: PricingEngine, eng_data: dict) -> None:
    """Write all config fields from eng_data onto an engine ORM object."""
    engine.name = eng_data["name"]
    engine.mode = eng_data["mode"]
    engine.formula_type = eng_data["formula_type"]
    engine.description = eng_data.get("description")
    engine.is_active = True
    engine.is_manual = eng_data.get("is_manual", False)
    engine.rate_per_kg = eng_data.get("rate_per_kg")
    engine.vat_rate = eng_data.get("vat_rate", 0.0)
    engine.handling_flat = eng_data.get("handling_flat", 0.0)
    engine.handling_pct = eng_data.get("handling_pct", 0.0)
    engine.min_charge = eng_data.get("min_charge", 0.0)
    engine.rate_per_cubic_ft = eng_data.get("rate_per_cubic_ft")
    engine.port_handling_flat = eng_data.get("port_handling_flat", 0.0)
    engine.processing_fee = eng_data.get("processing_fee", 0.0)
    engine.sea_min_charge = eng_data.get("sea_min_charge", 35.0)
    engine.value_bands = eng_data.get("value_bands")
    engine.hybrid_value_pct = eng_data.get("hybrid_value_pct", 0.0)
    engine.bulk_discount_tiers = eng_data.get("bulk_discount_tiers")
    engine.cost_carrier_per_kg = eng_data.get("cost_carrier_per_kg", 8.50)
    engine.cost_carrier_per_cubic_ft = eng_data.get("cost_carrier_per_cubic_ft", 3.0)
    engine.cost_customs = eng_data.get("cost_customs", 12.0)
    engine.cost_warehouse = eng_data.get("cost_warehouse", 8.0)
    engine.cost_overhead = eng_data.get("cost_overhead", 5.0)


def seed_engines(db: Session) -> None:
    existing = {e.code: e for e in db.query(PricingEngine).all()}

    for eng_data in AIR_ENGINES + SEA_ENGINES:
        code = eng_data["code"]
        if code in existing:
            # Upsert — keep config in sync with seed definitions
            _apply_engine_data(existing[code], eng_data)
        else:
            engine = PricingEngine(code=code)
            _apply_engine_data(engine, eng_data)
            db.add(engine)

    db.flush()

    # Build engine code→id map
    engine_map = {e.code: e.id for e in db.query(PricingEngine).all()}
    existing_configs = db.query(EngineConfig).count()

    if existing_configs == 0:
        for (ttype, tval, ecode, ctype, mode) in CATEGORY_MAPPINGS:
            engine_id = engine_map.get(ecode)
            if not engine_id:
                continue
            db.add(EngineConfig(
                engine_id=engine_id,
                target_type=ttype,
                target_value=tval,
                customer_type=ctype,
                corridor="USA-GH",
                is_active=True,
                priority=2,
            ))

    db.commit()
    print(f"[seed] Pricing engines seeded: {len(AIR_ENGINES + SEA_ENGINES)} engines, {len(CATEGORY_MAPPINGS)} category mappings.")
