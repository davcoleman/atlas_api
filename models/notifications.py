from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
import enum
from database import Base


class NotificationChannel(str, enum.Enum):
    email = "email"
    whatsapp = "whatsapp"
    sms = "sms"
    push = "push"
    in_app = "in_app"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    read = "read"


class NotificationEvent(str, enum.Enum):
    shipment_booked = "shipment_booked"
    shipment_status_update = "shipment_status_update"
    shipment_arriving = "shipment_arriving"
    payment_completed = "payment_completed"
    payment_failed = "payment_failed"
    low_wallet_balance = "low_wallet_balance"
    deposit_approved = "deposit_approved"
    ticket_created = "ticket_created"
    ticket_resolved = "ticket_resolved"
    lead_followup = "lead_followup"
    buyforme_update = "buyforme_update"
    referral_bonus = "referral_bonus"
    loyalty_points = "loyalty_points"
    welcome = "welcome"
    custom = "custom"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    event_type = Column(SAEnum(NotificationEvent), nullable=False)
    channel = Column(SAEnum(NotificationChannel), nullable=False)
    status = Column(SAEnum(NotificationStatus), default=NotificationStatus.pending)

    subject = Column(String(500), nullable=True)
    message = Column(Text, nullable=False)

    recipient_email = Column(String(255), nullable=True)
    recipient_phone = Column(String(50), nullable=True)

    external_id = Column(String(200), nullable=True)  # provider message ID
    error_message = Column(Text, nullable=True)

    reference_type = Column(String(50), nullable=True)  # shipment, ticket, wallet
    reference_id = Column(String(100), nullable=True)

    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
