"""Telegram client manager using Telethon."""

from telethon import TelegramClient

from telegram_processor.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_PHONE,
    TELEGRAM_SESSION_PATH,
)


class TelegramClientManager:
    """Manages Telegram client connection and session."""

    def __init__(self) -> None:
        """Initialize the client manager with credentials from environment."""
        self.api_id = TELEGRAM_API_ID
        self.api_hash = TELEGRAM_API_HASH
        self.phone = TELEGRAM_PHONE
        self.session_path = TELEGRAM_SESSION_PATH
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
            raise ValueError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env"
            )

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
