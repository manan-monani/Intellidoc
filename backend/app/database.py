"""
IntelliDoc Database Connection
==============================
Async SQLAlchemy engine and session factory.

How it works:
- Uses AsyncEngine for non-blocking database operations
- Provides `get_db()` dependency for FastAPI routes
- Sessions are automatically committed on success, rolled back on error
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────
# The engine manages the connection pool to PostgreSQL.
# echo=True in debug mode logs all SQL queries to the console.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,         # Max connections kept open
    max_overflow=20,      # Extra connections allowed during bursts
    pool_pre_ping=True,   # Check connections are alive before using
)

# ── Session Factory ──────────────────────────────────────────
# Each request gets its own session via dependency injection.
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
)


# ── Base Model ───────────────────────────────────────────────
# All SQLAlchemy models inherit from this.
class Base(DeclarativeBase):
    pass


# ── Dependency ───────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle ────────────────────────────────────────────────
async def init_db():
    """Create all database tables. Called on app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close all connections. Called on app shutdown."""
    await engine.dispose()
