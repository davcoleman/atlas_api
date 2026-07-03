from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.notifications import NotificationChannel, NotificationStatus, NotificationEvent


class NotificationOut(BaseModel):
    id: int
    user_id: int
    event_type: NotificationEvent
    channel: NotificationChannel
    status: NotificationStatus
    subject: Optional[str] = None
    message: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    total: int
    unread: int
    items: List[NotificationOut]


class SendNotificationRequest(BaseModel):
    user_id: int
    event_type: NotificationEvent
    channel: NotificationChannel
    subject: Optional[str] = None
    message: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
