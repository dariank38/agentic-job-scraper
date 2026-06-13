"""Real-time Telegram message listener using Telethon events."""

import asyncio
import logging
from typing import Callable, Optional
from telethon import events
from telethon.tl.types import Channel as TelegramChannel

from telegram_processor.client import TelegramClientManager

logger = logging.getLogger(__name__)


class TelegramMessageListener:
    """Listens for new messages in specified Telegram channels in real-time."""

    def __init__(self, client_manager: TelegramClientManager):
        """Initialize the listener with a Telegram client manager.
        
        Args:
            client_manager: Connected TelegramClientManager instance
        """
        self.client_manager = client_manager
        self._running = False
        self._handler = None
        self._channel_entities = []
        self._on_new_message_callback = None
        self._allowed_categories = None

    async def start(
        self,
        channel_usernames: list[str],
        on_new_message: Callable,
        allowed_categories: Optional[list[str]] = None
    ) -> None:
        """Start listening for new messages in the specified channels.
        
        Args:
            channel_usernames: List of channel usernames to monitor (e.g., ['@channel1', 'channel2'])
            on_new_message: Async callback function called when a new message is received.
                          Signature: async def callback(event, message_data)
            allowed_categories: Optional list of message categories to process.
                              If None, all messages are processed.
        """
        if self._running:
            logger.warning("Listener is already running")
            return

        self._running = True
        self._on_new_message_callback = on_new_message
        self._allowed_categories = allowed_categories
        client = self.client_manager.client

        # Resolve channel usernames to entity IDs
        self._channel_entities = []
        for username in channel_usernames:
            try:
                # Remove @ if present
                clean_username = username.lstrip('@')
                entity = await client.get_entity(clean_username)
                self._channel_entities.append(entity)
                logger.info(f"Listening to channel: {entity.title or clean_username}")
            except Exception as e:
                logger.error(f"Failed to get entity for {username}: {e}")

        if not self._channel_entities:
            logger.error("No valid channels to listen to")
            self._running = False
            return

        # Define the event handler
        @client.on(events.NewMessage(chats=self._channel_entities))
        async def handle_new_message(event):
            try:
                message = event.message
                
                # Extract message data
                message_data = {
                    'id': message.id,
                    'text': message.text or '',
                    'date': message.date,
                    'sender_id': message.sender_id,
                    'sender_username': None,
                    'sender_first_name': None,
                    'has_media': bool(message.media),
                    'channel_id': event.chat_id,
                    'channel_username': None,
                }

                # Get sender info
                if message.sender:
                    try:
                        sender = await client.get_entity(message.sender)
                        message_data['sender_username'] = getattr(sender, 'username', None)
                        message_data['sender_first_name'] = getattr(sender, 'first_name', None)
                    except Exception:
                        pass

                # Get channel info
                if event.chat:
                    try:
                        chat = await client.get_entity(event.chat)
                        message_data['channel_username'] = getattr(chat, 'username', None)
                    except Exception:
                        pass

                logger.info(f"New message from {message_data['channel_username'] or 'unknown'}: {message_data['text'][:50]}...")
                
                # Call the callback
                if self._on_new_message_callback:
                    await self._on_new_message_callback(event, message_data)
                
            except Exception as e:
                logger.error(f"Error handling new message: {e}", exc_info=True)

        self._handler = handle_new_message
        logger.info(f"Started listening to {len(self._channel_entities)} channels")

    async def stop(self) -> None:
        """Stop listening for new messages."""
        if not self._running:
            return

        client = self.client_manager.client
        if self._handler:
            client.remove_event_handler(self._handler)
            self._handler = None

        self._running = False
        self._channel_entities = []

        # Disconnect the Telegram client to properly close connections
        try:
            await self.client_manager.disconnect()
            logger.info("Stopped listening to channels and disconnected client")
        except Exception as e:
            logger.error(f"Error disconnecting Telegram client: {e}")

    async def add_channels(self, channel_usernames: list[str]) -> None:
        """Add channels to the running listener.
        
        Args:
            channel_usernames: List of channel usernames to add (e.g., ['@channel1', 'channel2'])
        """
        if not self._running:
            logger.warning("Listener is not running, cannot add channels")
            return

        client = self.client_manager.client
        
        # Remove old handler
        if self._handler:
            client.remove_event_handler(self._handler)
        
        # Resolve new channel usernames to entity IDs
        for username in channel_usernames:
            try:
                clean_username = username.lstrip('@')
                entity = await client.get_entity(clean_username)
                # Check if already in list
                if not any(e.id == entity.id for e in self._channel_entities):
                    self._channel_entities.append(entity)
                    logger.info(f"Added channel to listener: {entity.title or clean_username}")
            except Exception as e:
                logger.error(f"Failed to get entity for {username}: {e}")

        # Re-register handler with updated channel list
        @client.on(events.NewMessage(chats=self._channel_entities))
        async def handle_new_message(event):
            try:
                message = event.message
                
                message_data = {
                    'id': message.id,
                    'text': message.text or '',
                    'date': message.date,
                    'sender_id': message.sender_id,
                    'sender_username': None,
                    'sender_first_name': None,
                    'has_media': bool(message.media),
                    'channel_id': event.chat_id,
                    'channel_username': None,
                }

                if message.sender:
                    try:
                        sender = await client.get_entity(message.sender)
                        message_data['sender_username'] = getattr(sender, 'username', None)
                        message_data['sender_first_name'] = getattr(sender, 'first_name', None)
                    except Exception:
                        pass

                if event.chat:
                    try:
                        chat = await client.get_entity(event.chat)
                        message_data['channel_username'] = getattr(chat, 'username', None)
                    except Exception:
                        pass

                logger.info(f"New message from {message_data['channel_username'] or 'unknown'}: {message_data['text'][:50]}...")
                
                if self._on_new_message_callback:
                    await self._on_new_message_callback(event, message_data)
                
            except Exception as e:
                logger.error(f"Error handling new message: {e}", exc_info=True)

        self._handler = handle_new_message
        logger.info(f"Updated listener to {len(self._channel_entities)} channels")

    async def remove_channels(self, channel_usernames: list[str]) -> None:
        """Remove channels from the running listener.
        
        Args:
            channel_usernames: List of channel usernames to remove (e.g., ['@channel1', 'channel2'])
        """
        if not self._running:
            logger.warning("Listener is not running, cannot remove channels")
            return

        client = self.client_manager.client
        
        # Remove old handler
        if self._handler:
            client.remove_event_handler(self._handler)
        
        # Remove channels from list
        for username in channel_usernames:
            clean_username = username.lstrip('@')
            try:
                entity = await client.get_entity(clean_username)
                self._channel_entities = [e for e in self._channel_entities if e.id != entity.id]
                logger.info(f"Removed channel from listener: {entity.title or clean_username}")
            except Exception as e:
                logger.error(f"Failed to get entity for {username}: {e}")

        # Re-register handler with updated channel list
        if self._channel_entities:
            @client.on(events.NewMessage(chats=self._channel_entities))
            async def handle_new_message(event):
                try:
                    message = event.message
                    
                    message_data = {
                        'id': message.id,
                        'text': message.text or '',
                        'date': message.date,
                        'sender_id': message.sender_id,
                        'sender_username': None,
                        'sender_first_name': None,
                        'has_media': bool(message.media),
                        'channel_id': event.chat_id,
                        'channel_username': None,
                    }

                    if message.sender:
                        try:
                            sender = await client.get_entity(message.sender)
                            message_data['sender_username'] = getattr(sender, 'username', None)
                            message_data['sender_first_name'] = getattr(sender, 'first_name', None)
                        except Exception:
                            pass

                    if event.chat:
                        try:
                            chat = await client.get_entity(event.chat)
                            message_data['channel_username'] = getattr(chat, 'username', None)
                        except Exception:
                            pass

                    logger.info(f"New message from {message_data['channel_username'] or 'unknown'}: {message_data['text'][:50]}...")
                    
                    if self._on_new_message_callback:
                        await self._on_new_message_callback(event, message_data)
                    
                except Exception as e:
                    logger.error(f"Error handling new message: {e}", exc_info=True)

            self._handler = handle_new_message
            logger.info(f"Updated listener to {len(self._channel_entities)} channels")
        else:
            self._handler = None
            self._running = False
            logger.info("No channels left, listener stopped")

    @property
    def is_running(self) -> bool:
        """Check if the listener is currently running."""
        return self._running

    @property
    def listened_channels(self) -> list[str]:
        """Get list of currently listened channel usernames."""
        usernames = []
        for entity in self._channel_entities:
            username = getattr(entity, 'username', None)
            if username:
                usernames.append(username)
        return usernames


# Example usage
async def example_usage():
    """Example of how to use the TelegramMessageListener."""
    from telegram_processor.client import TelegramClientManager
    from telegram_processor.config import TELEGRAM_API_ID, TELEGRAM_API_HASH
    
    # Initialize client manager
    manager = TelegramClientManager(
        api_id=TELEGRAM_API_ID,
        api_hash=TELEGRAM_API_HASH,
        phone_number="+1234567890",
        session_name="listener_session"
    )
    
    await manager.connect()
    
    # Create listener
    listener = TelegramMessageListener(manager)
    
    # Define callback for new messages
    async def on_new_message(event, message_data):
        print(f"New message received: {message_data['text'][:100]}...")
        # Here you could:
        # 1. Save the message to database
        # 2. Trigger analysis
        # 3. Send notification via WebSocket
    
    # Start listening to specific channels
    await listener.start(
        channel_usernames=['@channel1', '@channel2'],
        on_new_message=on_new_message
    )
    
    # Keep running
    try:
        while listener.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await listener.stop()
        await manager.disconnect()
