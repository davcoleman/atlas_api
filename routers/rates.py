"""
Static rate data endpoints — freight rates, insurance tiers, HS codes.
These are DB-driven in production but seeded as constants here.
The frontend Quote.tsx page will call these instead of hardcoding values.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/rates", tags=["Rates"])


# ── Models ──────────────────────────────────────────────────────────────────

class FreightRate(BaseModel):
    id: str
    name: str
    rate_per_kg: float
    transit_days: str
    mode: str
    currency: str = "USD"
    is_active: bool = True


class InsuranceTier(BaseModel):
    id: str
    name: str
    rate: float
    description: str
    max_coverage: float
    is_mandatory: bool = False


class HSCode(BaseModel):
    code: str
    name: str
    duty_rate: float
    vat_rate: float
    category: str
    notes: Optional[str] = None


# ── Data (would be DB rows in production) ──────────────────────────────────

FREIGHT_RATES: list[FreightRate] = [
    FreightRate(id="air",     name="Air Freight", rate_per_kg=15.0,  transit_days="3–7 days",   mode="air"),
    FreightRate(id="sea",     name="Sea Freight", rate_per_kg=0.0,   transit_days="21–35 days", mode="sea"),  # sea uses cubic ft
    FreightRate(id="express", name="Express Air", rate_per_kg=25.0,  transit_days="1–3 days",   mode="air"),
    FreightRate(id="bulk",    name="Bulk Air",    rate_per_kg=10.0,  transit_days="5–10 days",  mode="air"),
]

INSURANCE_TIERS: list[InsuranceTier] = [
    InsuranceTier(id="none",     name="None",     rate=0.000, max_coverage=100,   description="Limited liability — max $100 reimbursement"),
    InsuranceTier(id="basic",    name="Basic",    rate=0.015, max_coverage=1000,  description="1.5% of declared value, up to $1,000 coverage"),
    InsuranceTier(id="standard", name="Standard", rate=0.025, max_coverage=5000,  description="2.5% of declared value, up to $5,000 coverage"),
    InsuranceTier(id="premium",  name="Premium",  rate=0.040, max_coverage=20000, description="4% of declared value, up to $20,000 coverage"),
]

# Ghana GRA / CEPS HS code duty table (12 categories from blueprint)
HS_CODES: list[HSCode] = [
    HSCode(code="8517.12", name="Mobile phones",             duty_rate=0.20, vat_rate=0.15, category="Phones & Tablets",    notes="Includes smartphones"),
    HSCode(code="8471.30", name="Laptops & tablets",         duty_rate=0.05, vat_rate=0.15, category="Laptops & Desktops",  notes="Portable computers"),
    HSCode(code="8473.30", name="Computer parts & peripherals", duty_rate=0.05, vat_rate=0.15, category="PC Parts"),
    HSCode(code="8528.72", name="Monitors & displays",       duty_rate=0.10, vat_rate=0.15, category="Monitors & Displays"),
    HSCode(code="8523.21", name="Gaming consoles",           duty_rate=0.20, vat_rate=0.15, category="Gaming Consoles"),
    HSCode(code="9102.11", name="Smartwatches & wearables",  duty_rate=0.20, vat_rate=0.15, category="Wearables & Accessories"),
    HSCode(code="8518.30", name="Headphones & earbuds",      duty_rate=0.20, vat_rate=0.15, category="Wearables & Accessories"),
    HSCode(code="9006.53", name="Cameras & photography",     duty_rate=0.10, vat_rate=0.15, category="Cameras & Photography"),
    HSCode(code="6109.10", name="T-shirts & clothing (cotton)", duty_rate=0.20, vat_rate=0.15, category="Clothes & Fashion"),
    HSCode(code="6402.99", name="Footwear (rubber/plastic)", duty_rate=0.20, vat_rate=0.15, category="Clothes & Fashion"),
    HSCode(code="3304.99", name="Cosmetics & beauty",        duty_rate=0.20, vat_rate=0.15, category="General Goods"),
    HSCode(code="9503.00", name="Toys & games",              duty_rate=0.10, vat_rate=0.15, category="General Goods"),
    HSCode(code="8708.99", name="Auto parts & accessories",  duty_rate=0.10, vat_rate=0.15, category="Sea Cargo & Heavy Items"),
    HSCode(code="4202.92", name="Bags & luggage",            duty_rate=0.20, vat_rate=0.15, category="Clothes & Fashion"),
    HSCode(code="8516.60", name="Kitchen appliances",        duty_rate=0.20, vat_rate=0.15, category="General Goods"),
    HSCode(code="8528.71", name="Smart TVs",                 duty_rate=0.20, vat_rate=0.15, category="Monitors & Displays"),
    HSCode(code="9401.61", name="Furniture (seating)",       duty_rate=0.20, vat_rate=0.15, category="Sea Cargo & Heavy Items"),
    HSCode(code="8509.40", name="Food blenders / processors", duty_rate=0.20, vat_rate=0.15, category="General Goods"),
    HSCode(code="2936.21", name="Vitamins & supplements",    duty_rate=0.10, vat_rate=0.15, category="General Goods",        notes="Check NAFDAC requirements"),
    HSCode(code="9019.10", name="Medical devices (small)",   duty_rate=0.00, vat_rate=0.15, category="General Goods",        notes="May be duty-exempt"),
]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/freight", response_model=List[FreightRate])
def get_freight_rates():
    """Live freight rates — mirrors what the Quote page needs."""
    return [r for r in FREIGHT_RATES if r.is_active]


@router.get("/insurance", response_model=List[InsuranceTier])
def get_insurance_tiers():
    return INSURANCE_TIERS


@router.get("/hs-codes", response_model=List[HSCode])
def get_hs_codes(q: Optional[str] = None):
    """Search HS codes by name or code."""
    if not q:
        return HS_CODES
    q_lower = q.lower()
    return [h for h in HS_CODES if q_lower in h.name.lower() or q_lower in h.code]


@router.get("/hs-codes/{code}", response_model=HSCode)
def get_hs_code(code: str):
    for h in HS_CODES:
        if h.code == code:
            return h
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"HS code '{code}' not found")
