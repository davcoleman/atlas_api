from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.tickets import TicketStatus, TicketPriority, TicketCategory


class TicketCreate(BaseModel):
    subject: str
    message: str
    category: TicketCategory = TicketCategory.general
    priority: TicketPriority = TicketPriority.medium
    shipment_id: Optional[int] = None


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[int] = None


class TicketMessageCreate(BaseModel):
    message: str
    attachment_url: Optional[str] = None
    is_internal: bool = False


class TicketMessageOut(BaseModel):
    id: int
    ticket_id: int
    sender_id: int
    sender_type: str
    message: str
    attachment_url: Optional[str] = None
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: int
    ticket_number: str
    user_id: int
    assigned_to: Optional[int] = None
    subject: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    shipment_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    feedback_rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[TicketMessageOut]] = None

    model_config = {"from_attributes": True}


class TicketFeedback(BaseModel):
    rating: int  # 1-5
    comment: Optional[str] = None


class TicketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TicketOut]
