"""Reset published_to_jobees=False for jobs that have company_link.

This allows the publisher to re-send those jobs to Jobees with the company_link
field populated. The Jobees external bulk endpoint now upserts (updates existing
jobs instead of skipping), so re-publishing won't create duplicates.

Usage:
    cd backend
    python -m scripts.reset_published          # reset all jobs with company_link
    python -m scripts.reset_published --all    # reset ALL published jobs
"""

import argparse
import asyncio

from sqlalchemy import select, update

from app.connection import AsyncSessionLocal
from app.models import Job


async def reset_published(reset_all: bool = False):
    async with AsyncSessionLocal() as db:
        if reset_all:
            result = await db.execute(
                select(Job).filter(Job.published_to_jobees == True)
            )
        else:
            result = await db.execute(
                select(Job).filter(
                    Job.published_to_jobees == True,
                    Job.company_link.isnot(None),
                    Job.company_link != "",
                )
            )
        jobs = result.scalars().all()

        count = len(jobs)
        if count == 0:
            print("No jobs to reset.")
            return

        print(f"Found {count} jobs to reset:")
        for job in jobs[:10]:
            print(f"  → id={job.id} | title={job.title[:60]} | company_link={job.company_link}")
        if count > 10:
            print(f"  ... and {count - 10} more")

        await db.execute(
            update(Job)
            .where(Job.id.in_([j.id for j in jobs]))
            .values(published_to_jobees=False, published_at=None)
        )
        await db.commit()
        print(f"\nReset {count} jobs to published_to_jobees=False.")
        print("Run the publisher to re-publish them to Jobees with company_link.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset published_to_jobees flag")
    parser.add_argument(
        "--all", action="store_true",
        help="Reset ALL published jobs (not just those with company_link)",
    )
    args = parser.parse_args()
    asyncio.run(reset_published(reset_all=args.all))
