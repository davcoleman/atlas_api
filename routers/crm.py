from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from database import get_db
from schemas.crm import LeadCreate, LeadUpdate, LeadOut, CommunicationLogCreate, CommunicationLogOut
from dependencies import get_current_user, require_permission
from models.users import User
from models.crm import Lead, CommunicationLog, LeadStage

router = APIRouter(prefix="/crm", tags=["CRM"])


# ── Leads ──────────────────────────────────────────────────────────────────────

@router.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(
    body: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    lead = Lead(**body.model_dump(exclude_none=True))
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/leads", response_model=List[LeadOut])
def list_leads(
    stage: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    q = db.query(Lead)
    if stage:
        q = q.filter(Lead.stage == stage)
    if assigned_to:
        q = q.filter(Lead.assigned_to == assigned_to)
    return q.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int,
    body: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(lead, field, value)
    if body.stage in (LeadStage.closed_won, LeadStage.confirmed):
        lead.converted_at = datetime.utcnow()
    lead.last_contacted_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/leads/{lead_id}", status_code=204)
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()


# ── Communication Logs ─────────────────────────────────────────────────────────

@router.post("/communications", response_model=CommunicationLogOut, status_code=201)
def log_communication(
    body: CommunicationLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    log = CommunicationLog(**body.model_dump(exclude_none=True), created_by=current_user.id)
    db.add(log)
    if body.lead_id:
        lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
        if lead:
            lead.last_contacted_at = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return log


@router.get("/communications", response_model=List[CommunicationLogOut])
def list_communications(
    user_id: Optional[int] = Query(None),
    lead_id: Optional[int] = Query(None),
    ticket_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("crm")),
):
    q = db.query(CommunicationLog)
    if user_id:
        q = q.filter(CommunicationLog.user_id == user_id)
    if lead_id:
        q = q.filter(CommunicationLog.lead_id == lead_id)
    if ticket_id:
        q = q.filter(CommunicationLog.ticket_id == ticket_id)
    return q.order_by(CommunicationLog.created_at.desc()).offset(skip).limit(limit).all()
