from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config.settings import settings
from utils.logger import logger
from .models import Base

# Ensure storage directory exists
db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
if db_path.startswith("./") or not db_path.startswith("/"):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db() -> None:
    """Initializes the database schema and performs lightweight migrations."""
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Safely migrate existing tables with new columns
        from sqlalchemy import text
        for col, col_type in [
            ("description", "TEXT"),
            ("upload_url", "VARCHAR(512)"),
            ("upload_storage_type", "VARCHAR(64)"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE lots ADD COLUMN {col} {col_type}"))
            except Exception:
                pass

    logger.info("Database initialized successfully.")

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context helper for obtaining an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
