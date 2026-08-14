from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./atlas_freight.db"
    secret_key: str = "change-me-in-production-use-long-random-string"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    google_client_id: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    sendgrid_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "usd"
    frontend_url: str = "http://localhost:5173"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@atlasfreight.com"
    smtp_from_name: str = "Atlas Freight Services"
    didit_api_key: str = ""
    didit_webhook_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"  # silently skip unknown env vars (e.g. ATLAS_FREIGHT_DIDIT_API_SECRET_KEY)


settings = Settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import catalog, engines, quotes  # noqa: F401
    from models import users, wallet, shipments, crm, tickets, notifications, buyforme, loyalty  # noqa: F401  # DiditWebhookEvent is inside users
    Base.metadata.create_all(bind=engine)


def migrate_db():
    """Add columns introduced after initial schema creation (SQLite-safe)."""
    from sqlalchemy import text
    new_cols = [
        ("users", "terms_accepted_at", "DATETIME"),
        ("users", "terms_acceptance_signature", "VARCHAR(200)"),
        ("users", "kyc_status", "VARCHAR(50)"),
        ("users", "kyc_session_id", "VARCHAR(100)"),
        ("users", "kyc_verified_at", "DATETIME"),
        ("shipments", "origin_lat", "FLOAT"),
        ("shipments", "origin_lng", "FLOAT"),
        ("shipments", "destination_lat", "FLOAT"),
        ("shipments", "destination_lng", "FLOAT"),
        ("shipments", "current_lat", "FLOAT"),
        ("shipments", "current_lng", "FLOAT"),
        ("shipments", "current_location_label", "VARCHAR(200)"),
        ("shipments", "progress_percent", "INTEGER DEFAULT 0"),
        ("users", "permissions", "TEXT"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in new_cols:
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in result.fetchall()}
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        conn.commit()

        # Backfill map pins for shipments created before live tracking existed
        conn.execute(text("""
            UPDATE shipments SET origin_lat = 40.6413, origin_lng = -73.7781,
                current_lat = COALESCE(current_lat, 40.6413), current_lng = COALESCE(current_lng, -73.7781)
            WHERE origin_lat IS NULL AND (origin_country IS NULL OR lower(origin_country) = 'usa')
        """))
        conn.execute(text("""
            UPDATE shipments SET destination_lat = 5.6052, destination_lng = -0.1719
            WHERE destination_lat IS NULL AND (destination_country IS NULL OR lower(destination_country) = 'ghana')
        """))
        conn.execute(text("UPDATE shipments SET progress_percent = 0 WHERE progress_percent IS NULL"))
        conn.commit()
