"""
HoLo Messaging Router — Africa's Talking & Web-Chat handler.
"""
from fastapi import APIRouter, Request, Form, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db, AsyncSessionLocal
from models.user import User
from models.hotel import Hotel
from models.vote import Vote
from services import gemini_engine, at_service, payment_service
from services.groq_engine import groq_audit_search, groq_live_discovery, groq_parse_intent
from typing import Optional

router = APIRouter(prefix="/sms", tags=["sms"])

HELP_MESSAGE = "👋 Welcome to HoLo Smart checks! I'm your honest Hotels and Lodges guide. How may I be of help today?"

RESET_KEYWORDS = {"restart", "reset", "start over", "cancel", "stop", "back"}

# ─── Helpers ────────────────────────────────────────────────────────────────

async def get_or_create_user(phone: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalars().first()
    if not user:
        try:
            user = User(phone=phone)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        except Exception:
            # Likely a race condition where user was created by another request
            await db.rollback()
            result = await db.execute(select(User).where(User.phone == phone))
            user = result.scalars().first()
            if not user:
                raise # Re-raise if it's truly a different error
    return user

async def send_reply(phone: str, message: str):
    """
    Intelligently route reply. Web users get ignored here (handled in response).
    """
    if phone.startswith("web_"):
        return # Handled by the synchronous return in incoming_msg
        
    if "whatsapp" in phone.lower():
        at_service.send_whatsapp(phone, message)
    else:
        at_service.send_sms(phone, message)

@router.get("/poll")
async def poll_messages(phone: str, db: AsyncSession = Depends(get_db)):
    """Allows web-chat to poll for 'push' messages from backend."""
    user = await get_or_create_user(phone, db)
    if user.session_state == "POST_STAY":
        # Check if we should send the vote prompt
        return {"reply": (
            "🛎️ HoLo: How was your stay? Reply with 1 number:\n\n"
            "1. Honest (Everything matched!)\n"
            "2. Laba Laba (Truth Alert! 🦋)\n\n"
            "Earn ₦100 airtime for your honest vote!"
        )}
    return {"reply": None}

# ─── Main Webhook ────────────────────────────────────────────────────────────

@router.post("/incoming")
async def incoming_msg(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    from_: Optional[str] = Form(None, alias="from"),
    to: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
):
    form = await request.form()
    phone = from_ or form.get("from", "")
    message = (text or form.get("text", "")).strip()

    if not phone or not message:
        return {"status": "ignored"}

    print(f"📨 Incoming from {phone}: '{message}'")
    user = await get_or_create_user(phone, db)

    # Web Chat Mode: Returns response directly to browser
    if phone.startswith("web_"):
        # 🔄 SMART RESET: If user sends a long message, assume they want a new search
        # regardless of current state (unless they specifically sent a number)
        is_numeric = message.strip().isdigit() and len(message.strip()) <= 2
        if not is_numeric and user.session_state != "IDLE":
            print(f"🔄 Smart Reset for {phone} (New search intent detected)")
            user.session_state = "IDLE"
            await db.commit()

        if message.lower() in RESET_KEYWORDS or message.lower() in {"hi", "hello", "hey"}:
            return {"reply": HELP_MESSAGE}
        
        # Determine handler based on state
        if user.session_state == "POST_STAY":
            reply = await _handle_post_stay_vote(phone, message, is_web=True)
        elif user.session_state == "AWAITING_SELECTION" and is_numeric:
            reply = await _handle_hotel_selection(phone, message, is_web=True)
        elif user.session_state == "AWAITING_PAYMENT_METHOD" and is_numeric:
            reply = await _handle_payment_method(phone, message, is_web=True)
        else:
            # Default to search if state is IDLE or if message is a new search intent
            reply = await _handle_search(phone, message, is_web=True)
        
        return {"reply": reply}

    # Standard AT Mode: Uses background tasks
    if message.lower() in RESET_KEYWORDS:
        user.session_state = "IDLE"
        await db.commit()
        background_tasks.add_task(send_reply, phone, HELP_MESSAGE)
        return {"status": "reset"}

    if message.lower() in {"help", "hi", "hello", "hey"}:
        background_tasks.add_task(send_reply, phone, HELP_MESSAGE)
        return {"status": "help_sent"}

    if user.session_state == "POST_STAY":
        background_tasks.add_task(_handle_post_stay_vote, phone, message)
    elif user.session_state == "AWAITING_SELECTION":
        background_tasks.add_task(_handle_hotel_selection, phone, message)
    elif user.session_state == "AWAITING_PAYMENT_METHOD":
        background_tasks.add_task(_handle_payment_method, phone, message)
    else:
        background_tasks.add_task(_handle_search, phone, message)
    
    return {"status": "processing"}

# ─── Handlers ────────────────────────────────────────────────────────────────

async def _handle_search(phone: str, message: str, is_web: bool = False):
    # 🛡️ Force local scope for models to avoid UnboundLocalError
    from models.user import User
    from models.hotel import Hotel
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalars().first()
        try:
            # 🧠 [GEMINI PRIMARY]: Parsing intent
            from services.gemini_engine import gemini_parse_intent
            print(f"🧠 [GEMINI PRIMARY]: Parsing intent for '{message}'...")
            intent = await gemini_parse_intent(message)
            print(f"🎯 Intent: {intent}")
            
            # Handle conversational messages (non-booking)
            if not intent.get('is_booking_request') and not intent.get('area'):
                print("🧠 [GEMINI PRIMARY]: Responding to general chat...")
                from services.groq_engine import groq_conversational_reply
                reply = await groq_conversational_reply(message) # Keeping Groq as high-speed chat fallback
                if not is_web: await send_reply(phone, reply)
                return reply
            
            # 🔍 UPFRONT DB SEARCH (Grounding)
            # ⚡️ HUMAN RHYTHMS: Backchanneling (Instant Acknowledgment)
            area_context = intent.get('area', 'Lagos')
            backchannel = f"Got you. ⚡️ Auditing {area_context} spots for operational reality... Give me a sec."
            if not is_web: await send_reply(phone, backchannel)
            
            # DB Search
            final_query = select(Hotel)
            if intent.get("area") and intent["area"] != "Lagos":
                final_query = final_query.where(Hotel.area.ilike(f"%{intent['area']}%"))
            if intent.get("budget_naira"):
                # Allow 20% flexibility to ensure we don't miss hyper-local gems over small price gaps
                max_budget = intent["budget_naira"] * 1.2
                final_query = final_query.where(Hotel.price_naira <= max_budget)
            
            result = await session.execute(final_query.order_by(Hotel.truth_score.desc()))
            hotels = result.scalars().all()
            
            # HARD VALIDATION: Even if the DB matched it, verify the area keyword in the name, address, or area field
            if intent.get("area") and intent["area"] != "Lagos":
                target_kws = {kw.lower() for kw in intent["area"].split() if len(kw) > 3}
                if target_kws:
                    hotels = [
                        h for h in hotels 
                        if any(kw in h.area.lower() or kw in h.name.lower() or kw in h.address.lower() for kw in target_kws)
                    ]
            
            if not hotels:
                # 🌐 DB MISS — try Groq+DDG first (free), then Gemini web search
                area_to_search = intent.get('area') or 'Lagos'
                budget = intent.get('budget_naira')

                # Try Groq + Google Places
                web_reply, hotel_names = await groq_live_discovery(message, area_to_search, budget)

                if web_reply:
                    # Store web marker, budget, area, and comma-separated hotel names
                    safe_budget = budget if budget else 15000
                    names_str = ",".join(hotel_names) if hotel_names else "Unknown Lodge"
                    user.last_results = f"web|{safe_budget}|{area_to_search}|{names_str}"
                    user.session_state = "AWAITING_SELECTION"
                    await session.commit()
                    if not is_web: await send_reply(phone, web_reply)
                    return web_reply
                else:
                    reply = f"⚠️ Even the live web is quiet for {area_to_search} right now. Try a different area or budget?"
                    if not is_web: await send_reply(phone, reply)
                    return reply
            
            # Format DB hotels into a strict string so AI stops hallucinating
            hotel_dicts = [h.to_dict() for h in hotels][:3] # Only pass top 3
            hotel_data = "\n".join([f"{i+1}. {h['name']} ({h['area']}) - ₦{h['price_naira']:,} | Truth Score: {h['truth_score']}/100 | Address: {h['address']}" for i, h in enumerate(hotel_dicts)])
            
            # Save hotel IDs for selection step
            user.last_results = ",".join([str(h['id']) for h in hotel_dicts])
            
            # 🧠 MULTI-ENGINE AI ORCHESTRATION (The 'Executive Brain')
            from services.nvidia_engine import nvidia_executive_audit
            
            # --- PRIMARY ENGINE: Gemini 2.0 (High Fidelity Audit) ---
            try:
                print(f"🧠 [GEMINI PRIMARY]: Performing Truth-Led Audit for '{message}'...")
                ai_response = await gemini_engine.deep_audit_search(message, hotel_data)
            except Exception as gem_e:
                print(f"⚠️ Gemini Primary busy or quota hit: {gem_e}")
                ai_response = None

            # --- FALLBACK 1: Groq LPU (Now Primary Fallback) ---
            if not ai_response or "⚠️" in ai_response:
                try:
                    print("🧠 [GROQ FALLBACK]: Triggering Groq LPU...")
                    ai_response = await groq_audit_search(message, hotel_data)
                except Exception as ge:
                    print(f"⚠️ Groq Engine busy: {ge}")
            
            # --- FALLBACK 2: NVIDIA NIM (Backup) ---
            if not ai_response or "⚠️" in ai_response:
                try:
                    print(f"⚡ [NVIDIA BACKUP]: Auditing for '{message}'...")
                    from services.nvidia_engine import nvidia_executive_audit
                    ai_response = nvidia_executive_audit(message, hotel_data, web_context="")
                except Exception as ne:
                    print(f"⚠️ NVIDIA Engine busy: {ne}")
            
            if not ai_response or "⚠️" in ai_response:
                area_requested = intent.get('area', 'that area')
                ai_response = f"Vera here. ⚡️ I've scanned {area_requested} and the surrounding grid, but I'm not seeing any verified lodges meeting our Truth Score threshold right there. Should we expand the audit to a nearby stable neighborhood?"
                
            if ai_response and "⚠️" not in ai_response:
                user.session_state = "AWAITING_SELECTION"
                await session.commit()
                if not is_web: await send_reply(phone, ai_response)
                return ai_response
            else:
                # 🛡️ [TOTAL PRICE LOCK]: Force price into every result
                print("🛠️ [SYSTEM]: Enforcing Total Price Lock...")
                area = intent.get('area', 'Lagos')
                ai_response = f"Vera here. 👋 Here's your price-verified audit for {area}:\n\n"
                
                for i, h in enumerate(hotel_dicts):
                    ai_response += f"**{h['name']}** — Truth Score: {h['truth_score']}/100\n"
                    ai_response += f"📍 **ADDRESS**: {h['address']}\n"
                    ai_response += f"💳 **PRICE**: ₦{h['price_naira']:,}\n"
                    ai_response += f"✅ Verified operational | ⚠️ Ground Truth active\n\n"
                
                ai_response += "Reply with the hotel number to proceed."
                user.session_state = "AWAITING_SELECTION"
                await session.commit()
                if not is_web: await send_reply(phone, ai_response)
                return ai_response

        except Exception as e:
            import traceback
            traceback.print_exc()
            reply = "⚠️ HoLo: Small Lagos moment while searching. Try again in 30s!"
            if not is_web: await send_reply(phone, reply)
            return reply

async def _handle_hotel_selection(phone: str, message: str, is_web: bool = False):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalars().first()
        # Handle web-discovered hotels (no DB IDs)
        if user.last_results and user.last_results.startswith("web|"):
            parts = user.last_results.split("|")
            area = parts[2] if len(parts) > 2 else "Lagos"
            hotel_names_str = parts[3] if len(parts) > 3 else "Unknown Web Lodge::15000"
            hotel_data_list = hotel_names_str.split(",")
            
            try:
                selection_idx = int(message.strip()) - 1
                if selection_idx < 0 or selection_idx >= len(hotel_data_list):
                    reply = "❓ HoLo: Please reply with just 1, 2, or 3."
                    if not is_web: await send_reply(phone, reply)
                    return reply
                
                selected_data = hotel_data_list[selection_idx].strip()
                hotel_parts = selected_data.split("::")
                selected_name = hotel_parts[0]
                real_price = int(hotel_parts[1]) if len(hotel_parts) > 1 and hotel_parts[1].isdigit() else 15000
                
                # Create a temporary Hotel record using the REAL scraped price
                new_hotel = Hotel(
                    name=selected_name,
                    area=area,
                    address="Verified Google Hotels Address",
                    price_naira=real_price,
                    truth_score=80.0, # Real web data
                    review_summary="Live pricing from Google Hotels via SerpApi."
                )
                session.add(new_hotel)
                await session.flush() # Get the new ID
                
                user.selected_hotel_id = new_hotel.id
                user.session_state = "AWAITING_PAYMENT_METHOD"
                await session.commit()
                
                reply = (
                    f"🏨 Locked in! You've selected {selected_name}.\n"
                    f"💳 Since this is a local web discovery, we are logging your requested budget of ₦{real_price:,} as a deposit.\n\n"
                    f"Our concierge team will contact the hotel to secure the booking.\n"
                    f"How would you like to pay your deposit?\n"
                    f"1. Paystack (Card/USSD)\n"
                    f"2. Bank Transfer (Naira)\n"
                    f"3. Pay at Hotel"
                )
                if not is_web: await send_reply(phone, reply)
                return reply
                
            except ValueError:
                pass

        # Standard DB hotel selection
        try:
            selection_idx = int(message.strip()) - 1
            hotel_ids = user.last_results.split(",")
            if selection_idx < 0 or selection_idx >= len(hotel_ids):
                reply = "❓ HoLo: Please reply with just 1, 2, or 3."
                if not is_web: await send_reply(phone, reply)
                return reply
                
            hotel_id = int(hotel_ids[selection_idx])
            result = await session.execute(select(Hotel).where(Hotel.id == hotel_id))
            hotel = result.scalar_one_or_none()
            
            # Save selection but don't pay yet
            user.selected_hotel_id = hotel_id
            user.session_state = "AWAITING_PAYMENT_METHOD"
            await session.commit()

            reply = (
                f"🏨 You've picked: {hotel.name}\n"
                f"💰 Total: ₦{hotel.price_naira:,}\n\n"
                f"How would you like to pay?\n"
                f"1. Paystack (Card/Bank Transfer)\n"
                f"2. Crypto (USDT)\n"
                f"3. Pay at Hotel\n\n"
                f"Reply with 1, 2, or 3."
            )
            if not is_web: await send_reply(phone, reply)
            return reply

        except Exception as e:
            print(f"Error in selection: {e}")
            reply = "⚠️ HoLo: Something went wrong. Let's try picking that lodge again?"
            if not is_web: await send_reply(phone, reply)
            return reply

async def _handle_payment_method(phone: str, message: str, is_web: bool = False):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalars().first()
        
        try:
            choice = message.strip()
            result = await session.execute(select(Hotel).where(Hotel.id == user.selected_hotel_id))
            hotel = result.scalar_one_or_none()

            if choice == "1":
                # Online Payment (Paystack)
                payment = payment_service.create_payment_link(
                    email=f"user_{phone.replace('+', '').replace('whatsapp:', '')}@holo.app",
                    amount_naira=hotel.price_naira,
                    hotel_name=hotel.name
                )
                
                if payment["success"]:
                    reply = (
                        f"✅ Secure Payment Link (Card/Transfer):\n"
                        f"{payment['authorization_url']}\n\n"
                        f"Once paid, your booking is instant. See you there!"
                    )
                    user.session_state = "AWAITING_PAYMENT"
                    await session.commit()
                else:
                    reply = "⚠️ Online payment service is down. Try choosing 'Pay at Hotel'?"
                
            elif choice == "2":
                # Crypto Payment (Placeholder)
                reply = (
                    f"🏧 HoLo Bank Transfer:\n"
                    f"Bank: Wema Bank (HoLo Verified)\n"
                    f"Account: 0123456789\n"
                    f"Amount: ₦{hotel.price_naira:,}\n\n"
                    f"Once transferred, reply with 'DONE' or your transaction receipt."
                )
                # Keep in AWAITING_PAYMENT_METHOD or move to a verification state
                
            elif choice == "3":
                # Cash at Hotel
                import uuid
                ref = f"HOLO-{str(uuid.uuid4())[:8].upper()}"
                user.booking_reference = ref
                user.session_state = "BOOKED"
                await session.commit()
                
                reply = (
                    f"✅ Booking Confirmed (Pay at Hotel)!\n"
                    f"Lodge: {hotel.name}\n"
                    f"Reference: {ref}\n\n"
                    f"Please show this code at the front desk. They are expecting you!"
                )
            else:
                reply = "❓ Please reply with 1 (Paystack), 2 (Bank Transfer), or 3 (Pay at Hotel)."

            if not is_web: await send_reply(phone, reply)
            return reply

        except Exception as e:
            print(f"Error in payment method: {e}")
            reply = "⚠️ Small issue setting up your payment. Try again?"
            if not is_web: await send_reply(phone, reply)
            return reply

async def _handle_post_stay_vote(phone: str, message: str, is_web: bool = False):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalars().first()
        
        # Airtime logic (only for real phone numbers)
        if not phone.startswith("web_"):
            at_service.send_airtime(phone, 100)
            reply = "🎁 THANK YOU! Your honest vote earned you ₦100 airtime. Score updated! 🥂"
        else:
            reply = "🎁 THANK YOU! Your vote has been recorded and the Truth Score updated! 🥂"
            
        user.session_state = "IDLE"
        await session.commit()
        if not is_web: await send_reply(phone, reply)
        return reply
