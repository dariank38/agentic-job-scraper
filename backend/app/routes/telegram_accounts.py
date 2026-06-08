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
    username: Optional[str]
    session_name: str
    is_active: bool
    is_authenticated: bool
    created_at: str
    last_used_at: Optional[str]


class AuthRequest(BaseModel):
    account_id: int


class CodeRequest(BaseModel):
    account_id: int
    code: str


class PasswordRequest(BaseModel):
    account_id: int
    password: str


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
                "username": acc.username,
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
            "username": new_account.username,
            "session_name": new_account.session_name,
            "is_active": new_account.is_active,
            "is_authenticated": new_account.is_authenticated,
            "created_at": new_account.created_at.isoformat() if new_account.created_at else None,
            "last_used_at": new_account.last_used_at.isoformat() if new_account.last_used_at else None,
        }

    @app.delete("/api/telegram-accounts/{account_id}")
    async def delete_telegram_account(account_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a Telegram account and clean up session file."""
        from pathlib import Path
        from telegram_processor import TelegramClientManager

        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Clean up session file
        try:
            session_path = TelegramClientManager(
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone_number,
                session_name=account.session_name,
            ).session_path
            if Path(session_path).exists():
                Path(session_path).unlink()
        except Exception:
            pass  # Ignore cleanup errors

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

    @app.post("/api/telegram-accounts/authenticate")
    async def start_authentication(request: AuthRequest, db: AsyncSession = Depends(get_db)):
        """Start authentication process for a Telegram account."""
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == request.account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        from telegram_processor import TelegramClientManager
        from pathlib import Path

        # Create a client manager for this account
        manager = TelegramClientManager(
            api_id=account.api_id,
            api_hash=account.api_hash,
            phone_number=account.phone_number,
            session_name=account.session_name,
        )

        # Delete existing session file if it exists to start fresh
        session_file = Path(manager.session_path)
        if session_file.exists():
            session_file.unlink()

        # Connect without auto-start, then send code request
        client = None
        try:
            client = await manager.connect(auto_start=False)
            result = await client.send_code_request(account.phone_number)
            # Store the phone_code_hash in database for verification
            account.phone_code_hash = result.phone_code_hash
            await db.commit()
            return {"success": True, "message": "Code sent to your phone"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            if client:
                await manager.disconnect()

    @app.post("/api/telegram-accounts/verify-code")
    async def verify_code(request: CodeRequest, db: AsyncSession = Depends(get_db)):
        """Verify the authentication code."""
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == request.account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get the phone_code_hash from database
        if not account.phone_code_hash:
            raise HTTPException(status_code=400, detail="Authentication session expired. Please request a new code.")

        from telegram_processor import TelegramClientManager

        # Create a client manager for this account
        manager = TelegramClientManager(
            api_id=account.api_id,
            api_hash=account.api_hash,
            phone_number=account.phone_number,
            session_name=account.session_name,
        )

        client = None
        try:
            client = await manager.connect(auto_start=False)
            await client.sign_in(account.phone_number, request.code, phone_code_hash=account.phone_code_hash)
            # Update account as authenticated and clear the hash
            account.is_authenticated = True
            account.phone_code_hash = None
            await db.commit()
            return {"success": True, "message": "Account authenticated successfully"}
        except Exception as e:
            error_msg = str(e)
            # Check for various forms of the 2FA error
            if "SessionPasswordNeededError" in error_msg or "two-steps verification" in error_msg.lower() or "password is required" in error_msg.lower():
                return {"success": False, "needs_password": True, "message": "Two-factor authentication password required"}
            raise HTTPException(status_code=400, detail=error_msg)
        finally:
            if client:
                await manager.disconnect()

    @app.post("/api/telegram-accounts/verify-password")
    async def verify_password(request: PasswordRequest, db: AsyncSession = Depends(get_db)):
        """Verify the 2FA password."""
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == request.account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        from telegram_processor import TelegramClientManager

        # Create a client manager for this account
        manager = TelegramClientManager(
            api_id=account.api_id,
            api_hash=account.api_hash,
            phone_number=account.phone_number,
            session_name=account.session_name,
        )

        client = None
        try:
            client = await manager.connect(auto_start=False)
            await client.sign_in(password=request.password)
            # Update account as authenticated
            account.is_authenticated = True
            await db.commit()
            return {"success": True, "message": "Account authenticated successfully"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            if client:
                await manager.disconnect()

