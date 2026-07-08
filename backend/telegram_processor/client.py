"""Telegram client manager using Telethon."""

import asyncio
from pathlib import Path

from telethon import TelegramClient

from telegram_processor.config import TELEGRAM_SESSION_PATH


class TelegramClientManager:
    """Manages Telegram client connection and session for multiple accounts."""

    def __init__(self, api_id: int, api_hash: str, phone_number: str, session_name: str) -> None:
        """Initialize the client manager with account credentials.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone_number: Phone number for the account
            session_name: Unique session name for this account
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone_number
        self.session_name = session_name
        self.session_path = TELEGRAM_SESSION_PATH.parent / f"{session_name}.session"
        self._client: TelegramClient | None = None

    @property
    def client(self) -> TelegramClient:
        """Get the connected Telegram client.

        Returns:
            TelegramClient: The connected client.

        Raises:
            RuntimeError: If not connected.
        """
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._client

    async def connect(self, auto_start: bool = True) -> TelegramClient:
        """Connect to Telegram and return the client.

        Args:
            auto_start: If True, verify the session is already authorized and resume it.
                       Raises RuntimeError if the account has not been authenticated yet.
                       If False, just connect without any authentication check
                       (use this for the interactive first-time auth flow).

        Returns:
            TelegramClient: The connected Telegram client.

        Raises:
            ValueError: If required credentials are missing.
            RuntimeError: If auto_start=True but the session is not yet authorized.
        """
        if not self.api_id or not self.api_hash:
            raise ValueError("API ID and API Hash must be provided")

        self.session_path.parent.mkdir(parents=True, exist_ok=True)

        self._client = TelegramClient(
            str(self.session_path),
            self.api_id,
            self.api_hash,
        )

        # Retry logic for SQLite database lock errors
        max_retries = 3
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                await self._client.connect()
                break
            except Exception as e:
                error_str = str(e).lower()
                if 'database is locked' in error_str or 'database is locked' in str(e):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                raise

        if auto_start:
            # BUG FIX: Check if session is already authorized before attempting to start
            # If not authenticated, raise error instead of blocking on input
            if not await self._client.is_user_authorized():
                await self._client.disconnect()
                self._client = None
                raise RuntimeError(
                    f"Telegram account '{self.session_name}' is not authenticated. "
                    "Please complete the authentication flow before using this account."
                )
            # Session is already authorized, connect() is sufficient to resume it
            # No need to call start() which is for first-time authentication

        return self._client

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None