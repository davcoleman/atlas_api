"""
AFL Smart Pricing Engine — 16 formula implementations
8 air engines + 8 sea engines, all driven by DB-stored config.

Air base rule:  Shipping = weight_kg × rate_per_kg
                Total    = Shipping + VAT (on shipping only) + Handling + Insurance

Sea base rule:  Cubic ft = (L × W × H) / 1728  [all dims in inches]
                Total    = Sea Freight + Port Handling + Processing Fee + Insurance
                Min charge: $35
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from models.engines import PricingEngine

INSURANCE_RATES = {
    "none":     {"rate": 0.000, "label": "None"},
    "basic":    {"rate": 0.015, "label": "Basic (1.5%)"},
    "standard": {"rate": 0.025, "label": "Standard (2.5%)"},
    "premium":  {"rate": 0.040, "label": "Premium (4%)"},
}


@dataclass
class PriceResult:
    engine_code: str
    base_shipping: float
    vat_amount: float
    handling_fee: float
    insurance_premium: float
    subtotal: float
    is_manual: bool = False
    notes: str = ""

    # Profitability
    total_cost: float = 0.0
    gross_margin: float = 0.0
    margin_pct: float = 0.0
    margin_alert: bool = False


def _resolve_value_band(bands: list[dict], value: float) -> float:
    """Return the fee/rate for the band that contains `value`."""
    for band in sorted(bands, key=lambda b: b.get("min", 0)):
        max_v = band.get("max", float("inf"))
        if band.get("min", 0) <= value <= max_v:
            return band.get("handling") or band.get("rate") or band.get("base_fee") or 0.0
    # fall through to last band
    return (bands[-1].get("handling") or bands[-1].get("rate") or bands[-1].get("base_fee") or 0.0) if bands else 0.0


def _bulk_discount(tiers: list[dict] | None, weight_kg: float, base_cost: float) -> float:
    if not tiers:
        return 0.0
    discount = 0.0
    for tier in sorted(tiers, key=lambda t: t.get("min_kg", 0), reverse=True):
        if weight_kg >= tier.get("min_kg", 0):
            discount = base_cost * tier.get("discount_pct", 0.0)
            break
    return discount


def _profitability(engine: PricingEngine, weight_kg: float, revenue: float, cubic_ft: float = 0.0) -> tuple[float, float, float, bool]:
    if engine.mode == "air":
        carrier = weight_kg * engine.cost_carrier_per_kg
    else:
        carrier = cubic_ft * engine.cost_carrier_per_cubic_ft
    total_cost = carrier + engine.cost_customs + engine.cost_warehouse + engine.cost_overhead
    gross_margin = revenue - total_cost
    margin_pct = (gross_margin / revenue) if revenue > 0 else 0.0
    alert = margin_pct < engine.margin_alert_threshold
    return round(total_cost, 2), round(gross_margin, 2), round(margin_pct, 4), alert


# ─────────────────────────────────────────────
#  AIR ENGINES
# ─────────────────────────────────────────────

def _air_engine_flat(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 1 — Fixed Value Engine (iPhones, Samsung, Tablets)
    Shipping = weight × rate_per_kg
    Handling = fixed fee from declared-value band
    """
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    handling = _resolve_value_band(engine.value_bands or [], declared_value) if engine.value_bands else engine.handling_flat
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_value_band(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 2 — Value Band Laptop Engine
    Shipping = weight × rate_per_kg
    Handling = value-band rate (semi-hybrid for premium units)
    """
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    band_rate = _resolve_value_band(engine.value_bands or [], declared_value)
    handling = band_rate + (declared_value * engine.hybrid_value_pct if engine.hybrid_value_pct else 0)
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_hybrid(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 3 — Hybrid Electronics Engine (GPUs, CPUs, SSDs)
    Shipping = weight × rate_per_kg
    Handling = tiered base fee + hybrid_value_pct × declared_value
    """
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    base_fee = _resolve_value_band(engine.value_bands or [], declared_value)
    handling = base_fee + declared_value * (engine.hybrid_value_pct or 0.06)
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_flat_kg(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 4 — Flat KG + Handling Engine (Headsets, Keyboards, Chargers)
    Shipping = weight × rate_per_kg  (standard $15 base)
    Handling = flat category fee
    """
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    handling = engine.handling_flat
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_pure_kg(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 5 — Pure KG Engine (Clothes, Shoes, Bags)
    Uses category-specific KG rate (NOT the $15 base rate)
    """
    base = weight_kg * (engine.rate_per_kg or 8.0)
    vat = base * engine.vat_rate
    handling = engine.handling_flat + base * engine.handling_pct
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_premium(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 6 — Premium Protection Engine (Luxury Watches, Medical, Cameras)
    Forces minimum Standard insurance tier.
    """
    forced_tier = insurance_tier if insurance_tier in ("standard", "premium") else "standard"
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    handling = engine.handling_flat + declared_value * engine.handling_pct
    ins = declared_value * INSURANCE_RATES.get(forced_tier, INSURANCE_RATES["standard"])["rate"]
    subtotal = max(base + vat + handling + ins, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    notes = "Insurance upgraded to Standard minimum for premium items." if forced_tier != insurance_tier else ""
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       notes=notes, total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _air_engine_bulk(engine: PricingEngine, weight_kg: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Engine 7 — Bulk/Wholesale Engine
    Standard total minus volume discount tier.
    """
    base = weight_kg * (engine.rate_per_kg or 15.0)
    vat = base * engine.vat_rate
    handling = engine.handling_flat
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    gross = base + vat + handling + ins
    discount = _bulk_discount(engine.bulk_discount_tiers, weight_kg, gross)
    subtotal = max(gross - discount, engine.min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal)
    notes = f"Volume discount applied: -${discount:.2f}" if discount > 0 else ""
    return PriceResult(engine.code, round(base, 2), round(vat, 2), round(handling, 2), round(ins, 2), round(subtotal, 2),
                       notes=notes, total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _engine_manual(engine: PricingEngine, *_) -> PriceResult:
    """Engine 8 (air) / Engine 8 (sea) — Manual Quote Engine
    Auto-escalated to admin review queue.
    """
    return PriceResult(engine.code, 0, 0, 0, 0, 0, is_manual=True,
                       notes="This item requires a manual quote. An admin will contact you within 24 hours.")


# ─────────────────────────────────────────────
#  SEA ENGINES
# ─────────────────────────────────────────────

def _cubic_feet(l: Optional[float], w: Optional[float], h: Optional[float]) -> float:
    if l and w and h:
        return (l * w * h) / 1728
    return 0.0


def _sea_engine_fixed(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 1 — Fixed Item Engine (TVs, Fridges, Sofas)
    Pre-defined fixed sea freight per item type (from value bands keyed on declared_value).
    """
    sea_freight = _resolve_value_band(engine.value_bands or [], declared_value) if engine.value_bands else engine.rate_per_cubic_ft or 35.0
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(sea_freight + port + proc + ins, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(sea_freight, 2), 0.0, round(port + proc, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_pure_cubic(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 2 — Pure Cubic Feet Engine (Boxes, Household Items)"""
    sea_freight = cubic_ft * (engine.rate_per_cubic_ft or 4.0)
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(sea_freight + port + proc + ins, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(sea_freight, 2), 0.0, round(port + proc, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_category_cubic(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 3 — Category Cubic Engine (Electronics, Fragile, Heavy Cargo)
    Category rate per cubic ft + flat handling.
    """
    sea_freight = cubic_ft * (engine.rate_per_cubic_ft or 5.5)
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(sea_freight + port + proc + ins, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(sea_freight, 2), 0.0, round(port + proc, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_hybrid(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 4 — Hybrid Sea Engine (Premium TVs, Luxury Furniture)
    Sea freight + value protection fee (tiered by declared value).
    """
    sea_freight = cubic_ft * (engine.rate_per_cubic_ft or 5.0)
    value_fee = declared_value * (engine.hybrid_value_pct or 0.04)
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    handling = port + proc + value_fee
    subtotal = max(sea_freight + handling + ins, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(sea_freight, 2), 0.0, round(handling, 2), round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_box_tier(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 5 — Box Tier Engine (Standard Boxes, Student Cargo)
    Fixed tier price from weight bands + overweight surcharge.
    """
    tier_price = _resolve_value_band(engine.value_bands or [], weight_kg) if engine.value_bands else 45.0
    overweight_surcharge = max(0, (weight_kg - 50) * 0.5)  # $0.50/kg over 50kg
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    subtotal = max(tier_price + overweight_surcharge + port + proc + ins, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(tier_price, 2), 0.0, round(port + proc + overweight_surcharge, 2),
                       round(ins, 2), round(subtotal, 2),
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_bulk(engine: PricingEngine, weight_kg: float, cubic_ft: float, declared_value: float, insurance_tier: str) -> PriceResult:
    """Sea Engine 6 — Bulk Cargo Engine
    Standard total minus cubic footage discount.
    """
    sea_freight = cubic_ft * (engine.rate_per_cubic_ft or 4.0)
    port = engine.port_handling_flat
    proc = engine.processing_fee
    ins = declared_value * INSURANCE_RATES.get(insurance_tier, INSURANCE_RATES["none"])["rate"]
    gross = sea_freight + port + proc + ins
    discount = _bulk_discount(engine.bulk_discount_tiers, cubic_ft, gross)
    subtotal = max(gross - discount, engine.sea_min_charge)
    cost, gm, mp, alert = _profitability(engine, weight_kg, subtotal, cubic_ft)
    return PriceResult(engine.code, round(sea_freight, 2), 0.0, round(port + proc, 2), round(ins, 2), round(subtotal, 2),
                       notes=f"Volume discount: -${discount:.2f}" if discount else "",
                       total_cost=cost, gross_margin=gm, margin_pct=mp, margin_alert=alert)


def _sea_engine_pallet(engine: PricingEngine, *_) -> PriceResult:
    """Sea Engine 7 — Pallet & Container Engine → custom quote."""
    return PriceResult(engine.code, 0, 0, 0, 0, 0, is_manual=True,
                       notes="Pallet/container shipments require a custom quote. Our operations team will respond within 4 hours.")


# ─────────────────────────────────────────────
#  DISPATCH TABLE
# ─────────────────────────────────────────────

_AIR_DISPATCH = {
    "AIR_FLAT":       _air_engine_flat,
    "AIR_VALUE_BAND": _air_engine_value_band,
    "AIR_HYBRID":     _air_engine_hybrid,
    "AIR_FLAT_KG":    _air_engine_flat_kg,
    "AIR_PURE_KG":    _air_engine_pure_kg,
    "AIR_PREMIUM":    _air_engine_premium,
    "AIR_BULK":       _air_engine_bulk,
    "AIR_MANUAL":     _engine_manual,
}

_SEA_DISPATCH = {
    "SEA_FIXED":         _sea_engine_fixed,
    "SEA_PURE_CUBIC":    _sea_engine_pure_cubic,
    "SEA_CATEGORY_CUBIC":_sea_engine_category_cubic,
    "SEA_HYBRID":        _sea_engine_hybrid,
    "SEA_BOX_TIER":      _sea_engine_box_tier,
    "SEA_BULK":          _sea_engine_bulk,
    "SEA_PALLET":        _sea_engine_pallet,
    "SEA_MANUAL":        _engine_manual,
}


def calculate(
    engine: PricingEngine,
    weight_kg: float,
    declared_value: float,
    insurance_tier: str = "none",
    dim_l: Optional[float] = None,
    dim_w: Optional[float] = None,
    dim_h: Optional[float] = None,
) -> PriceResult:
    """Entry point — dispatch to the correct engine formula."""
    if engine.is_manual:
        return _engine_manual(engine)

    if engine.mode == "air":
        fn = _AIR_DISPATCH.get(engine.code, _air_engine_flat_kg)
        return fn(engine, weight_kg, declared_value, insurance_tier)
    else:
        cubic_ft = _cubic_feet(dim_l, dim_w, dim_h)
        fn = _SEA_DISPATCH.get(engine.code, _sea_engine_pure_cubic)
        return fn(engine, weight_kg, cubic_ft, declared_value, insurance_tier)
