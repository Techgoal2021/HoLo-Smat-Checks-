"""
Africa's Talking service — SMS, WhatsApp, and Airtime rewards.
"""
import requests
import africastalking
from config import get_settings

settings = get_settings()

# Initialize AT SDK
africastalking.initialize(settings.at_username, settings.at_api_key)
sms_service = africastalking.SMS
airtime_service = africastalking.Airtime

# WhatsApp Endpoints
WA_ENDPOINT = "https://chat.africastalking.com/whatsapp/message/send"
WA_SANDBOX_ENDPOINT = "https://chat.sandbox.africastalking.com/whatsapp/message/send"

def send_sms(phone: str, message: str) -> dict:
    """Send an SMS via Africa's Talking."""
    try:
        clean_phone = phone if phone.startswith("+") else f"+{phone}"
        response = sms_service.send(message, [clean_phone], sender_id=settings.at_shortcode)
        print(f"📱 SMS sent to {clean_phone}: {response}")
        return {"success": True, "response": response}
    except Exception as e:
        print(f"❌ SMS send error to {phone}: {e}")
        return {"success": False, "error": str(e)}

def send_whatsapp(phone: str, message: str) -> dict:
    """Send a WhatsApp message via Africa's Talking official API."""
    try:
        # Strip 'whatsapp:' prefix if present
        clean_phone = phone.replace("whatsapp:", "")
        if not clean_phone.startswith("+"):
            clean_phone = f"+{clean_phone}"
            
        payload = {
            "username": settings.at_username,
            "waNumber": settings.at_wa_number, 
            "phoneNumber": clean_phone,
            "body": {
                "message": message
            }
        }
        
        headers = {
            "apikey": settings.at_api_key,
            "content-type": "application/json"
        }
        
        # Use sandbox endpoint if username is sandbox
        endpoint = WA_SANDBOX_ENDPOINT if settings.at_username == "sandbox" else WA_ENDPOINT
        
        response = requests.post(endpoint, json=payload, headers=headers)
        data = response.json()
        print(f"💬 WhatsApp sent to {clean_phone}: {data}")
        return {"success": True, "response": data}
    except Exception as e:
        print(f"❌ WhatsApp send error to {phone}: {e}")
        return {"success": False, "error": str(e)}

def send_airtime(phone: str, amount_ngn: int = 100) -> dict:
    """Send ₦100 airtime reward via Africa's Talking."""
    try:
        clean_phone = phone.replace("whatsapp:", "")
        if not clean_phone.startswith("+"):
            clean_phone = f"+{clean_phone}"
            
        recipients = [
            {
                "phoneNumber": clean_phone,
                "amount": f"NGN {amount_ngn}",
                "currencyCode": "NGN",
            }
        ]
        response = airtime_service.send(recipients=recipients)
        print(f"🎁 Airtime sent to {clean_phone}: {response}")
        return {"success": True, "response": response}
    except Exception as e:
        print(f"❌ Airtime send error to {phone}: {e}")
        return {"success": False, "error": str(e)}
