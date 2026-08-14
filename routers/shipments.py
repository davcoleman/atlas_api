import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from schemas.shipments import (
    ShipmentCreate, ShipmentOut, ShipmentStatusUpdate,
    StatusHistoryOut, ShipmentListResponse, ShipmentLocationUpdate,
)
from dependencies import get_current_user, require_permission
from models.users import User, UserRole
from models.shipments import Shipment, ShipmentStatus, ShipmentStatusHistory
from services.notification_service import notify_shipment_booked, notify_shipment_status
from services.wallet_service import deduct, get_or_create_wallet
from services.geo_service import resolve_country_coords

router = APIRouter(prefix="/shipments", tags=["Shipments"])


def _gen_tracking() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"ATL-{date_str}-{suffix}"


def price_shipment(db: Session, body: ShipmentCreate, customer_type: str = "retail"):
    """Run a shipment through the same pricing engine /quotes/calculate uses.

    Used as a fallback whenever a shipment is created without an accepted
    SavedQuote attached (e.g. the customer "New Shipment" form), so it never
    silently lands with total_amount = 0.
    """
    from models.catalog import CatalogItem
    from routers.quotes import _resolve_engine
    from services import pricing_engine as engine_svc

    catalog_item = None
    if body.product_id:
        catalog_item = db.query(CatalogItem).filter(CatalogItem.product_id == body.product_id).first()
    if not catalog_item and body.item_name:
        catalog_item = db.query(CatalogItem).filter(
            CatalogItem.item_name.ilike(body.item_name)
        ).first()

    category = (catalog_item.category if catalog_item else body.category) or "General Goods"
    engine_hint = catalog_item.default_engine_hint if catalog_item else None

    engine = _resolve_engine(
        db,
        body.product_id or (catalog_item.product_id if catalog_item else None),
        category,
        engine_hint,
        body.shipping_mode.value,
        customer_type,
    )
    result = engine_svc.calculate(
        engine,
        weight_kg=body.weight_kg * body.quantity,
        declared_value=body.declared_value_usd * body.quantity,
        insurance_tier=body.insurance_tier,
        dim_l=body.dim_l, dim_w=body.dim_w, dim_h=body.dim_h,
    )
    return engine.code, result


def apply_default_coords(shipment: Shipment) -> None:
    """Seed origin/current/destination pins from the country hub lookup so the
    tracking map has something to plot before an admin sets a live position."""
    origin_coords = resolve_country_coords(shipment.origin_country or "USA")
    dest_coords = resolve_country_coords(shipment.destination_country or "Ghana")
    if origin_coords:
        shipment.origin_lat, shipment.origin_lng = origin_coords
        shipment.current_lat, shipment.current_lng = origin_coords
        shipment.current_location_label = shipment.origin_address or shipment.origin_country or "Origin"
    if dest_coords:
        shipment.destination_lat, shipment.destination_lng = dest_coords


