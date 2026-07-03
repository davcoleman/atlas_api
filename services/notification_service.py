from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from models.notifications import Notification, NotificationChannel, NotificationStatus, NotificationEvent
from models.users import User


TEMPLATES: dict[str, dict] = {
    NotificationEvent.shipment_booked: {
        "subject": "Shipment Confirmed — {tracking_number}",
        "message": "Your shipment {tracking_number} for '{item_name}' has been confirmed. We will notify you as it progresses.",
    },
    NotificationEvent.shipment_status_update: {
        "subject": "Shipment Update — {tracking_number}",
        "message": "Your shipment {tracking_number} status has changed to: {status}.",
    },
    NotificationEvent.shipment_arriving: {
        "subject": "Your Cargo Arrives Tomorrow — {tracking_number}",
        "message": "Your cargo ({tracking_number}) is arriving tomorrow. Please ensure you are available for pickup or delivery.",
    },
    NotificationEvent.payment_completed: {
        "subject": "Payment Received",
        "message": "Your payment of {currency} {amount} has been received and your wallet updated.",
    },
    NotificationEvent.payment_failed: {
        "subject": "Payment Failed",
        "message": "Your payment of {currency} {amount} could not be processed. Please try again.",
    },
    NotificationEvent.low_wallet_balance: {
        "subject": "Low Wallet Balance",
        "message": "Your wallet balance is {currency} {balance}. Top up now to avoid delays in your shipments.",
    },
    NotificationEvent.deposit_approved: {
        "subject": "Deposit Approved",
        "message": "Your wallet deposit of {currency} {amount} has been approved. Your new balance is {currency} {balance}.",
    },
    NotificationEvent.ticket_created: {
        "subject": "Support Ticket Created — {ticket_number}",
        "message": "Your support ticket {ticket_number} has been created. Our team will respond shortly.",
    },
    NotificationEvent.ticket_resolved: {
        "subject": "Ticket Resolved — {ticket_number}",
        "message": "Your support ticket {ticket_number} has been resolved. Please share your feedback.",
    },
    NotificationEvent.lead_followup: {
        "subject": "Following Up on Your Inquiry",
        "message": "Hello {name}, we wanted to follow up on your recent shipping inquiry. Our team is ready to assist you.",
    },
    NotificationEvent.buyforme_update: {
        "subject": "Buy-for-Me Update — {request_number}",
        "message": "Your purchase request {request_number} for '{product_name}' has been updated to: {status}.",
    },
    NotificationEvent.referral_bonus: {
        "subject": "Referral Bonus Earned!",
        "message": "You earned a {currency} {amount} bonus for referring a new customer. Keep sharing your referral code!",
    },
    NotificationEvent.loyalty_points: {
        "subject": "Loyalty Points Earned",
        "message": "You earned {points} loyalty points. Your new total is {total} points.",
    },
    NotificationEvent.welcome: {
        "subject": "Welcome to Atlas Freight!",
        "message": "Welcome aboard, {name}! We're excited to have you. Start shipping today and enjoy our competitive rates.",
    },
}


def _render(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except KeyError:
        return template


def create_notification(
    db: Session,
    user_id: int,
    event_type: NotificationEvent,
    channel: NotificationChannel,
    context: Optional[dict] = None,
    custom_message: Optional[str] = None,
    custom_subject: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
) -> Notification:
    ctx = context or {}
    template = TEMPLATES.get(event_type, {"subject": "Atlas Freight", "message": custom_message or ""})

    subject = custom_subject or _render(template["subject"], ctx)
    message = custom_message or _render(template["message"], ctx)

    user = db.query(User).filter(User.id == user_id).first()

    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        channel=channel,
        status=NotificationStatus.pending,
        subject=subject,
        message=message,
        recipient_email=user.email if user else None,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(notification)
    db.flush()

    # Attempt delivery (mock — in production connect Twilio/SendGrid)
    _dispatch(notification)
    notification.status = NotificationStatus.sent
    notification.sent_at = datetime.utcnow()

    db.commit()
    db.refresh(notification)
    return notification


def _dispatch(notification: Notification):
    """Mock dispatcher — replace with Twilio/SendGrid calls in production."""
    pass


def notify_shipment_booked(db: Session, user_id: int, tracking_number: str, item_name: str):
    ctx = {"tracking_number": tracking_number, "item_name": item_name}
    for channel in [NotificationChannel.email, NotificationChannel.whatsapp]:
        create_notification(db, user_id, NotificationEvent.shipment_booked, channel, ctx,
                            reference_type="shipment", reference_id=tracking_number)


def notify_shipment_status(db: Session, user_id: int, tracking_number: str, status: str):
    ctx = {"tracking_number": tracking_number, "status": status}
    create_notification(db, user_id, NotificationEvent.shipment_status_update,
                        NotificationChannel.email, ctx, reference_type="shipment", reference_id=tracking_number)


def notify_payment_completed(db: Session, user_id: int, amount: float, currency: str = "GHS"):
    ctx = {"amount": f"{amount:.2f}", "currency": currency}
    for channel in [NotificationChannel.email, NotificationChannel.whatsapp]:
        create_notification(db, user_id, NotificationEvent.payment_completed, channel, ctx,
                            reference_type="wallet")


def notify_deposit_approved(db: Session, user_id: int, amount: float, balance: float, currency: str = "GHS"):
    ctx = {"amount": f"{amount:.2f}", "balance": f"{balance:.2f}", "currency": currency}
    for channel in [NotificationChannel.email, NotificationChannel.whatsapp]:
        create_notification(db, user_id, NotificationEvent.deposit_approved, channel, ctx,
                            reference_type="wallet")


def notify_ticket_resolved(db: Session, user_id: int, ticket_number: str):
    ctx = {"ticket_number": ticket_number}
    create_notification(db, user_id, NotificationEvent.ticket_resolved, NotificationChannel.email,
                        ctx, reference_type="ticket", reference_id=ticket_number)


def notify_buyforme_update(db: Session, user_id: int, request_number: str, product_name: str, status: str):
    ctx = {"request_number": request_number, "product_name": product_name, "status": status}
    create_notification(db, user_id, NotificationEvent.buyforme_update, NotificationChannel.email,
                        ctx, reference_type="buyforme", reference_id=request_number)


def notify_welcome(db: Session, user_id: int, name: str):
    ctx = {"name": name}
    create_notification(db, user_id, NotificationEvent.welcome, NotificationChannel.email, ctx)


def notify_referral_bonus(db: Session, user_id: int, amount: float, currency: str = "GHS"):
    ctx = {"amount": f"{amount:.2f}", "currency": currency}
    create_notification(db, user_id, NotificationEvent.referral_bonus, NotificationChannel.email, ctx)
