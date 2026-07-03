from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class TicketStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    waiting_customer = "waiting_customer"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TicketCategory(str, enum.Enum):
    shipment = "shipment"
    payment = "payment"
    buyforme = "buyforme"
    account = "account"
    general = "general"
    complaint = "complaint"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(20), unique=True, nullable=False, index=True)  # TKT-YYYY-XXXXXX

    user_id = Column(Integer, nullable=False, index=True)
    assigned_to = Column(Integer, nullable=True, index=True)  # crm_agent user_id

    subject = Column(String(500), nullable=False)
    category = Column(SAEnum(TicketCategory), default=TicketCategory.general)
    priority = Column(SAEnum(TicketPriority), default=TicketPriority.medium)
    status = Column(SAEnum(TicketStatus), default=TicketStatus.pending)

    shipment_id = Column(Integer, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    feedback_sent = Column(Boolean, default=False)
    feedback_rating = Column(Integer, nullable=True)  # 1-5

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, nullable=False, index=True)
    sender_id = Column(Integer, nullable=False)
    sender_type = Column(String(20), nullable=False)  # customer | staff | system

    message = Column(Text, nullable=False)
    attachment_url = Column(String(500), nullable=True)
    is_internal = Column(Boolean, default=False)  # internal staff notes

    created_at = Column(DateTime, server_default=func.now())
