from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas.analytics import AnalyticsReport, DashboardKPIs
from dependencies import get_current_user, require_staff_or_admin
from models.users import User, UserType
from services.analytics_service import (
    get_dashboard_kpis,
    get_revenue_trend,
    get_top_routes,
    get_wallet_activity,
    get_customer_retention,
)
from services.loyalty_service import get_loyalty_summary

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=AnalyticsReport)
def dashboard(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    return {
        "kpis": get_dashboard_kpis(db),
        "revenue_trend": get_revenue_trend(db, months),
        "top_routes": get_top_routes(db),
        "wallet_activity": get_wallet_activity(db, months),
        "customer_retention": get_customer_retention(db),
        "staff_performance": [],
    }


@router.get("/kpis", response_model=DashboardKPIs)
def kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    return get_dashboard_kpis(db)


@router.get("/revenue")
def revenue_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    return get_revenue_trend(db, months)


@router.get("/routes")
def top_routes(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    return get_top_routes(db, limit)


@router.get("/wallet-activity")
def wallet_activity(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    return get_wallet_activity(db, months)


@router.get("/my-performance")
def my_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simplified 'My Performance' view for business users."""
    from models.shipments import Shipment
    from sqlalchemy import func

    total_shipments = db.query(func.count(Shipment.id)).filter(
        Shipment.user_id == current_user.id
    ).scalar() or 0

    total_spend = db.query(func.sum(Shipment.total_amount)).filter(
        Shipment.user_id == current_user.id,
        Shipment.payment_status == "paid",
    ).scalar() or 0.0

    loyalty = get_loyalty_summary(db, current_user.id)

    return {
        "total_shipments": total_shipments,
        "total_spend_usd": round(total_spend, 2),
        "loyalty_points": loyalty["total_points"],
        "loyalty_tier": loyalty["tier"],
        "referral_code": current_user.referral_code,
    }