@router.post("/", response_model=ShipmentOut, status_code=201)
def create_shipment(
    body: ShipmentCreate,
    pay_from_wallet: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Estimate total from a linked, previously-accepted quote if available
    total_amount = 0.0
    engine_code = None
    base_shipping = vat_amount = handling_fee = insurance_premium = 0.0

    if body.quote_reference:
        from models.quotes import SavedQuote
        quote = db.query(SavedQuote).filter(SavedQuote.reference_id == body.quote_reference).first()
        if quote:
            total_amount = quote.subtotal
            engine_code = quote.engine_code
            base_shipping, vat_amount = quote.base_shipping, quote.vat_amount
            handling_fee, insurance_premium = quote.handling_fee, quote.insurance_premium

    if total_amount <= 0:
        # No accepted quote attached (e.g. the "New Shipment" dashboard form) —
        # price it live so it never lands in the admin panel showing $0.00.
        engine_code, result = price_shipment(db, body)
        total_amount = result.subtotal
        base_shipping, vat_amount = result.base_shipping, result.vat_amount
        handling_fee, insurance_premium = result.handling_fee, result.insurance_premium

    shipment = Shipment(
        tracking_number=_gen_tracking(),
        user_id=current_user.id,
        quote_reference=body.quote_reference,
        item_name=body.item_name,
        product_id=body.product_id,
        category=body.category,
        quantity=body.quantity,
        weight_kg=body.weight_kg,
        declared_value_usd=body.declared_value_usd,
        dim_l=body.dim_l,
        dim_w=body.dim_w,
        dim_h=body.dim_h,
        shipping_mode=body.shipping_mode,
        origin_address=body.origin_address,
        destination_address=body.destination_address,
        insurance_tier=body.insurance_tier,
        engine_code=engine_code,
        base_shipping=base_shipping,
        vat_amount=vat_amount,
        handling_fee=handling_fee,
        insurance_premium=insurance_premium,
        total_amount=total_amount,
        notes=body.notes,
        estimated_arrival=datetime.utcnow() + timedelta(days=14 if body.shipping_mode.value == "sea" else 7),
    )
    apply_default_coords(shipment)

    if pay_from_wallet and total_amount > 0:
        wallet = get_or_create_wallet(db, current_user.id)
        if wallet.balance >= total_amount:
            deduct(db, current_user.id, total_amount, f"Shipment payment — {shipment.tracking_number}")
            shipment.payment_status = "paid"

    db.add(shipment)
    db.flush()

    # Record initial status history
    history = ShipmentStatusHistory(
        shipment_id=shipment.id,
        new_status=shipment.status.value,
        note="Shipment created",
        changed_by=current_user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(shipment)

    notify_shipment_booked(db, current_user.id, shipment.tracking_number, shipment.item_name)
    return shipment


@router.get("/", response_model=ShipmentListResponse)
def list_shipments(
    status: Optional[str] = Query(None),
    shipping_mode: Optional[str] = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Shipment)
    if current_user.role == UserRole.customer:
        q = q.filter(Shipment.user_id == current_user.id)
    if status:
        q = q.filter(Shipment.status == status)
    if shipping_mode:
        q = q.filter(Shipment.shipping_mode == shipping_mode)

    total = q.count()
    items = q.order_by(Shipment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{tracking_number}", response_model=ShipmentOut)
def get_shipment(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Shipment).filter(Shipment.tracking_number == tracking_number)
    if current_user.role == UserRole.customer:
        q = q.filter(Shipment.user_id == current_user.id)
    shipment = q.first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.get("/{tracking_number}/history", response_model=List[StatusHistoryOut])
def get_status_history(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(Shipment.tracking_number == tracking_number).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if current_user.role == UserRole.customer and shipment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(ShipmentStatusHistory).filter(
        ShipmentStatusHistory.shipment_id == shipment.id
    ).order_by(ShipmentStatusHistory.created_at.asc()).all()


@router.patch("/{tracking_number}/status", response_model=ShipmentOut)
def update_status(
    tracking_number: str,
    body: ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("shipments")),
):
    shipment = db.query(Shipment).filter(Shipment.tracking_number == tracking_number).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    history = ShipmentStatusHistory(
        shipment_id=shipment.id,
        previous_status=shipment.status.value,
        new_status=body.status.value,
        note=body.note,
        changed_by=current_user.id,
    )
    db.add(history)

    shipment.status = body.status
    if body.estimated_arrival:
        shipment.estimated_arrival = body.estimated_arrival
    if body.status == ShipmentStatus.delivered:
        shipment.delivered_at = datetime.utcnow()
        shipment.payment_status = "paid"
        shipment.progress_percent = 100
        if shipment.destination_lat is not None and shipment.destination_lng is not None:
            shipment.current_lat = shipment.destination_lat
            shipment.current_lng = shipment.destination_lng
            shipment.current_location_label = shipment.destination_address or shipment.destination_country

    db.commit()
    db.refresh(shipment)

    notify_shipment_status(db, shipment.user_id, shipment.tracking_number, body.status.value)
    return shipment


@router.patch("/{tracking_number}/location", response_model=ShipmentOut)
def update_location(
    tracking_number: str,
    body: ShipmentLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("shipments")),
):
    shipment = db.query(Shipment).filter(Shipment.tracking_number == tracking_number).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment.current_lat = body.current_lat
    shipment.current_lng = body.current_lng
    if body.current_location_label:
        shipment.current_location_label = body.current_location_label
    if body.progress_percent is not None:
        shipment.progress_percent = max(0, min(100, body.progress_percent))

    if body.note:
        history = ShipmentStatusHistory(
            shipment_id=shipment.id,
            previous_status=shipment.status.value,
            new_status=shipment.status.value,
            note=body.note,
            changed_by=current_user.id,
        )
        db.add(history)

    db.commit()
    db.refresh(shipment)
    return shipment


@router.patch("/{tracking_number}/pay", response_model=ShipmentOut)
def pay_from_wallet(
    tracking_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = db.query(Shipment).filter(
        Shipment.tracking_number == tracking_number,
        Shipment.user_id == current_user.id,
    ).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if shipment.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Already paid")

    deduct(db, current_user.id, shipment.total_amount,
           f"Shipment payment — {shipment.tracking_number}", shipment_id=shipment.id)
    shipment.payment_status = "paid"
    db.commit()
    db.refresh(shipment)
    return shipment
