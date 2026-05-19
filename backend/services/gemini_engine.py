"""
Gemini AI Engine — The Brain of HoLo.
Handles NLU (parsing user requests) and hotel scoring with smart fallback.
"""
import json
import re
from google import genai
from google.genai import types
from config import get_settings
import json
import re

# Tool Definitions for Agentic Vera
def search_local_db(area: str) -> str:
    """Check the HoLo ground-truth database for verified hotels in an area."""
    # This will be called by Gemini autonomously
    return "QUERY_DB_FOR_" + area

def verify_power_status(hotel_name: str) -> str:
    """Deep-scan for recent mentions of power issues or generator status for a specific hotel."""
    return "SEARCH_POWER_FOR_" + hotel_name

settings = get_settings()

client = None

def get_client():
    global client
    if not client:
        # Fallback to a dummy key so the app boots even if ENV is missing on Vercel
        api_key = settings.gemini_api_key or "dummy_key_to_prevent_startup_crash"
        client = genai.Client(api_key=api_key)
    return client

MODEL = "gemini-2.0-flash"

def _call_gemini(prompt: str, retries: int = 1) -> str:
    """Make a Gemini API call with retry logic and absolute fallback."""
    import time
    for i in range(retries + 1):
        try:
            c = get_client()
            response = c.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if "429" in str(e):
                print(f"📡 [HoLo] Gemini is resting (Quota Limit).")
                if i < retries:
                    time.sleep(2)
                    continue
            else:
                print(f"❌ Gemini Error: {e}")
            return ""

async def gemini_parse_intent(message: str) -> dict:
    """Parse user message into structured intent using Gemini 2.0."""
    prompt = f"""
    You are a Lagos-based hospitality intent parser for HoLo.
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
        c = get_client()
        response = await c.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Gemini Intent Fallback: {e}")
        from services.groq_engine import groq_parse_intent
        return await groq_parse_intent(message)


def parse_user_request(message: str) -> dict:
    """
    Extract booking intent from a natural language WhatsApp/SMS message.
    Returns structured dict with: budget, area, date, nights.
    """
    prompt = f"""
You are HoLo, an AI assistant for a hotel booking platform in Lagos, Nigeria.

