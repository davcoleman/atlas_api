from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from dependencies import require_super_admin, require_staff_or_admin, require_permission
from models.users import User, UserRole, UserType, BusinessProfile
from models.shipments import Shipment, ShipmentStatus, ShipmentStatusHistory
from models.wallet import Wallet, WalletTransaction, TransactionStatus, TransactionType
from models.tickets import SupportTicket, TicketStatus
from models.buyforme import BuyForMeRequest, BuyForMeStatus
from models.notifications import Notification
from schemas.shipments import ShipmentOut, AdminShipmentOut, AdminShipmentCreate
from schemas.wallet import WalletTransactionOut
from schemas.users import UserOut, StaffCreate, StaffUpdate
from schemas.buyforme import AdminBuyForMeOut
from services.permissions import PERMISSION_CATALOG, parse_permissions, serialize_permissions
from services.auth_service import hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])

WALLET_LEGACY_ROLES = (UserRole.finance_admin,)


# ── Overview ───────────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    from services.analytics_service import get_dashboard_kpis
    return get_dashboard_kpis(db)


@router.get("/dashboard-summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    from services.analytics_service import get_admin_dashboard_summary
    return get_admin_dashboard_summary(db)


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_all_users(
    role: Optional[str] = None,
    user_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if user_type:
        q = q.filter(User.user_type == user_type)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    return q.offset(skip).limit(limit).all()


@router.get("/users/business")
def list_business_users(
    discount_eligible: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers")),
):
    from models.users import BusinessProfile, UserType  # noqa: F811
    q = db.query(User, BusinessProfile).join(
        BusinessProfile, User.id == BusinessProfile.user_id
    ).filter(User.user_type == UserType.business)
    if discount_eligible is not None:
        q = q.filter(BusinessProfile.discount_eligible == discount_eligible)
    rows = q.offset(skip).limit(limit).all()
    return [
        {
            "user": r[0].__dict__,
            "business_profile": r[1].__dict__,
        }
        for r in rows
    ]


# ── Customers ─────────────────────────────────────────────────────────────────

@router.get("/customers")
def list_customers(
    search: Optional[str] = None,
    user_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers")),
):
    q = db.query(User).filter(User.role == UserRole.customer)
    if user_type:
        q = q.filter(User.user_type == user_type)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))

    total = q.count()
    users = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for u in users:
        shipment_count = db.query(func.count(Shipment.id)).filter(Shipment.user_id == u.id).scalar() or 0
        wallet = db.query(Wallet).filter(Wallet.user_id == u.id).first()
        phone = None
        if u.user_type == UserType.business:
            bp = db.query(BusinessProfile).filter(BusinessProfile.user_id == u.id).first()
            phone = bp.contact_number if bp else None
        items.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": phone,
            "user_type": u.user_type.value,
            "is_active": u.is_active,
            "shipment_count": shipment_count,
            "wallet_balance": round(wallet.balance, 2) if wallet else 0.0,
            "created_at": u.created_at,
        })
    return {"total": total, "items": items}


@router.get("/customers/stats")
def customers_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customers")),
):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = db.query(func.count(User.id)).filter(User.role == UserRole.customer).scalar() or 0
    business = db.query(func.count(User.id)).filter(
        User.role == UserRole.customer, User.user_type == UserType.business
    ).scalar() or 0
    personal = total - business
    new_this_month = db.query(func.count(User.id)).filter(
        User.role == UserRole.customer, User.created_at >= month_start
    ).scalar() or 0
    active_this_month = db.query(func.count(func.distinct(Shipment.user_id))).filter(
        Shipment.created_at >= month_start
    ).scalar() or 0

    return {
        "total_customers": total,
        "business_accounts": business,
        "personal_accounts": personal,
        "new_this_month": new_this_month,
        "active_this_month": active_this_month,
    }


# ── Shipments ─────────────────────────────────────────────────────────────────

