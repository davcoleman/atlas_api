from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from schemas.notifications import NotificationOut, NotificationListResponse, SendNotificationRequest
from dependencies import get_current_user, require_staff_or_admin
from models.users import User
from models.notifications import Notification, NotificationStatus
from services.notification_service import create_notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=NotificationListResponse)
def get_notifications(
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.read_at == None)
    total = q.count()
    unread = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_at == None,
    ).count()
    items = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "unread": unread, "items": items}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if notif:
        notif.read_at = datetime.utcnow()
        notif.status = NotificationStatus.read
        db.commit()
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_at == None,
    ).update({"read_at": datetime.utcnow(), "status": NotificationStatus.read})
    db.commit()
    return {"message": "All notifications marked as read"}


@router.post("/send", response_model=NotificationOut)
def send_notification(
    body: SendNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    notif = create_notification(
        db,
        body.user_id,
        body.event_type,
        body.channel,
        custom_message=body.message,
        custom_subject=body.subject,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
    )
    return notif
