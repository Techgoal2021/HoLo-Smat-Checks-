import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from models.database import init_db
from routers.sms import _handle_search

async def main():
    await init_db()
    print("\n--- TEST: Finding a hotel in a missing area ---")
    reply = await _handle_search("web_12345", "Find me a hotel in Epe under 40k", is_web=True)
    print("\n[AI REPLY]:")
    print(reply)

if __name__ == "__main__":
    asyncio.run(main())