@router.get("/shipments", response_model=List[AdminShipmentOut])
def all_shipments(
    status: Optional[str] = None,
    shipping_mode: Optional[str] = None,
    user_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("shipments")),
):
    q = db.query(Shipment, User).join(User, User.id == Shipment.user_id)
    if status:
        q = q.filter(Shipment.status == status)
    if shipping_mode:
        q = q.filter(Shipment.shipping_mode == shipping_mode)
    if user_id:
        q = q.filter(Shipment.user_id == user_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            User.full_name.ilike(like),
            User.email.ilike(like),
            Shipment.tracking_number.ilike(like),
        ))

    rows = q.order_by(Shipment.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for s, u in rows:
        item = AdminShipmentOut.model_validate(s)
        item.customer_name = u.full_name
        item.customer_email = u.email
        results.append(item)
    return results


@router.get("/shipments/stats")
def shipments_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("shipments")),
):
    def _count(status):
        return db.query(func.count(Shipment.id)).filter(Shipment.status == status).scalar() or 0

    return {
        "total": db.query(func.count(Shipment.id)).scalar() or 0,
        "pending": _count(ShipmentStatus.pending),
        "in_transit": _count(ShipmentStatus.in_transit),
        "delivered": _count(ShipmentStatus.delivered),
        "on_hold": _count(ShipmentStatus.on_hold),
        "cancelled": _count(ShipmentStatus.cancelled),
    }


@router.post("/shipments", response_model=AdminShipmentOut, status_code=201)
def admin_create_shipment(
    body: AdminShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("shipments")),
):
    customer = db.query(User).filter(
        User.id == body.customer_id, User.role == UserRole.customer
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from routers.shipments import _gen_tracking, apply_default_coords, price_shipment
    from services.notification_service import notify_shipment_booked

    total_amount = body.total_amount or 0.0
    engine_code = base_shipping = vat_amount = handling_fee = insurance_premium = None
    if total_amount <= 0:
        # Admin left the amount blank — price it live instead of booking at $0.
        engine_code, result = price_shipment(db, body)
        total_amount = result.subtotal
        base_shipping, vat_amount = result.base_shipping, result.vat_amount
        handling_fee, insurance_premium = result.handling_fee, result.insurance_premium

    shipment = Shipment(
        tracking_number=_gen_tracking(),
        user_id=customer.id,
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
        base_shipping=base_shipping or 0.0,
        vat_amount=vat_amount or 0.0,
        handling_fee=handling_fee or 0.0,
        insurance_premium=insurance_premium or 0.0,
        total_amount=total_amount,
        notes=body.notes,
        assigned_staff_id=current_user.id,
        estimated_arrival=datetime.utcnow() + timedelta(days=14 if body.shipping_mode.value == "sea" else 7),
    )
    apply_default_coords(shipment)
    db.add(shipment)
    db.flush()

    history = ShipmentStatusHistory(
        shipment_id=shipment.id,
        new_status=shipment.status.value,
        note=f"Created by admin ({current_user.full_name})",
        changed_by=current_user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(shipment)

    notify_shipment_booked(db, customer.id, shipment.tracking_number, shipment.item_name)

    result = AdminShipmentOut.model_validate(shipment)
    result.customer_name = customer.full_name
    result.customer_email = customer.email
    return result


# ── Wallet Ledger ─────────────────────────────────────────────────────────────

@router.get("/wallet/ledger", response_model=List[WalletTransactionOut])
def admin_full_ledger(
    user_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wallet", legacy_full_access_roles=WALLET_LEGACY_ROLES)),
):
    q = db.query(WalletTransaction)
    if user_id:
        q = q.filter(WalletTransaction.user_id == user_id)
    if transaction_type:
        q = q.filter(WalletTransaction.transaction_type == transaction_type)
    if status:
        q = q.filter(WalletTransaction.status == status)
    return q.order_by(WalletTransaction.created_at.desc()).offset(skip).limit(limit).all()


# ── Tickets ───────────────────────────────────────────────────────────────────

@router.get("/tickets")
def all_tickets(
    status: Optional[str] = None,
    assigned_to: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tickets")),
):
    q = db.query(SupportTicket)
    if status:
        q = q.filter(SupportTicket.status == status)
    if assigned_to:
        q = q.filter(SupportTicket.assigned_to == assigned_to)
    return q.order_by(SupportTicket.created_at.desc()).offset(skip).limit(limit).all()


@router.patch("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tickets")),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.assigned_to = agent_id
    ticket.status = TicketStatus.in_progress
    db.commit()
    return {"message": f"Ticket assigned to agent {agent_id}"}


# ── Buy-for-Me ────────────────────────────────────────────────────────────────

@router.get("/buyforme", response_model=List[AdminBuyForMeOut])
def all_buyforme(
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("buyforme")),
):
    q = db.query(BuyForMeRequest, User).join(User, User.id == BuyForMeRequest.customer_id)
    if status:
        q = q.filter(BuyForMeRequest.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            User.full_name.ilike(like),
            User.email.ilike(like),
            BuyForMeRequest.product_name.ilike(like),
            BuyForMeRequest.request_number.ilike(like),
        ))

    rows = q.order_by(BuyForMeRequest.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for req, user in rows:
        item = AdminBuyForMeOut.model_validate(req)
        item.customer_name = user.full_name
        item.customer_email = user.email
        results.append(item)
    return results


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports/shipment-volume")
def shipment_volume_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics")),
):
    from services.analytics_service import get_revenue_trend, get_top_routes
    return {
        "revenue_trend": get_revenue_trend(db, 12),
        "top_routes": get_top_routes(db, 10),
    }


