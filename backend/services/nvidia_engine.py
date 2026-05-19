import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
# Using the NVIDIA NIM endpoint for Llama 3.1 70B
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

import httpx

def nvidia_executive_audit(message, available_hotels, web_context=""):
    """
    Performs a high-performance Executive Audit using NVIDIA NIM optimized inference.
    """
    if not NVIDIA_API_KEY:
        return None

    from services.persona import get_system_prompt
    system_instruction = get_system_prompt("audit")

    prompt = f"""
    {system_instruction}

    USER REQUEST: "{message}"
    
    VETTED OPTIONS FROM OUR DATABASE:
    {available_hotels}
    
    LIVE WEB CONTEXT:
    {web_context}
    
    YOUR GOAL:
    1. CATEGORIZE the results into two groups:
       - GROUP A (Hyper-Local): Hotels that are EXACTLY in the user's requested area (check the address).
       - GROUP B (Elite Nearby): Better alternatives within a 10-15 minute radius (e.g. Ikeja, Omole).
    
    2. PRIORITY: List GROUP A first. Even if the 'Truth Score' is lower, the user's geographic constraint is primary.
    
    3. AUDIT: Be sharp about 'Operational Reality' (Wi-Fi/Power). If a spot is shaky, flag it. 

    FORMAT:
    ### 📍 Hyper-Local Audit (Matches your exact area)
    1. **[Hotel Name]** — Truth Score: [Score]/100
       ✅ [Strength] | ⚠️ [Operational Risk]

    ### 🚀 Elite Nearby Alternatives
    [Only 1 or 2 high-quality options]
    2. **[Hotel Name]** — Truth Score: [Score]/100

    End by asking them to reply with the number (1, 2, or 3) to lock it in. 🇳🇬⚡️
    """

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta/llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024
    }

    try:
        # Use sync httpx client to match the existing synchronous function signature
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"⚠️ NVIDIA Engine Error: {e}")
        return None
