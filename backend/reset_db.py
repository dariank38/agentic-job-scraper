"""Reset the database by dropping and reinitializing tables."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from telegram_processor.config import DATABASE_URL
from app import models

async def reset_database():
    """Drop all tables and recreate them."""
    print(f"Connecting to database: {DATABASE_URL}")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(models.Base.metadata.drop_all)
        
        print("Creating all tables...")
        await conn.run_sync(models.Base.metadata.create_all)
    
    await engine.dispose()
    print("Database reset complete!")

if __name__ == "__main__":
    asyncio.run(reset_database())
