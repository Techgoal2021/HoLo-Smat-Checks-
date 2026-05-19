"""
Payments Router — Paystack webhook handler.
"""
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.user import User
from services import at_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Paystack webhook — fires when a payment is completed.
    Sends booking confirmation and schedules post-stay audit.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "invalid_payload"}

    event = payload.get("event")
    data = payload.get("data", {})

    if event == "charge.success":
        reference = data.get("reference", "")
        # Find user by booking reference
        result = await db.execute(
            select(User).where(User.booking_reference == reference)
        )
        user = result.scalars().first()

        if user:
            user.session_state = "BOOKED"
            await db.commit()

            at_service.send_sms(
                user.phone,
                f"🏨 HoLo: Payment confirmed! Ref: {reference}\n"
                "Your room is secured. Check in using this reference.\n"
                "Tomorrow at 10 AM we'll follow up to verify your stay. 👍"
            )

    return {"status": "ok"}


@router.get("/verify/{reference}")
async def verify_payment_endpoint(reference: str):
    """Manual payment verification endpoint."""
    from services.payment_service import verify_payment
    result = verify_payment(reference)
    return result
