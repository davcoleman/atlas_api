from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from typing import List

from models.shipments import Shipment, ShipmentStatus
from models.wallet import Wallet, WalletTransaction, TransactionType, TransactionStatus
from models.tickets import SupportTicket, TicketStatus
from models.buyforme import BuyForMeRequest, BuyForMeStatus
from models.users import User, UserRole

ACTIVE_SHIPMENT_STATUSES = [
    ShipmentStatus.confirmed, ShipmentStatus.processing, ShipmentStatus.in_transit,
    ShipmentStatus.arrived, ShipmentStatus.out_for_delivery,
]


def get_dashboard_kpis(db: Session) -> dict:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Revenue (sum of shipment amounts this month vs last)
    revenue_this = db.query(func.sum(Shipment.total_amount)).filter(
        Shipment.payment_status == "paid",
        Shipment.created_at >= month_start,
    ).scalar() or 0.0

    revenue_last = db.query(func.sum(Shipment.total_amount)).filter(
        Shipment.payment_status == "paid",
        Shipment.created_at >= prev_month_start,
        Shipment.created_at < month_start,
    ).scalar() or 0.0

    revenue_change = ((revenue_this - revenue_last) / revenue_last * 100) if revenue_last else 0.0

    # Shipment counts
    ships_this = db.query(func.count(Shipment.id)).filter(Shipment.created_at >= month_start).scalar() or 0
    ships_last = db.query(func.count(Shipment.id)).filter(
        Shipment.created_at >= prev_month_start, Shipment.created_at < month_start
    ).scalar() or 0
    ships_change = ((ships_this - ships_last) / ships_last * 100) if ships_last else 0.0

    # Active customers (shipped at least once)
    active_this = db.query(func.count(func.distinct(Shipment.user_id))).filter(
        Shipment.created_at >= month_start
    ).scalar() or 0
    active_last = db.query(func.count(func.distinct(Shipment.user_id))).filter(
        Shipment.created_at >= prev_month_start, Shipment.created_at < month_start
    ).scalar() or 0
    cust_change = ((active_this - active_last) / active_last * 100) if active_last else 0.0

    # Wallet totals
    total_wallet = db.query(func.sum(Wallet.balance)).scalar() or 0.0
    pending_deps = db.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).scalar() or 0.0

    # Support
    open_tickets = db.query(func.count(SupportTicket.id)).filter(
        SupportTicket.status.in_([TicketStatus.pending, TicketStatus.in_progress])
    ).scalar() or 0

    pending_bfm = db.query(func.count(BuyForMeRequest.id)).filter(
        BuyForMeRequest.status == BuyForMeStatus.pending
    ).scalar() or 0

    return {
        "total_revenue": revenue_this,
        "revenue_change_pct": round(revenue_change, 2),
        "total_shipments": ships_this,
        "shipments_change_pct": round(ships_change, 2),
        "active_customers": active_this,
        "customers_change_pct": round(cust_change, 2),
        "wallet_balance_total": total_wallet,
        "pending_deposits": pending_deps,
        "open_tickets": open_tickets,
        "pending_buyforme": pending_bfm,
    }


def get_revenue_trend(db: Session, months: int = 6) -> List[dict]:
    result = []
    now = datetime.utcnow()
    for i in range(months - 1, -1, -1):
        target = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        next_month = (target.replace(day=28) + timedelta(days=4)).replace(day=1)

        revenue = db.query(func.sum(Shipment.total_amount)).filter(
            Shipment.payment_status == "paid",
            Shipment.created_at >= target,
            Shipment.created_at < next_month,
        ).scalar() or 0.0

        count = db.query(func.count(Shipment.id)).filter(
            Shipment.created_at >= target,
            Shipment.created_at < next_month,
        ).scalar() or 0

        result.append({
            "period": target.strftime("%Y-%m"),
            "revenue": round(revenue, 2),
            "shipment_count": count,
        })
    return result


def get_top_routes(db: Session, limit: int = 5) -> List[dict]:
    rows = db.query(
        Shipment.origin_country,
        Shipment.destination_country,
        func.count(Shipment.id).label("count"),
        func.sum(Shipment.total_amount).label("revenue"),
        func.avg(Shipment.total_amount).label("avg_value"),
    ).group_by(Shipment.origin_country, Shipment.destination_country).order_by(
        func.count(Shipment.id).desc()
    ).limit(limit).all()

    return [
        {
            "route": f"{r.origin_country} → {r.destination_country}",
            "shipment_count": r.count,
            "total_revenue": round(float(r.revenue or 0), 2),
            "avg_value": round(float(r.avg_value or 0), 2),
        }
        for r in rows
    ]


def get_wallet_activity(db: Session, months: int = 6) -> List[dict]:
    result = []
    now = datetime.utcnow()
    for i in range(months - 1, -1, -1):
        target = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        next_month = (target.replace(day=28) + timedelta(days=4)).replace(day=1)

        def _sum(t_type):
            return db.query(func.sum(WalletTransaction.amount)).filter(
                WalletTransaction.transaction_type == t_type,
                WalletTransaction.status == TransactionStatus.completed,
                WalletTransaction.created_at >= target,
                WalletTransaction.created_at < next_month,
            ).scalar() or 0.0

        deps = _sum(TransactionType.deposit)
        deds = _sum(TransactionType.deduction)
        refs = _sum(TransactionType.refund)

        result.append({
            "period": target.strftime("%Y-%m"),
            "deposits": round(deps, 2),
            "deductions": round(deds, 2),
            "refunds": round(refs, 2),
            "net": round(deps - deds + refs, 2),
        })
    return result


