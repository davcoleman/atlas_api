import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from schemas.tickets import (
    TicketCreate, TicketUpdate, TicketOut, TicketMessageCreate,
    TicketMessageOut, TicketFeedback, TicketListResponse,
)
from dependencies import get_current_user, require_staff_or_admin
from models.users import User, UserRole
from models.tickets import SupportTicket, TicketMessage, TicketStatus
from services.notification_service import notify_ticket_resolved

router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


def _gen_ticket_number() -> str:
    year = datetime.utcnow().strftime("%Y")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"TKT-{year}-{suffix}"


@router.post("/", response_model=TicketOut, status_code=201)
def create_ticket(
    body: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = SupportTicket(
        ticket_number=_gen_ticket_number(),
        user_id=current_user.id,
        subject=body.subject,
        category=body.category,
        priority=body.priority,
        shipment_id=body.shipment_id,
    )
    db.add(ticket)
    db.flush()

    first_message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        sender_type="customer",
        message=body.message,
    )
    db.add(first_message)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/", response_model=TicketListResponse)
def list_tickets(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SupportTicket)
    if current_user.role == UserRole.customer:
        q = q.filter(SupportTicket.user_id == current_user.id)
    if status:
        q = q.filter(SupportTicket.status == status)
    if category:
        q = q.filter(SupportTicket.category == category)

    total = q.count()
    items = q.order_by(SupportTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == UserRole.customer and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = db.query(TicketMessage).filter(
        TicketMessage.ticket_id == ticket_id,
        TicketMessage.is_internal == False,
    ).order_by(TicketMessage.created_at.asc()).all()

    ticket_dict = ticket.__dict__.copy()
    ticket_dict["messages"] = messages
    return ticket_dict


@router.post("/{ticket_id}/messages", response_model=TicketMessageOut, status_code=201)
def add_message(
    ticket_id: int,
    body: TicketMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == UserRole.customer and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sender_type = "customer" if current_user.role == UserRole.customer else "staff"
    msg = TicketMessage(
        ticket_id=ticket_id,
        sender_id=current_user.id,
        sender_type=sender_type,
        message=body.message,
        attachment_url=body.attachment_url,
        is_internal=body.is_internal,
    )
    db.add(msg)

    if ticket.status == TicketStatus.waiting_customer and sender_type == "customer":
        ticket.status = TicketStatus.in_progress
    elif ticket.status == TicketStatus.in_progress and sender_type == "staff":
        ticket.status = TicketStatus.waiting_customer

    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ticket, field, value)
    if body.status == TicketStatus.resolved:
        ticket.resolved_at = datetime.utcnow()
        notify_ticket_resolved(db, ticket.user_id, ticket.ticket_number)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/feedback")
def submit_feedback(
    ticket_id: int,
    body: TicketFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1–5")
    ticket.feedback_rating = body.rating
    db.commit()
    return {"message": "Thank you for your feedback!"}
