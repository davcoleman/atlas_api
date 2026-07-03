from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import re

from database import get_db
from models.catalog import CatalogItem
from models.engines import PricingEngine, EngineConfig
from models.quotes import SavedQuote
from schemas.quotes import QuoteRequest, QuoteOut, QuoteBreakdown, SaveQuoteRequest
from services import pricing_engine as engine_svc

router = APIRouter(prefix="/quotes", tags=["Quotes"])

# ── Reference ID generator ──────────────────────────────────────────────────

def _next_reference_id(db: Session) -> str:
    year = datetime.utcnow().year
    prefix = f"AFL-{year}-"
    last = (
        db.query(SavedQuote)
        .filter(SavedQuote.reference_id.like(f"{prefix}%"))
        .order_by(SavedQuote.id.desc())
        .first()
    )
    if last:
        try:
            seq = int(re.sub(r"\D", "", last.reference_id.split("-")[-1])) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{str(seq).zfill(6)}"


# ── Engine resolution ────────────────────────────────────────────────────────

def _resolve_engine(
    db: Session,
    product_id: str | None,
    category: str | None,
    default_engine_hint: str | None,
    shipping_mode: str,
    customer_type: str,
) -> PricingEngine:
    """
    Priority:
    1. Product-level override (EngineConfig target_type='product')
    2. Category engine mapping  (EngineConfig target_type='category')
    3. Default system engine (first active engine for this mode)
    """
    # P1 — product override
    if product_id:
        cfg = (
            db.query(EngineConfig)
            .filter(
                EngineConfig.target_type == "product",
                EngineConfig.target_value == product_id,
                EngineConfig.is_active == True,
                EngineConfig.customer_type.in_([customer_type, "retail"]),
            )
            .order_by(EngineConfig.priority)
            .first()
        )
        if cfg:
            eng = db.query(PricingEngine).filter(PricingEngine.id == cfg.engine_id, PricingEngine.is_active == True).first()
            if eng:
                return eng

    # P2 — category mapping (join on PricingEngine.mode to avoid returning wrong-mode engine)
    if category:
        cfg = (
            db.query(EngineConfig)
            .join(PricingEngine, PricingEngine.id == EngineConfig.engine_id)
            .filter(
                EngineConfig.target_type == "category",
                func.lower(EngineConfig.target_value) == category.lower(),
                EngineConfig.is_active == True,
                EngineConfig.customer_type.in_([customer_type, "retail"]),
                PricingEngine.mode == shipping_mode,
                PricingEngine.is_active == True,
            )
            .order_by(EngineConfig.priority)
            .first()
        )
        if cfg:
            eng = db.query(PricingEngine).filter(PricingEngine.id == cfg.engine_id).first()
            if eng:
                return eng

    # P3 — hint-based fallback from catalog
    if default_engine_hint:
        hint_map = {
            "FLAT":       f"AIR_FLAT"       if shipping_mode == "air" else "SEA_FIXED",
            "HYBRID":     f"AIR_HYBRID"     if shipping_mode == "air" else "SEA_HYBRID",
            "VALUE_BAND": f"AIR_VALUE_BAND" if shipping_mode == "air" else "SEA_BOX_TIER",
            "KG":         f"AIR_PURE_KG"    if shipping_mode == "air" else "SEA_PURE_CUBIC",
            "FIXED":      "SEA_FIXED",
            "CUSTOM":     f"AIR_MANUAL"     if shipping_mode == "air" else "SEA_MANUAL",
        }
        code = hint_map.get(default_engine_hint)
        if code:
            eng = db.query(PricingEngine).filter(PricingEngine.code == code, PricingEngine.is_active == True).first()
            if eng:
                return eng

    # P4 — absolute fallback: first active engine for this mode
    fallback_code = "AIR_FLAT_KG" if shipping_mode == "air" else "SEA_PURE_CUBIC"
    eng = db.query(PricingEngine).filter(PricingEngine.code == fallback_code, PricingEngine.is_active == True).first()
    if eng:
        return eng

    raise HTTPException(status_code=500, detail="No active pricing engine found — please seed the database.")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/calculate", response_model=QuoteOut)