Extract booking details from this message: "{message}"

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "budget_naira": <integer or null>,
  "area": "<any neighbourhood or area in Lagos Nigeria mentioned by the user, e.g. Yaba, Lekki, Victoria Island, Ikeja, Surulere, Ikoyi, Ajah, Gbagada, Maryland, Magodo, Festac, Oshodi, Apapa, Ikorodu, Mushin, Agege, Ogba, Ojodu, Berger, Sangotedo, Chevron, Banana Island, or null if not mentioned>",
  "nights": <integer, default 1>,
  "date": "<tonight/tomorrow/specific date or 'tonight'>",
  "is_booking_request": <true or false>
}}
"""
    raw = _call_gemini(prompt)
    
    if not raw:
        # 🚀 LIKELY RATE LIMITED - TRIGGERING SMART FALLBACK
        print("🛠️  [HoLo CORE]: Gemini is rate-limited. Triggering SMART FALLBACK...", flush=True)
        return _fallback_parse(message)

    try:
        clean = re.sub(r"```json|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        print("🛠️  [HoLo CORE]: AI returned junk. Triggering FALLBACK...", flush=True)
        return _fallback_parse(message)


def _fallback_parse(message: str) -> dict:
    """Simple regex/keyword fallback if Gemini is rate-limited."""
    msg = message.lower()
    intent = {
        "budget_naira": None,
        "area": None,
        "nights": 1,
        "date": "tonight",
        "is_booking_request": True
    }
    
    # Extract Budget (e.g., 15k, 20000)
    budget_match = re.search(r"(\d+)\s*k", msg)
    if budget_match:
        intent["budget_naira"] = int(budget_match.group(1)) * 1000
    else:
        full_num = re.search(r"(\d{4,6})", msg)
        if full_num:
            intent["budget_naira"] = int(full_num.group(1))

    # Extract Area — full Lagos geography
    lagos_areas = [
        "victoria island", "banana island", "lekki phase 1", "lekki", "ikoyi",
        "ajah", "sangotedo", "chevron", "ikeja gra", "ikeja", "yaba", "surulere",
        "gbagada", "maryland", "magodo", "festac", "oshodi", "apapa", "ikorodu",
        "mushin", "agege", "ogba", "ojodu", "berger", "isale eko", "lagos island",
        "epe", "badagry", "okokomaiko", "amuwo", "alimosho"
    ]
    for area in lagos_areas:
        if area in msg:
            intent["area"] = area.title()
            break
            
    if not intent["area"]:
        # Dynamic fallback: look for words after "in", "at", or "around"
        area_match = re.search(r"\b(?:in|at|around)\s+([a-z]+(?:-[a-z]+)?)\b", msg)
        if area_match and area_match.group(1) not in ["a", "the", "an", "lagos", "my", "our", "this"]:
            intent["area"] = area_match.group(1).title()

    return intent


def generate_hotel_recommendations(hotels: list, user_prefs: dict) -> str:
    """Generate conversational recommendations with hard fallback."""
    budget = user_prefs.get("budget_naira")
    area = user_prefs.get("area", "Lagos")

    hotel_data = "\n".join([
        f"- {h['name']} ({h['area']}): ₦{h['price_naira']:,}/night | "
        f"Truth Score: {h['truth_score']}/100"
        for h in hotels
    ])

    prompt = (
        f"You are the HoLo Truth Engine. Provide a brutally honest, objective summary of these hotels "
        f"in {area} (Budget: {budget}):\n{hotel_data}\n\n"
        "Focus on Power and Wi-Fi facts. Do not use sales language. Stop after the data is presented."
    )
    
    # Try AI first
    raw = _call_gemini(prompt)
    
    # HARD FALLBACK (Manual formatting if AI fails)
    if not raw:
        print(f"🛠️ [HoLo CORE]: AI Offline. Generating Manual Fallback.")
        msg = f"🏨 HoLo (Offline Mode): I found {len(hotels)} verified options in {area}:\n\n"
        for i, h in enumerate(hotels[:3], 1):
            msg += f"{i}. {h['name']}: ₦{h['price_naira']:,} (Score: {h['truth_score']}/100)\n"
        msg += "\nReply with the hotel NUMBER (1, 2, or 3) to book."
        return msg

    return raw


def generate_booking_confirmation(hotel_name: str, reference: str, payment_url: str) -> str:
    return (
        f"✅ HoLo: You're all set!\n"
        f"Lodge: {hotel_name}\n"
        f"Ref: {reference}\n"
        f"Pay here: {payment_url}\n"
        f"Show this ref at check-in. Stay verified! 🏨"
    )


def analyze_hotel_reputation(hotel_name: str, area: str) -> dict:
    """
    Uses Google Search Grounding to find real-world sentiment for a hotel.
    Searches for both recent and historical complaints/praise regarding power & wifi.
    """
    import time
    prompt = f"""
    Search for real guest reviews, news, or social media complaints about "{hotel_name}" in {area}, Lagos.
    Specifically look for mentions of:
    1. Power consistency (Generators, inverters, load shedding, "Up NEPA" frequency).
    2. Wi-Fi speed and stability (Is it actually usable for Zoom/Teams?).
    3. "Laba Laba" (Lies): Check if their advertised photos/amenities match recent guest photos.
    4. Safety and Noise (Clubs nearby, security guard presence).
    
    Return a JSON response with:
    {{
      "power_score": <0-100>,
      "wifi_score": <0-100>,
      "security_score": <0-100>,
      "staff_score": <0-100>,
      "sentiment_summary": "<short summary including specific complaints/praise found>",
      "verdict": "<one word: Trustworthy, Risky, or Unverified>"
    }}
    """
    
    for i in range(2): 
        try:
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
            c = get_client()
            response = c.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config
            )
            
            raw = response.text
            clean = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(clean)
            
            # Weighted Truth Score Calculation
            data["truth_score"] = int(
                (data["power_score"] * 0.3) + 
                (data["wifi_score"] * 0.3) + 
                (data["security_score"] * 0.2) + 
                (data["staff_score"] * 0.2) +
                (10 if data["verdict"] == "Trustworthy" else 0)
            )
            return data
            
        except Exception as e:
            if "429" in str(e) and i < 1:
                time.sleep(10)
                continue
            return {
                "power_score": 60,
                "wifi_score": 60,
                "security_score": 60,
                "staff_score": 60,
                "sentiment_summary": "Live audit failed due to signal issues. Using baseline truth.",
                "verdict": "Unverified",
                "truth_score": 60
            }


def live_web_hotel_search(message: str, area: str, budget_naira: int = None) -> str:
    """
    Uses Gemini + Google Search grounding to discover real hotels from the web
    when the local database has no results for the requested area.
    Returns a formatted reply ready to send to the user.
    """
    budget_ctx = f"with a budget around ₦{budget_naira:,}/night" if budget_naira else ""
    prompt = f"""
