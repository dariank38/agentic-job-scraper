import asyncio

from sqlalchemy import func, select

from app.connection import get_db
from app.models import Job


async def check():
    db = await get_db()
    
    # Count jobs with is_applied=True
    result = await db.execute(select(func.count()).select_from(Job).filter(Job.is_applied == True))
    count = result.scalar()
    print(f'Jobs with is_applied=True: {count}')
    
    # Show details of those jobs
    result2 = await db.execute(select(Job).filter(Job.is_applied == True).limit(5))
    jobs = result2.scalars().all()
    for job in jobs:
        print(f'Job {job.id}: {job.title}, is_applied={job.is_applied}, applied_at={job.applied_at}')

asyncio.run(check())
