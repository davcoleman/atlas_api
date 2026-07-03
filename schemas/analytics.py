from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class RevenuePoint(BaseModel):
    period: str
    revenue: float
    shipment_count: int


class RouteStats(BaseModel):
    route: str
    shipment_count: int
    total_revenue: float
    avg_value: float


class WalletActivityPoint(BaseModel):
    period: str
    deposits: float
    deductions: float
    refunds: float
    net: float


class CustomerRetentionStats(BaseModel):
    total_customers: int
    active_customers: int
    new_this_month: int
    repeat_customers: int
    retention_rate: float


class StaffPerformance(BaseModel):
    staff_id: int
    staff_name: str
    tickets_resolved: int
    avg_resolution_hours: float
    shipments_processed: int


class DashboardKPIs(BaseModel):
    total_revenue: float
    revenue_change_pct: float
    total_shipments: int
    shipments_change_pct: float
    active_customers: int
    customers_change_pct: float
    wallet_balance_total: float
    pending_deposits: float
    open_tickets: int
    pending_buyforme: int


class AnalyticsReport(BaseModel):
    kpis: DashboardKPIs
    revenue_trend: List[RevenuePoint]
    top_routes: List[RouteStats]
    wallet_activity: List[WalletActivityPoint]
    customer_retention: CustomerRetentionStats
    staff_performance: List[StaffPerformance]