def get_customer_retention(db: Session) -> dict:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = db.query(func.count(User.id)).scalar() or 0
    active = db.query(func.count(func.distinct(Shipment.user_id))).filter(
        Shipment.created_at >= month_start - timedelta(days=90)
    ).scalar() or 0
    new_month = db.query(func.count(User.id)).filter(User.created_at >= month_start).scalar() or 0
    repeat_subq = db.query(Shipment.user_id).group_by(Shipment.user_id).having(
        func.count(Shipment.id) > 1
    ).subquery()
    repeat = db.query(func.count()).select_from(repeat_subq).scalar() or 0

    retention = (active / total * 100) if total else 0.0
    return {
        "total_customers": total,
        "active_customers": active,
        "new_this_month": new_month,
        "repeat_customers": 0,
        "retention_rate": round(retention, 2),
    }


def _pct_change(this_period: float, last_period: float) -> float:
    if not last_period:
        return 0.0
    return round((this_period - last_period) / last_period * 100, 2)


def get_admin_dashboard_summary(db: Session) -> dict:
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Revenue (paid shipments, this month vs last)
    def _revenue(start, end=None):
        q = db.query(func.sum(Shipment.total_amount)).filter(
            Shipment.payment_status == "paid",
            Shipment.created_at >= start,
        )
        if end:
            q = q.filter(Shipment.created_at < end)
        return q.scalar() or 0.0

    revenue_this = _revenue(month_start)
    revenue_last = _revenue(prev_month_start, month_start)

    # Shipment volume (created this month vs last, as an activity signal)
    def _ship_count(start, end=None):
        q = db.query(func.count(Shipment.id)).filter(Shipment.created_at >= start)
        if end:
            q = q.filter(Shipment.created_at < end)
        return q.scalar() or 0

    shipments_this = _ship_count(month_start)
    shipments_last = _ship_count(prev_month_start, month_start)

    # Active shipments right now (current snapshot, not time-windowed)
    active_shipments_count = db.query(func.count(Shipment.id)).filter(
        Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES)
    ).scalar() or 0

    # Customers
    total_customers = db.query(func.count(User.id)).filter(User.role == UserRole.customer).scalar() or 0
    customers_this = db.query(func.count(User.id)).filter(
        User.role == UserRole.customer, User.created_at >= month_start
    ).scalar() or 0
    customers_last = db.query(func.count(User.id)).filter(
        User.role == UserRole.customer, User.created_at >= prev_month_start, User.created_at < month_start
    ).scalar() or 0

    # Deliveries today vs yesterday
    deliveries_today = db.query(func.count(Shipment.id)).filter(
        Shipment.delivered_at >= today_start
    ).scalar() or 0
    deliveries_yesterday = db.query(func.count(Shipment.id)).filter(
        Shipment.delivered_at >= yesterday_start, Shipment.delivered_at < today_start
    ).scalar() or 0

    # Recent shipments (joined with customer name)
    recent_rows = db.query(Shipment, User).join(User, User.id == Shipment.user_id).order_by(
        Shipment.created_at.desc()
    ).limit(5).all()
    recent_shipments = [
        {
            "tracking_number": s.tracking_number,
            "customer_name": u.full_name,
            "origin_country": s.origin_country,
            "destination_country": s.destination_country,
            "status": s.status.value,
            "total_amount": round(s.total_amount, 2),
            "currency": s.currency,
        }
        for s, u in recent_rows
    ]

    # Pending actions
    pending_deposits_count = db.query(func.count(WalletTransaction.id)).filter(
        WalletTransaction.transaction_type == TransactionType.deposit,
        WalletTransaction.status == TransactionStatus.pending,
    ).scalar() or 0

    shipments_on_hold_count = db.query(func.count(Shipment.id)).filter(
        Shipment.status == ShipmentStatus.on_hold
    ).scalar() or 0

    pending_buyforme_count = db.query(func.count(BuyForMeRequest.id)).filter(
        BuyForMeRequest.status == BuyForMeStatus.pending
    ).scalar() or 0

    open_tickets_count = db.query(func.count(SupportTicket.id)).filter(
        SupportTicket.status.in_([TicketStatus.pending, TicketStatus.in_progress])
    ).scalar() or 0

    # Quick stats
    in_transit_count = db.query(func.count(Shipment.id)).filter(
        Shipment.status == ShipmentStatus.in_transit
    ).scalar() or 0
    pending_pickup_count = db.query(func.count(Shipment.id)).filter(
        Shipment.status == ShipmentStatus.pending
    ).scalar() or 0

    return {
        "kpis": {
            "total_revenue": round(revenue_this, 2),
            "revenue_change_pct": _pct_change(revenue_this, revenue_last),
            "active_shipments": active_shipments_count,
            "shipments_change_pct": _pct_change(shipments_this, shipments_last),
            "total_customers": total_customers,
            "customers_change_pct": _pct_change(customers_this, customers_last),
            "deliveries_today": deliveries_today,
            "deliveries_change_pct": _pct_change(deliveries_today, deliveries_yesterday),
        },
        "recent_shipments": recent_shipments,
        "pending_actions": {
            "pending_deposits": pending_deposits_count,
            "shipments_on_hold": shipments_on_hold_count,
            "pending_buyforme": pending_buyforme_count,
            "open_tickets": open_tickets_count,
        },
        "quick_stats": {
            "completed_today": deliveries_today,
            "in_transit": in_transit_count,
            "pending_pickup": pending_pickup_count,
            "issues": shipments_on_hold_count,
        },
    }
