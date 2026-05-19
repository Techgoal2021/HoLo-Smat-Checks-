"""
Seed the HoLo database with minimal baseline data.
The system focuses on LIVE DISCOVERY for neighborhood-level ground truth.
"""
from models.hotel import Hotel
from sqlalchemy import delete

# Minimal baseline for system testing (Purely dynamic system)
LAGOS_HOTELS = [
    {
        "name": "HoLo Baseline - Yaba",
        "area": "Yaba",
        "address": "Baseline Data Point, Yaba, Lagos",
        "price_naira": 15000,
        "truth_score": 50.0,
        "review_summary": "System baseline. Use Live Discovery for real spots.",
    }
]

async def seed_hotels(db):
    """Insert minimal seeds and WIPE old data."""
    print("🧹 Cleaning database... Ensuring a PURELY DYNAMIC experience.")
    await db.execute(delete(Hotel))
    await db.commit()

    for hotel_data in LAGOS_HOTELS:
        hotel = Hotel(**hotel_data)
        db.add(hotel)

    await db.commit()
    print("✅ Database is clean. Live Discovery Radar is active.")

if __name__ == "__main__":
    import asyncio
    from models.database import Base, engine, AsyncSessionLocal
    async def run_seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSessionLocal() as session:
            await seed_hotels(session)
        await engine.dispose()
    asyncio.run(run_seed())
