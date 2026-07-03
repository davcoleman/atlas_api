from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.crm import LeadStage, CommunicationChannel, CommunicationDirection


class LeadCreate(BaseModel):
    user_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    estimated_value: Optional[float] = None
    notes: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class LeadUpdate(BaseModel):
    stage: Optional[LeadStage] = None
    assigned_to: Optional[int] = None
    estimated_value: Optional[float] = None
    notes: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class LeadOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    assigned_to: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    company_name: Optional[str] = None
    stage: LeadStage
    source: Optional[str] = None
    estimated_value: Optional[float] = None
    notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommunicationLogCreate(BaseModel):
    user_id: Optional[int] = None
    lead_id: Optional[int] = None
    ticket_id: Optional[int] = None
    channel: CommunicationChannel
    direction: CommunicationDirection
    subject: Optional[str] = None
    body: str
    sender: Optional[str] = None
    recipient: Optional[str] = None


class CommunicationLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    lead_id: Optional[int] = None
    ticket_id: Optional[int] = None
    channel: CommunicationChannel
    direction: CommunicationDirection
    subject: Optional[str] = None
    body: str
    sender: Optional[str] = None
    recipient: Optional[str] = None
    delivered: bool
    created_at: datetime

    model_config = {"from_attributes": True}