You are Vera, the HoLo Smart Checks AI — a brutally honest Lagos hotel guide.

Search the web RIGHT NOW for real, currently operating hotels and lodges in {area}, Lagos, Nigeria {budget_ctx}.

The user asked: "{message}"

Your task:
1. Search Google for actual hotels in {area} Lagos that are open today.
2. For each one, find honest guest reviews mentioning power backup, Wi-Fi quality, and value for money.
3. Flag any major complaints you find (e.g. no generator, slow WiFi, misleading photos).

Format your response EXACTLY like this (no deviation):
"Here's what I found in {area} after a live web check:

1. [Hotel Name] — ₦X,000/night
   ✅ [What works well] | ⚠️ [Honest concern if any]

2. [Hotel Name] — ₦X,000/night
   ✅ [What works well] | ⚠️ [Honest concern if any]

3. [Hotel Name] — ₦X,000/night
   ✅ [What works well] | ⚠️ [Honest concern if any]

Reply with 1, 2, or 3 to proceed."

IMPORTANT RULES:
- Only list hotels you can verify exist in {area} Lagos right now.
- If fewer than 3 exist, list what you find and explain honestly.
- Never invent hotel names. If you truly find nothing, say so and suggest the nearest area.
- Keep each hotel summary to 1-2 lines max.
"""
    try:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        c = get_client()
        response = c.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        print(f"Live Web Search Error: {e}")
        return ""


async def deep_audit_search(message: str, available_hotels: str = "") -> str:
    """
    Consolidated function for performing a 'Brutally Honest' live audit based on a user request.
    """
    prompt = f"""
    You are Vera, the HoLo Agentic Audit Engineer.
    
    YOUR AGENTIC MISSION:
    1. PRICE HUNT: Use your tools to find the actual room rates or estimated price range (e.g., ₦7,000 - ₦15,000) for every hotel.
    2. STRICT FENCE: If a hotel is not physically located in the requested neighborhood, it MUST be labeled [NEARBY].
    3. MANDATORY FORMAT:
       ### 📍 Hyper-Local Audit (Matches Area)
       **[Hotel Name]** — Truth Score: [Score]/100
       📍 **ADDRESS**: [Full Address]
       💳 **PRICE**: ₦[Amount or Range]
       ✅ [Strength] | ⚠️ [The Operational Risk]

    USER REQUEST: "{message}"
    
    VETTED DATA:
    {available_hotels}
    """
    
    try:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        c = get_client()
        response = await c.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini Deep Audit Error: {e}")
        return ""
