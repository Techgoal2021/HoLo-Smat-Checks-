"""
Paystack payment service — create and verify payment links.
"""
import requests
import uuid
from config import get_settings

settings = get_settings()

PAYSTACK_BASE = "https://api.paystack.co"


def _headers():
    return {
        "Authorization": f"Bearer {settings.paystack_secret_key}",
        "Content-Type": "application/json",
    }


def create_payment_link(email: str, amount_naira: int, hotel_name: str) -> dict:
    """
    Initialize a Paystack transaction and return the payment URL.
    amount_naira is converted to kobo (x100) for Paystack.
    """
    reference = f"HOLO-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "email": email,
        "amount": amount_naira * 100,  # Convert to kobo
        "reference": reference,
        "callback_url": "https://holo.app/payment/success",
        "metadata": {
            "hotel_name": hotel_name,
            "custom_fields": [
                {
                    "display_name": "Hotel",
                    "variable_name": "hotel_name",
                    "value": hotel_name,
                }
            ],
        },
    }

    try:
        response = requests.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json=payload,
            headers=_headers(),
            timeout=10,
        )
        data = response.json()
        if data.get("status"):
            return {
                "success": True,
                "authorization_url": data["data"]["authorization_url"],
                "reference": reference,
            }
        return {"success": False, "error": data.get("message", "Unknown error")}
    except Exception as e:
        print(f"❌ Paystack error: {e}")
        return {"success": False, "error": str(e)}


def verify_payment(reference: str) -> dict:
    """Verify a Paystack transaction by reference."""
    try:
        response = requests.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers=_headers(),
            timeout=10,
        )
        data = response.json()
        if data.get("status") and data["data"]["status"] == "success":
            return {"success": True, "data": data["data"]}
        return {"success": False, "status": data.get("data", {}).get("status", "unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}
