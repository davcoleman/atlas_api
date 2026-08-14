import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas.buyforme import (
    BuyForMeCreate, BuyForMeOut, AdminBuyForMeUpdate, BuyForMeListResponse,
    ScrapeRequest, ScrapedProductOut,
)
from dependencies import get_current_user, require_permission
from models.users import User, UserRole
from models.buyforme import BuyForMeRequest, BuyForMeStatus
from services.notification_service import notify_buyforme_update
from services.wallet_service import deduct

router = APIRouter(prefix="/buyforme", tags=["Buy-for-Me"])


def _gen_request_number() -> str:
    year = datetime.utcnow().strftime("%Y")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"BFM-{year}-{suffix}"


@router.post("/", response_model=BuyForMeOut, status_code=201)
def create_request(
    body: BuyForMeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = BuyForMeRequest(
        request_number=_gen_request_number(),
        customer_id=current_user.id,
        product_name=body.product_name,
        product_url=body.product_url,
        product_description=body.product_description,
        product_photo_url=body.product_photo_url,
        quantity=body.quantity,
        cost_estimate=body.cost_estimate,
        shipping_method=body.shipping_method,
        payment_option=body.payment_option,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/", response_model=BuyForMeListResponse)
def list_requests(
    status: Optional[str] = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(BuyForMeRequest)
    if current_user.role == UserRole.customer:
        q = q.filter(BuyForMeRequest.customer_id == current_user.id)
    if status:
        q = q.filter(BuyForMeRequest.status == status)
    total = q.count()
    items = q.order_by(BuyForMeRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{request_number}", response_model=BuyForMeOut)
def get_request(
    request_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(BuyForMeRequest).filter(BuyForMeRequest.request_number == request_number)
    if current_user.role == UserRole.customer:
        q = q.filter(BuyForMeRequest.customer_id == current_user.id)
    req = q.first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@router.patch("/{request_number}", response_model=BuyForMeOut)
def admin_update_request(
    request_number: str,
    body: AdminBuyForMeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("buyforme")),
):
    req = db.query(BuyForMeRequest).filter(BuyForMeRequest.request_number == request_number).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(req, field, value)

    now = datetime.utcnow()
    if body.status == BuyForMeStatus.approved and not req.approved_at:
        req.approved_at = now
        req.assigned_admin_id = current_user.id
    elif body.status == BuyForMeStatus.purchased and not req.purchased_at:
        req.purchased_at = now
        # Auto-deduct wallet if payment_option is wallet and costs are set
        if req.payment_option.value == "wallet" and body.actual_cost:
            total = (body.actual_cost or 0) + (body.shipping_cost or 0) + (body.service_fee or 0)
            req.total_cost = total
            try:
                deduct(db, req.customer_id, total, f"Buy-for-Me payment — {request_number}")
                req.payment_status = "paid"
            except Exception:
                pass
    elif body.status == BuyForMeStatus.shipped and not req.shipped_at:
        req.shipped_at = now
    elif body.status == BuyForMeStatus.delivered and not req.delivered_at:
        req.delivered_at = now

    db.commit()
    db.refresh(req)

    notify_buyforme_update(db, req.customer_id, req.request_number, req.product_name, req.status.value)
    return req


@router.delete("/{request_number}", status_code=204)
def cancel_request(
    request_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(BuyForMeRequest).filter(BuyForMeRequest.request_number == request_number)
    if current_user.role == UserRole.customer:
        q = q.filter(BuyForMeRequest.customer_id == current_user.id)
    req = q.first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status not in (BuyForMeStatus.pending,):
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    req.status = BuyForMeStatus.cancelled
    db.commit()


# ── Amazon Scraper ─────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=ScrapedProductOut)
def scrape_product_url(
    body: ScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Paste any Amazon product URL — returns product name, price, image,
    description, weight and dimensions to pre-fill the Buy-for-Me form.

    Supports:
    - amazon.com/dp/ASIN
    - amazon.com/Product-Name/dp/ASIN/ref=...
    - amazon.co.uk, amazon.ca, amazon.de (regional)
    - Short links: a.co/d/... or amzn.to/...
    """
    from services.scraper_service import scrape_amazon_url
    result = scrape_amazon_url(body.url)
    return result
