"""
HoLo — FastAPI Application Entry Point.
The Truth-Led Booking Platform for Lagos Professionals.
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from models.database import init_db, AsyncSessionLocal, get_db, engine
from sqlalchemy.ext.asyncio import AsyncSession
from seed_data import seed_hotels
from routers import sms, dashboard, payments, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and seed data on startup."""
    print("🚀 HoLo backend starting up...")
    if os.getenv("VERCEL") != "1":
        await init_db()
        async with AsyncSessionLocal() as db:
            await seed_hotels(db)
        print("✅ HoLo is ready. The Lagos Truth Engine is live.")
    else:
        print("⚡ Running in Vercel Serverless mode. Skipping DB init.")
    yield
    print("🛑 HoLo shutting down.")
    await engine.dispose()


app = FastAPI(
    title="HoLo API",
    description="The Truth-Led Booking Platform for Lagos Professionals",
    version="1.0.0",
    lifespan=lifespan,
    root_path="/api" if os.getenv("VERCEL") == "1" else "",
)

# CORS — allow dashboard frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skip ngrok browser warning for all visitors (free tier fix)
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class NgrokSkipWarning(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokSkipWarning)

# Register routers
app.include_router(sms.router)
app.include_router(dashboard.router)
app.include_router(payments.router)
app.include_router(auth.router)

# Serve static files from the public folder
public_path = Path(__file__).parent.parent / "public"
if public_path.exists():
    # Mount at /static for legacy references
    app.mount("/static", StaticFiles(directory=str(public_path)), name="static")
    # Mount at /assets so the dashboard can also be served as a directory
    app.mount("/assets", StaticFiles(directory=str(public_path)), name="assets")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(str(public_path / "index.html"))

    @app.get("/chat")
    async def serve_mobile_chat():
        return FileResponse(str(public_path / "chat.html"))

    @app.get("/go")
    async def serve_qr_redirect():
        return FileResponse(str(public_path / "go.html"))

    @app.get("/style.css")
    async def serve_style():
        return FileResponse(str(public_path / "style.css"), media_type="text/css")

    @app.get("/main.js")
    async def serve_main_js():
        return FileResponse(str(public_path / "main.js"), media_type="application/javascript")

    @app.post("/admin/trigger-vote")
    async def trigger_demo_vote(db: AsyncSession = Depends(get_db)):
        """Broadcasts voting request to all users for demo purposes."""
        from sqlalchemy import select
        from models.user import User
        from routers.sms import send_reply
        
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        count = 0
        for user in users:
            user.session_state = "POST_STAY"
            message = (
                "🛎️ HoLo: How was your stay? Reply with 1 number:\n\n"
                "1. Honest (Everything matched!)\n"
                "2. Laba Laba (Truth Alert! 🦋)\n\n"
                "Earn ₦100 airtime for your honest vote!"
            )
            if not user.phone.startswith("web_"):
                # For real SMS/WA
                from services import at_service
                if "whatsapp" in user.phone.lower():
                    at_service.send_whatsapp(user.phone, message)
                else:
                    at_service.send_sms(user.phone, message)
            
            # Note: For web-chat users, we rely on them seeing the message next time they poll or we can return it.
            # But for simplicity, we just set the state.
            count += 1
            
        await db.commit()
        return {"status": "broadcast_sent", "users_reached": count}


@app.get("/health")
async def health_check():
    return {
        "status": "🟢 HoLo is live",
        "platform": "The Truth-Led Booking Platform",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    from config import get_settings
    settings = get_settings()
    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port, reload=False)
