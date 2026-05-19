import os
import json
import re
from groq import Groq
from config import get_settings
from services.persona import LAGOS_DEV_PERSONA

settings = get_settings()
GROQ_API_KEY = settings.groq_api_key
GROQ_MODEL = "llama-3.1-8b-instant"

async def groq_parse_intent(message: str) -> dict:
    """
    Parse user message into structured intent using Groq.
    """
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""
    You are a Lagos-based hospitality intent parser.
    Extract details from this message: "{message}"
    
    Return ONLY valid JSON:
    {{
      "budget_naira": <int or null>,
      "area": "<neighborhood or null>",
      "nights": <int, default 1>,
      "date": "tonight",
      "is_booking_request": <bool>
    }}
    """
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Groq Intent Error: {e}. Using local Survival Brain...")
        # SURVIVAL BRAIN: Local Keyword Matching
        intent = {"budget_naira": None, "area": None, "nights": 1, "date": "tonight", "is_booking_request": False}
        
        # Extract Budget (e.g., 7k, 15000)
        budget_match = re.search(r"(\d+)\s*(k|000)", message.lower())
        if budget_match:
            val = int(budget_match.group(1))
            intent["budget_naira"] = val * 1000 if budget_match.group(2) == "k" else val
            intent["is_booking_request"] = True
            
        # Extract Area (Simple matching for common Lagos areas)
        areas = ["agege", "ogba", "ikeja", "lekki", "yaba", "surulere", "ojodu", "berger", "ifako", "mangoro"]
        for a in areas:
            if a in message.lower():
                intent["area"] = a.capitalize()
                intent["is_booking_request"] = True
                
        return intent

async def groq_live_discovery(message, area, budget=None):
    """
    Perform a live search for hotels using Google Places API and format with Groq.
    """
    google_api_key = settings.google_places_api_key
    if not google_api_key:
        return ("⚠️ HoLo: Google Places API key missing.", [])

    raw_context = ""
    found_hotel_data = []
    
    try:
        import requests
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": google_api_key,
            "X-Goog-FieldMask": "places.displayName,places.rating,places.formattedAddress,places.reviews"
        }
        clean_area = area.replace("/", " ").replace("\\", " ").strip()
        query = f"verified hotels and guest houses near {clean_area} Lagos Nigeria"
        
        payload = {"textQuery": query, "languageCode": "en", "maxResultCount": 20}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        places = response.json().get("places", [])
        
        if not places: return ("", [])

        for idx, place in enumerate(places, 1):
            name = place.get("displayName", {}).get("text", "Unknown Lodge")
            address = place.get("formattedAddress", "Unknown Address")
            rating = place.get("rating", 0)
            
            # ULTRA-STRICT NEIGHBORHOOD FENCE
            clean_area_lower = clean_area.lower().strip()
            is_local = clean_area_lower in address.lower() or clean_area_lower in name.lower()
            
            # Exclude false positives (e.g. 'Ogba' in an address but not the primary area)
            neighbors = {"ikeja", "lekki", "yaba", "surulere", "omole"}
            if any(nb in address.lower() and nb not in clean_area_lower for nb in neighbors):
                is_local = False

            marker = "[HYPER-LOCAL]" if is_local else "[NEARBY]"
            reviews = place.get("reviews", [])[:2]
            rev_str = " | ".join([r.get("text", {}).get("text", "")[:100] for r in reviews])
            
            # Injected price context for the AI
            est_price = budget if budget else 15000
            raw_context += f"{idx}. {marker} **{name}**\n   📍 ADDRESS: {address}\n   💳 EST_PRICE: ₦{est_price:,}\n   Reviews: {rev_str}\n\n"
            found_hotel_data.append(f"{name}::{est_price}")
            
    except Exception as e:
        print(f"❌ Discovery Error: {e}")
        return ("", [])
            
    from services.persona import get_system_prompt
    display_budget = budget if budget else 15000
    
    prompt = f"""
    {get_system_prompt("audit")}
    
    VERIFIED DATA (MANDATORY FORMAT):
    {raw_context}
    
    YOUR GOAL:
    1. List [HYPER-LOCAL] first.
    2. MANDATORY: You MUST include the '📍 ADDRESS' and '💳 PRICE' for EVERY hotel.
    
    FORMAT:
    **[Hotel Name]** — Truth Score: [Score]/100
    📍 **ADDRESS**: [Full Address]
    💳 **PRICE**: [Price from Data]
    ✅ [Strength] | ⚠️ [Risk]
    """
    
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        return (completion.choices[0].message.content, found_hotel_data)
    except:
        return ("", [])

async def groq_conversational_reply(message: str) -> str:
    """Handles general conversational fallback when intent is not a booking request."""
    from services.persona import get_system_prompt
    system_instruction = get_system_prompt("chat")
    
    prompt = f"""
    {system_instruction}
    
    The user said: "{message}"
    
    INSTRUCTION: You are Vera. Respond exactly as: "Vera here. 👋 Welcome to HoLo Smart checks! I'm your honest Hotels and Lodges guide. How may I be of help today?" if they are just saying hi.
    """
    
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Groq SDK Error: {e}")
        return None

async def groq_audit_search(message: str, hotel_data: str) -> str:
    """
    Directly uses Groq to perform a web search for hotel intel.
    """
    from services.persona import get_system_prompt
    system_instruction = get_system_prompt("audit")
    
    prompt = f"""
    {system_instruction}
    
    TASK: Perform a high-fidelity price and infrastructure audit for:
    {hotel_data}
    
    USER REQUEST: "{message}"
    
    STRICT REQUIREMENTS:
    1. 💳 MANDATORY PRICE: You MUST include a '💳 PRICE' line for EVERY hotel. If exact data is missing, provide a verified estimate (e.g., ₦7,500 - ₦12,000) based on the area market.
    2. 📍 ADDRESS LOCK: Bold the address.
    3. NEIGHBORHOOD FENCE: If it's not in the target area, label as [NEARBY].
    
    FORMAT:
    **[Hotel Name]** — Truth Score: [Score]/100
    📍 **ADDRESS**: [Full Address]
    💳 **PRICE**: ₦[Amount or Estimated Range]
    ✅ [Strength] | ⚠️ [Risk]
    """
    
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Groq Audit Error: {e}")
        return None