@router.get("/reports/wallet-summary")
def wallet_summary_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wallet", legacy_full_access_roles=WALLET_LEGACY_ROLES)),
):
    from sqlalchemy import func
    from models.wallet import Wallet
    total_balance = db.query(func.sum(Wallet.balance)).scalar() or 0.0
    pending_deposits = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).scalar() or 0.0
    total_processed = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.status == TransactionStatus.completed,
    ).scalar() or 0.0
    return {
        "total_wallet_balance": round(total_balance, 2),
        "pending_deposits": round(pending_deposits, 2),
        "total_processed_volume": round(total_processed, 2),
    }


# ── Staff ─────────────────────────────────────────────────────────────────────
# Only a super_admin can create/edit staff or grant privileges — letting a staff
# account manage other staff would let it escalate its own access.

@router.get("/staff/permissions")
def list_permission_catalog(current_user: User = Depends(require_super_admin)):
    return [{"key": k, "label": v} for k, v in PERMISSION_CATALOG.items()]


@router.get("/staff", response_model=List[UserOut])
def list_staff(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    q = db.query(User).filter(User.role != UserRole.customer)
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    return q.order_by(User.created_at.desc()).all()


@router.post("/staff", response_model=UserOut, status_code=201)
def create_staff(
    body: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    staff = User(
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
        is_verified=True,
        permissions=serialize_permissions(body.permissions),
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.patch("/staff/{user_id}", response_model=UserOut)
def update_staff(
    user_id: int,
    body: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    staff = db.query(User).filter(User.id == user_id, User.role != UserRole.customer).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff account not found")
    if staff.role == UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Cannot modify a super admin account")

    if body.full_name is not None:
        staff.full_name = body.full_name
    if body.role is not None:
        staff.role = body.role
    if body.permissions is not None:
        staff.permissions = serialize_permissions(body.permissions)
    if body.is_active is not None:
        staff.is_active = body.is_active

    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/staff/{user_id}", status_code=204)
def deactivate_staff(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    staff = db.query(User).filter(User.id == user_id, User.role != UserRole.customer).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff account not found")
    if staff.role == UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Cannot deactivate a super admin account")

    staff.is_active = False
    staff.permissions = ""
    db.commit()
