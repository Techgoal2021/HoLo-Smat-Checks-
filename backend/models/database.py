from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

settings = get_settings()

# asyncpg handles SSL via connect_args, not URL params
# Strip ?sslmode=require from URL if present (asyncpg doesn't support it)
database_url = settings.database_url.split('?')[0]

if "postgresql" in database_url:
    connect_args = {"statement_cache_size": 0, "ssl": "require"}
else:
    connect_args = {}

engine = create_async_engine(
    database_url,
    echo=False,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        from models.hotel import Hotel
        from models.user import User
        from models.vote import Vote
        await conn.run_sync(Base.metadata.create_all)
