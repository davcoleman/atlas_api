from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from schemas.users import (
    UserOut, UserProfileUpdate, BusinessProfileCreate,
    BusinessProfileOut, ChangePasswordRequest, AdminRoleUpdate,
)
from dependencies import get_current_user, require_super_admin
from models.users import User, BusinessProfile
from services.auth_service import verify_password, hash_password, compute_profile_completeness

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_profile(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.full_name:
        current_user.full_name = body.full_name
    if body.user_type:
        current_user.user_type = body.user_type
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="Account uses social login — no password set")
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@router.get("/me/business-profile", response_model=BusinessProfileOut)
def get_business_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")
    return profile


@router.post("/me/business-profile", response_model=BusinessProfileOut, status_code=201)
def create_business_profile(
    body: BusinessProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Business profile already exists. Use PATCH to update.")
    profile = BusinessProfile(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(profile)
    db.flush()
    profile.profile_completeness = compute_profile_completeness(profile)
    profile.discount_eligible = profile.profile_completeness == 100
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/me/business-profile", response_model=BusinessProfileOut)
def update_business_profile(
    body: BusinessProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    profile.profile_completeness = compute_profile_completeness(profile)
    profile.discount_eligible = profile.profile_completeness == 100
    db.commit()
    db.refresh(profile)
    return profile


# Admin endpoints
@router.get("/", response_model=List[UserOut], dependencies=[Depends(require_super_admin)])
def list_users(
    skip: int = 0,
    limit: int = 50,
    user_type: Optional[str] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if user_type:
        q = q.filter(User.user_type == user_type)
    if role:
        q = q.filter(User.role == role)
    return q.offset(skip).limit(limit).all()


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_super_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/role", response_model=UserOut, dependencies=[Depends(require_super_admin)])
def update_user_role(user_id: int, body: AdminRoleUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/deactivate", dependencies=[Depends(require_super_admin)])
def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"message": "User deactivated"}
