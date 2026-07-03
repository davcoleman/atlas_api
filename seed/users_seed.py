"""Seed the default super-admin account."""
from sqlalchemy.orm import Session
from models.users import User, UserRole, UserType
from services.auth_service import hash_password, generate_referral_code


ADMIN_EMAIL = "donking@gmail.com"
ADMIN_PASSWORD = "admin@123"


def seed_admin(db: Session) -> None:
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing:
        if existing.role != UserRole.super_admin:
            existing.role = UserRole.super_admin
            db.commit()
        return

    admin = User(
        full_name="System Administrator",
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        user_type=UserType.personal,
        role=UserRole.super_admin,
        is_active=True,
        is_verified=True,
        referral_code=generate_referral_code("Admin"),
    )
    db.add(admin)
    db.commit()
    print(f"[seed] Admin user created: {ADMIN_EMAIL}")
