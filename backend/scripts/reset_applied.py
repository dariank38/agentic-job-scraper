"""Reset all is_applied flags to False for jobs."""

import asyncio
from sqlalchemy import select, update
from app.connection import get_db
from app.models import Job

async def reset_applied():
    async for db in get_db():
        # Count jobs with is_applied=True
        result = await db.execute(select(Job).filter(Job.is_applied == True))
        jobs = result.scalars().all()
        
        print(f'Found {len(jobs)} jobs with is_applied=True')
        
        if jobs:
            # Reset all to False
            await db.execute(update(Job).values(is_applied=False, applied_at=None))
            await db.commit()
            print(f'Reset {len(jobs)} jobs to is_applied=False')
        else:
            print('No jobs to reset')

if __name__ == "__main__":
    asyncio.run(reset_applied())
