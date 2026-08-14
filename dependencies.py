from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import decode_token, get_user_by_id
from models.users import User, UserRole

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_roles(*roles: UserRole):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {[r.value for r in roles]}",
            )
        return current_user
    return checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.super_admin, UserRole.finance_admin):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user


def require_staff_or_admin(current_user: User = Depends(get_current_user)) -> User:
    allowed = (UserRole.staff, UserRole.finance_admin, UserRole.crm_agent, UserRole.super_admin)
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Staff access required")
    return current_user


def require_permission(perm: str, legacy_full_access_roles: tuple = (
    UserRole.staff, UserRole.finance_admin, UserRole.crm_agent, UserRole.super_admin,
)):
    """Gate an endpoint behind a named privilege from services/permissions.PERMISSION_CATALOG.

    super_admin always passes. An account whose `permissions` column is still NULL
    predates the granular system — if its role is in `legacy_full_access_roles` it
    keeps the old unconditional access that role used to have (pass a narrower tuple
    for endpoints that used to be gated more strictly than require_staff_or_admin,
    e.g. wallet admin routes that previously excluded plain staff/crm_agent).
    Accounts with an explicit `permissions` value (staff created via the Staff tab)
    are always checked against it, regardless of role.
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.super_admin:
            return current_user
        if current_user.role not in (UserRole.staff, UserRole.finance_admin, UserRole.crm_agent):
            raise HTTPException(status_code=403, detail="Staff access required")
        if current_user.permissions is None:
            if current_user.role in legacy_full_access_roles:
                return current_user
            raise HTTPException(status_code=403, detail=f"Missing required privilege: '{perm}'")
        granted = {p for p in current_user.permissions.split(",") if p}
        if perm not in granted:
            raise HTTPException(status_code=403, detail=f"Missing required privilege: '{perm}'")
        return current_user
    return checker