def calculate_quote(req: QuoteRequest, db: Session = Depends(get_db)):
    """
    Calculate a shipping quote without saving it.
    Resolves the correct pricing engine and runs the formula.
    """
    # Look up catalog item if product_id or item_name given
    catalog_item: CatalogItem | None = None
    if req.product_id:
        catalog_item = db.query(CatalogItem).filter(CatalogItem.product_id == req.product_id).first()
    if not catalog_item and req.item_name:
        catalog_item = (
            db.query(CatalogItem)
            .filter(func.lower(CatalogItem.item_name) == req.item_name.lower())
            .first()
        )

    category = (catalog_item.category if catalog_item else req.category) or "General Goods"
    engine_hint = catalog_item.default_engine_hint if catalog_item else None
    weight = (catalog_item.avg_weight_kg if catalog_item and req.weight_kg == 0 else req.weight_kg)
    l = req.dim_l_inches or (catalog_item.dim_l_inches if catalog_item else None)
    w = req.dim_w_inches or (catalog_item.dim_w_inches if catalog_item else None)
    h = req.dim_h_inches or (catalog_item.dim_h_inches if catalog_item else None)
    display_name = req.item_name or (catalog_item.item_name if catalog_item else "Unknown Item")

    engine = _resolve_engine(
        db,
        req.product_id or (catalog_item.product_id if catalog_item else None),
        category,
        engine_hint,
        req.shipping_mode,
        req.customer_type,
    )

    result = engine_svc.calculate(
        engine,
        weight_kg=weight * req.quantity,
        declared_value=req.declared_value_usd * req.quantity,
        insurance_tier=req.insurance_tier,
        dim_l=l, dim_w=w, dim_h=h,
    )

    breakdown = QuoteBreakdown(
        base_shipping=result.base_shipping,
        vat_amount=result.vat_amount,
        handling_fee=result.handling_fee,
        insurance_premium=result.insurance_premium,
        duty_estimate=0.0,
        subtotal=result.subtotal,
        total_cost=result.total_cost,
        gross_margin=result.gross_margin,
        margin_pct=result.margin_pct,
        margin_alert=result.margin_alert,
    )

    return QuoteOut(
        reference_id="PREVIEW",
        item_name=display_name,
        shipping_mode=req.shipping_mode,
        weight_kg=weight * req.quantity,
        declared_value_usd=req.declared_value_usd * req.quantity,
        engine_code=engine.code,
        insurance_tier=req.insurance_tier,
        breakdown=breakdown,
        is_manual=result.is_manual,
        notes=result.notes or None,
    )


@router.post("/save", response_model=QuoteOut)
def save_quote(req: SaveQuoteRequest, db: Session = Depends(get_db)):
    """Save an accepted quote and assign a permanent AFL-YYYY-XXXXXX reference ID."""
    ref_id = _next_reference_id(db)
    expires = datetime.utcnow() + timedelta(hours=72)
    q = req.quote

    row = SavedQuote(
        reference_id=ref_id,
        item_name=q.item_name,
        shipping_mode=q.shipping_mode,
        weight_kg=q.weight_kg,
        declared_value_usd=q.declared_value_usd,
        engine_code=q.engine_code,
        insurance_tier=q.insurance_tier,
        base_shipping=q.breakdown.base_shipping,
        vat_amount=q.breakdown.vat_amount,
        handling_fee=q.breakdown.handling_fee,
        insurance_premium=q.breakdown.insurance_premium,
        duty_estimate=q.breakdown.duty_estimate,
        subtotal=q.breakdown.subtotal,
        total_cost=q.breakdown.total_cost,
        gross_margin=q.breakdown.gross_margin,
        margin_pct=q.breakdown.margin_pct,
        margin_alert=q.breakdown.margin_alert,
        is_manual=q.is_manual,
        notes=q.notes,
        expires_at=expires,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    q.reference_id = ref_id
    q.expires_at = expires
    return q


@router.get("/{reference_id}", response_model=QuoteOut)
def get_quote(reference_id: str, db: Session = Depends(get_db)):
    row = db.query(SavedQuote).filter(SavedQuote.reference_id == reference_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Quote not found")
    return QuoteOut(
        reference_id=row.reference_id,
        item_name=row.item_name,
        shipping_mode=row.shipping_mode,
        weight_kg=row.weight_kg,
        declared_value_usd=row.declared_value_usd,
        engine_code=row.engine_code or "",
        insurance_tier=row.insurance_tier,
        breakdown=QuoteBreakdown(
            base_shipping=row.base_shipping,
            vat_amount=row.vat_amount,
            handling_fee=row.handling_fee,
            insurance_premium=row.insurance_premium,
            duty_estimate=row.duty_estimate,
            subtotal=row.subtotal,
            total_cost=row.total_cost,
            gross_margin=row.gross_margin,
            margin_pct=row.margin_pct,
            margin_alert=row.margin_alert or False,
        ),
        is_manual=row.is_manual or False,
        expires_at=row.expires_at,
        notes=row.notes,
    )
