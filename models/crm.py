from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class LeadStage(str, enum.Enum):
    inquiry = "inquiry"
    quote_sent = "quote_sent"
    payment_pending = "payment_pending"
    confirmed = "confirmed"
    shipped = "shipped"
    closed_won = "closed_won"
    closed_lost = "closed_lost"


class CommunicationChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    email = "email"
    phone = "phone"
    system = "system"
    sms = "sms"


class CommunicationDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class Lead(Base):
    __tablename__ = "crm_leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # null if not yet registered
    assigned_to = Column(Integer, nullable=True, index=True)  # staff user_id

    # Contact info (for unregistered leads)
    contact_name = Column(String(200), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    company_name = Column(String(300), nullable=True)

    stage = Column(SAEnum(LeadStage), default=LeadStage.inquiry)
    source = Column(String(100), nullable=True)  # web, whatsapp, referral, walk-in
    estimated_value = Column(Float, nullable=True)  # USD
    notes = Column(Text, nullable=True)

    last_contacted_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CommunicationLog(Base):
    __tablename__ = "crm_communication_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)
    ticket_id = Column(Integer, nullable=True, index=True)

    channel = Column(SAEnum(CommunicationChannel), nullable=False)
    direction = Column(SAEnum(CommunicationDirection), nullable=False)
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=False)
    sender = Column(String(200), nullable=True)
    recipient = Column(String(200), nullable=True)

    external_id = Column(String(200), nullable=True)  # Twilio/SendGrid message ID
    delivered = Column(Boolean, default=False)
    created_by = Column(Integer, nullable=True)  # staff user_id
    created_at = Column(DateTime, server_default=func.now())
