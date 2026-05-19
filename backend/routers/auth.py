"""
HoLo Auth Router — Phone-based OTP login.
No passwords. Just phone + 4-digit code via Africa's Talking.
"""
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.database import get_db
from models.user import User
from services import at_service

router = APIRouter(prefix="/auth", tags=["auth"])


class OTPRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str

class ProfileUpdate(BaseModel):
    phone: str
    name: str


@router.post("/request-otp")
async def request_otp(body: OTPRequest, db: AsyncSession = Depends(get_db)):
    """Send a 4-digit OTP to the user's phone via SMS."""
    phone = body.phone.strip()
    if not phone:
        return {"success": False, "error": "Phone number required"}

    # Find or create user
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalars().first()
    is_new = user is None

    if not user:
        user = User(phone=phone)
        db.add(user)

    # Generate 4-digit OTP
    otp = str(random.randint(1000, 9999))
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    await db.commit()

    # Send via Africa's Talking SMS
    message = f"🔐 HoLo Code: {otp}\nValid for 5 minutes. Don't share this code."
    sms_result = at_service.send_sms(phone, message)

    print(f"🔐 OTP for {phone}: {otp} (SMS: {sms_result['success']})")

    return {
        "success": True,
        "is_new_user": is_new,
        "message": "OTP sent to your phone"
    }


@router.post("/verify-otp")
async def verify_otp(body: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify the OTP and log the user in."""
    phone = body.phone.strip()
    otp = body.otp.strip()

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalars().first()

    if not user or not user.otp:
        return {"success": False, "error": "No OTP requested for this number"}

    if user.otp_expiry and datetime.utcnow() > user.otp_expiry:
        return {"success": False, "error": "OTP expired. Request a new one."}

    if user.otp != otp:
        return {"success": False, "error": "Wrong code. Try again."}

    # Clear OTP after use
    user.otp = None
    user.otp_expiry = None
    await db.commit()

    print(f"✅ {phone} logged in successfully")

    return {
        "success": True,
        "user": {
            "phone": user.phone,
            "name": user.name,
            "is_new": user.name is None,
        }
    }


@router.post("/save-profile")
async def save_profile(body: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    """Save the user's name after first login."""
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalars().first()

    if not user:
        return {"success": False, "error": "User not found"}

    user.name = body.name.strip()
    await db.commit()

    return {"success": True, "name": user.name}
