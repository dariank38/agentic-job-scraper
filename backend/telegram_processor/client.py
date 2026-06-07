"""Telegram client manager using Telethon."""

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

    async def connect(self) -> TelegramClient:
        """Connect to Telegram and return the client.

        Returns:
            TelegramClient: The connected Telegram client.

        Raises:
            ValueError: If required credentials are missing.
        """
        if not self.api_id or not self.api_hash:
            raise ValueError("API ID and API Hash must be provided")

        self.session_path.parent.mkdir(parents=True, exist_ok=True)

        self._client = TelegramClient(
            str(self.session_path),
            self.api_id,
            self.api_hash,
        )

        await self._client.start(phone=self.phone)
        return self._client

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                print(f"[Telegram] Warning: disconnect error (ignored): {e}")
            finally:
                self._client = None
