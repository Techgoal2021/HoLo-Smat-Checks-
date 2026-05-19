"""
Dashboard API Router — Serves data to the HoLo Honesty Dashboard.
"""
import httpx
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.database import get_db
from models.hotel import Hotel
from models.vote import Vote
from pathlib import Path

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/config")
async def get_dashboard_config(request: Request):
    """
    Attempts to auto-detect the public URL for the QR code.
    Checks ngrok local API first, then falls back to current request host.
    """
    public_url = None
    try:
        async with httpx.AsyncClient() as client:
            # Ngrok local API is usually at 4040
            response = await client.get("http://127.0.0.1:4040/api/tunnels", timeout=0.5)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data.get("tunnels", []):
                    if tunnel.get("proto") == "https":
                        public_url = tunnel.get("public_url")
                        break
    except Exception:
        pass

    if not public_url:
        # Fallback to current origin
        public_url = str(request.base_url).rstrip("/")

    return {"public_url": public_url}

AREAS = ["Yaba", "Lekki", "Victoria Island", "Ikeja", "Surulere"]


@router.get("/hotels")
async def get_hotels(db: AsyncSession = Depends(get_db)):
    """Return all hotels with their current Truth Scores."""
    result = await db.execute(select(Hotel).order_by(Hotel.truth_score.desc()))
    hotels = result.scalars().all()
    return {"hotels": [h.to_dict() for h in hotels]}


@router.get("/hotels/{hotel_id}")
async def get_hotel(hotel_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalars().first()
    if not hotel:
        return {"error": "Hotel not found"}
    return hotel.to_dict()


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate platform stats for the dashboard hero section."""
    hotels_result = await db.execute(select(Hotel))
    hotels = hotels_result.scalars().all()

    votes_result = await db.execute(select(func.count(Vote.id)))
    total_votes = votes_result.scalar() or 0

    avg_truth = sum(h.truth_score for h in hotels) / len(hotels) if hotels else 0
    verified_count = sum(1 for h in hotels if h.truth_score >= 80)

    # Area breakdown
    area_stats = []
    for area in AREAS:
        area_hotels = [h for h in hotels if h.area == area]
        if area_hotels:
            avg = sum(h.truth_score for h in area_hotels) / len(area_hotels)
            area_stats.append({
                "area": area,
                "avg_truth_score": round(avg, 1),
                "hotel_count": len(area_hotels),
                "verified_count": sum(1 for h in area_hotels if h.truth_score >= 80),
            })

    return {
        "total_hotels": len(hotels),
        "total_votes": total_votes,
        "avg_truth_score": round(avg_truth, 1),
        "verified_hotels": verified_count,
        "area_breakdown": area_stats,
    }


@router.get("/activity")
async def get_recent_activity(db: AsyncSession = Depends(get_db)):
    """Return the latest 20 votes for the live feed."""
    result = await db.execute(
        select(Vote, Hotel.name)
        .join(Hotel, Vote.hotel_id == Hotel.id)
        .order_by(Vote.created_at.desc())
        .limit(20)
    )
    rows = result.all()

    activity = []
    for vote, hotel_name in rows:
        power_text = "✅ Power OK" if vote.power_ok else "❌ Power Issues"
        activity.append({
            "hotel_name": hotel_name,
            "vote_type": vote.vote_type,
            "power_ok": vote.power_ok,
            "label": power_text,
            "time": vote.created_at.isoformat(),
        })

    return {"activity": activity}


@router.post("/intelligence/update")
async def update_live_intelligence(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Triggers a background crawl of Google Search to update all hotel Truth Scores.
    """
    from services.gemini_engine import analyze_hotel_reputation
    
    result = await db.execute(select(Hotel))
    hotels = result.scalars().all()
    
    async def process_intelligence():
        # Using a new session for the background task
        from models.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            for hotel in hotels:
                print(f"🕵️ HoLo Intel: Analyzing {hotel.name}...")
                intel = analyze_hotel_reputation(hotel.name, hotel.area)
                
                # Fetch fresh hotel instance for this session
                h = await session.get(Hotel, hotel.id)
                h.power_score = intel["power_score"]
                h.wifi_score = intel["wifi_score"]
                h.security_score = intel["security_score"]
                h.staff_score = intel["staff_score"]
                h.truth_score = intel["truth_score"]
                h.review_summary = f"LIVE INTEL: {intel['sentiment_summary']}"
                
            await session.commit()
            print("✅ HoLo Intel: All hotels updated from live web feeds.")

    background_tasks.add_task(process_intelligence)
    return {"status": "intelligence_crawl_started", "hotels_queued": len(hotels)}
