from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import settings, create_tables, migrate_db
from routers import catalog, quotes, rates
from routers import auth, users, wallet, shipments, crm, tickets, notifications, analytics, buyforme, loyalty, admin, kyc

app = FastAPI(
    title="Atlas Freight Logistics API",
    description="Full-featured freight logistics platform — Auth, Wallet, Shipments, CRM, Buy-for-Me, Analytics.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_env_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
_dev_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
]
_allowed_origins = list(set(_env_origins + _dev_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core (existing)
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(quotes.router,  prefix="/api/v1")
app.include_router(rates.router,   prefix="/api/v1")

# Auth & Users
app.include_router(auth.router,    prefix="/api/v1")
app.include_router(users.router,   prefix="/api/v1")

# Wallet & Payments
app.include_router(wallet.router,  prefix="/api/v1")

# Shipments
app.include_router(shipments.router, prefix="/api/v1")

# CRM
app.include_router(crm.router,     prefix="/api/v1")

# Support Tickets
app.include_router(tickets.router, prefix="/api/v1")

# Notifications
app.include_router(notifications.router, prefix="/api/v1")

# Analytics & Reporting
app.include_router(analytics.router, prefix="/api/v1")

# Buy-for-Me
app.include_router(buyforme.router, prefix="/api/v1")

# Loyalty & Referrals
app.include_router(loyalty.router, prefix="/api/v1")

# Admin
app.include_router(admin.router,   prefix="/api/v1")

# KYC (Didit)
app.include_router(kyc.router,     prefix="/api/v1")


@app.on_event("startup")
def startup():
    create_tables()
    migrate_db()
    from database import SessionLocal
    from seed.catalog_seed import seed_catalog
    from seed.engines_seed import seed_engines
    from seed.users_seed import seed_admin
    db = SessionLocal()
    try:
        seed_engines(db)
        seed_catalog(db)
        seed_admin(db)
    finally:
        db.close()


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "Atlas Freight Logistics API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
