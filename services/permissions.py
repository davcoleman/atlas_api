"""Granular staff privileges, assigned per-account by a super admin.

Distinct from `UserRole` (which is a coarse account tier). A "staff" role
account is otherwise powerless until specific privileges from this catalog
are granted — see `dependencies.require_permission`.
"""

PERMISSION_CATALOG: dict[str, str] = {
    "shipments": "Manage Shipments",
    "customers": "Manage Customers",
    "wallet": "Wallet & Payments",
    "tickets": "Support Tickets",
    "buyforme": "Buy-for-Me Requests",
    "crm": "CRM & Leads",
    "analytics": "Analytics & Reports",
}


def parse_permissions(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p for p in raw.split(",") if p]


def serialize_permissions(perms: list[str]) -> str:
    valid = [p for p in dict.fromkeys(perms) if p in PERMISSION_CATALOG]
    return ",".join(valid)
