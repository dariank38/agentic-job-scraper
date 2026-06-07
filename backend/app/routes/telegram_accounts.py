from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.connection import get_db
from app.models import TelegramAccount


class TelegramAccountCreate(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str


class TelegramAccountResponse(BaseModel):
    id: int
    api_id: int
    phone_number: str
    session_name: str
    is_active: bool
    is_authenticated: bool
    created_at: str
    last_used_at: Optional[str]


def register_telegram_account_routes(app):
    """Register Telegram account management routes."""

    @app.get("/api/telegram-accounts", response_model=List[TelegramAccountResponse])
    async def get_telegram_accounts(db: AsyncSession = Depends(get_db)):
        """Get all Telegram accounts."""
        result = await db.execute(select(TelegramAccount))
        accounts = result.scalars().all()
        return [
            {
                "id": acc.id,
                "api_id": acc.api_id,
                "phone_number": acc.phone_number,
                "session_name": acc.session_name,
                "is_active": acc.is_active,
                "is_authenticated": acc.is_authenticated,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
                "last_used_at": acc.last_used_at.isoformat() if acc.last_used_at else None,
            }
            for acc in accounts
        ]

    @app.post("/api/telegram-accounts", response_model=TelegramAccountResponse)
    async def create_telegram_account(
        account: TelegramAccountCreate, db: AsyncSession = Depends(get_db)
    ):
        """Create a new Telegram account."""
        # Check if phone number already exists
        result = await db.execute(
            select(TelegramAccount).filter(TelegramAccount.phone_number == account.phone_number)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Phone number already exists")

        # Generate session name
        session_name = f"session_{account.phone_number.replace('+', '')}"

        new_account = TelegramAccount(
            api_id=account.api_id,
            api_hash=account.api_hash,
            phone_number=account.phone_number,
            session_name=session_name,
        )
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        return {
            "id": new_account.id,
            "api_id": new_account.api_id,
            "phone_number": new_account.phone_number,
            "session_name": new_account.session_name,
            "is_active": new_account.is_active,
            "is_authenticated": new_account.is_authenticated,
            "created_at": new_account.created_at.isoformat() if new_account.created_at else None,
            "last_used_at": new_account.last_used_at.isoformat() if new_account.last_used_at else None,
        }

    @app.delete("/api/telegram-accounts/{account_id}")
    async def delete_telegram_account(account_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a Telegram account."""
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        await db.delete(account)
        await db.commit()
        return {"success": True}

    @app.patch("/api/telegram-accounts/{account_id}/toggle-active")
    async def toggle_account_active(account_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle account active status."""
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        account.is_active = not account.is_active
        await db.commit()
        return {"success": True, "is_active": account.is_active}
