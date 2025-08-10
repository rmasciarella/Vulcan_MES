"""
WebSocket Client Library

Provides a robust WebSocket client with automatic reconnection,
message queuing, and error handling for real-time schedule updates.
"""

import asyncio
import json
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


@dataclass
class ClientConfig:
    """WebSocket client configuration."""

    url: str
    token: str | None = None
    auto_reconnect: bool = True
    reconnect_delay: float = 1.0
    max_reconnect_delay: float = 30.0
    reconnect_decay: float = 1.5
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    max_queue_size: int = 1000
    topics: list[str] = field(default_factory=list)


class ReconnectionStrategy:
    """Exponential backoff reconnection strategy."""

    def __init__(
        self, initial_delay: float = 1.0, max_delay: float = 30.0, decay: float = 1.5
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.decay = decay
        self.current_delay = initial_delay
        self.attempts = 0

    def get_next_delay(self) -> float:
        """Get the next reconnection delay."""
        delay = min(self.current_delay, self.max_delay)
        self.current_delay *= self.decay
        self.attempts += 1
        return delay

    def reset(self) -> None:
        """Reset the reconnection strategy."""
        self.current_delay = self.initial_delay
        self.attempts = 0


class WebSocketClient:
    """
    Robust WebSocket client with automatic reconnection and message handling.

    Example usage:
        ```python
        async def on_message(message):
            print(f"Received: {message}")

        async def on_event(event_type, data):
            print(f"Event {event_type}: {data}")

        config = ClientConfig(
            url="ws://localhost:8000/ws/dashboard",
            token="your_jwt_token",
            topics=["dashboard", "alerts"]
        )

        client = WebSocketClient(config)
        client.on_message = on_message
        client.on_domain_event = on_event

        await client.connect()
        await client.send_message({"type": "ping"})
        ```
    """

    def __init__(self, config: ClientConfig):
        self.config = config
        self.websocket: websockets.WebSocketClientProtocol | None = None
        self.state = ConnectionState.DISCONNECTED
        self.reconnection_strategy = ReconnectionStrategy(
            config.reconnect_delay, config.max_reconnect_delay, config.reconnect_decay
        )

        # Message queue for offline sending
        self.message_queue: deque = deque(maxlen=config.max_queue_size)

        # Subscribed topics
        self.subscribed_topics: set[str] = set(config.topics)

        # Callbacks
        self.on_connect: Callable | None = None
        self.on_disconnect: Callable | None = None
        self.on_message: Callable | None = None
        self.on_error: Callable | None = None
        self.on_domain_event: Callable | None = None
        self.on_metrics_update: Callable | None = None

        # Tasks
        self._receive_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None

        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.connected_at: datetime | None = None
        self.last_ping: datetime | None = None
        self.last_pong: datetime | None = None

    async def connect(self) -> bool:
        """
        Connect to the WebSocket server.

        Returns:
            True if connection successful, False otherwise
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected")
            return True

        self.state = ConnectionState.CONNECTING

        try:
            # Build connection URL with token
            url = self.config.url
            if self.config.token:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}token={self.config.token}"

            # Connect to WebSocket
            self.websocket = await websockets.connect(
                url,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
            )

            self.state = ConnectionState.CONNECTED
            self.connected_at = datetime.now()
            self.reconnection_strategy.reset()

            # Start receive and ping tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._ping_task = asyncio.create_task(self._ping_loop())

            # Send any queued messages
            await self._flush_message_queue()

            # Subscribe to topics
            if self.subscribed_topics:
                await self.subscribe(list(self.subscribed_topics))

            # Call connect callback
            if self.on_connect:
                await self._safe_callback(self.on_connect)

            logger.info(f"Connected to {self.config.url}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.state = ConnectionState.DISCONNECTED

            if self.on_error:
                await self._safe_callback(self.on_error, e)

            # Start reconnection if enabled
            if self.config.auto_reconnect:
                await self._schedule_reconnect()

            return False

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self.state = ConnectionState.CLOSED

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()

        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # Call disconnect callback
        if self.on_disconnect:
            await self._safe_callback(self.on_disconnect)

        logger.info("Disconnected from WebSocket")

    async def send_message(self, message: dict[str, Any]) -> bool:
        """
        Send a message to the server.

        Args:
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if self.state != ConnectionState.CONNECTED:
            # Queue message if not connected
            self.message_queue.append(message)
            logger.debug(f"Message queued (not connected): {message.get('type')}")
            return False

        try:
            await self.websocket.send(json.dumps(message))
            self.messages_sent += 1
            logger.debug(f"Message sent: {message.get('type')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")

            # Queue message for retry
            self.message_queue.append(message)

            # Trigger reconnection
            if self.config.auto_reconnect:
                await self._handle_connection_lost()

            return False

    async def ping(self) -> bool:
        """Send a ping message to the server."""
        return await self.send_message(
            {"type": "ping", "timestamp": datetime.now().isoformat()}
        )

    async def subscribe(self, topics: list[str]) -> bool:
        """
        Subscribe to topics.

        Args:
            topics: List of topics to subscribe to
        """
        self.subscribed_topics.update(topics)

        return await self.send_message(
            {
                "type": "subscribe",
                "topics": topics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def unsubscribe(self, topics: list[str]) -> bool:
        """
        Unsubscribe from topics.

        Args:
            topics: List of topics to unsubscribe from
        """
        for topic in topics:
            self.subscribed_topics.discard(topic)

        return await self.send_message(
            {
                "type": "unsubscribe",
                "topics": topics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def get_stats(self) -> bool:
        """Request connection statistics from the server."""
        return await self.send_message(
            {"type": "get_stats", "timestamp": datetime.now().isoformat()}
        )

    async def get_metrics(self) -> bool:
        """Request system metrics from the server."""
        return await self.send_message(
            {"type": "get_metrics", "timestamp": datetime.now().isoformat()}
        )

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the current connection."""
        return {
            "state": self.state.value,
            "connected_at": self.connected_at.isoformat()
            if self.connected_at
            else None,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "queued_messages": len(self.message_queue),
            "subscribed_topics": list(self.subscribed_topics),
            "reconnect_attempts": self.reconnection_strategy.attempts,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "last_pong": self.last_pong.isoformat() if self.last_pong else None,
        }

    async def _receive_loop(self) -> None:
        """Receive messages from the server."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.messages_received += 1
                    await self._handle_message(data)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    if self.on_error:
                        await self._safe_callback(self.on_error, e)

        except WebSocketException as e:
            logger.error(f"WebSocket error in receive loop: {e}")
            await self._handle_connection_lost()

        except Exception as e:
            logger.error(f"Unexpected error in receive loop: {e}")
            await self._handle_connection_lost()

    async def _ping_loop(self) -> None:
        """Send periodic ping messages."""
        while self.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self.config.ping_interval)

                # Check if we received a pong recently
                if self.last_pong and self.last_ping:
                    time_since_pong = datetime.now() - self.last_pong
                    if time_since_pong > timedelta(
                        seconds=self.config.ping_timeout * 2
                    ):
                        logger.warning("No pong received, connection may be dead")
                        await self._handle_connection_lost()
                        break

                # Send ping
                self.last_ping = datetime.now()
                await self.ping()

            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
                break

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle a received message."""
        message_type = message.get("type")

        # Handle specific message types
        if message_type == "pong":
            self.last_pong = datetime.now()

        elif message_type == "connection_established":
            logger.info(f"Connection established: {message}")

        elif message_type == "domain_event":
            # Handle domain events
            if self.on_domain_event:
                event_type = message.get("event_type")
                data = message.get("data", {})
                await self._safe_callback(self.on_domain_event, event_type, data)

        elif message_type == "metrics_update":
            # Handle metrics updates
            if self.on_metrics_update:
                metrics = message.get("metrics", {})
                await self._safe_callback(self.on_metrics_update, metrics)

        elif message_type == "queued_messages":
            # Handle queued messages from server
            messages = message.get("messages", [])
            logger.info(f"Received {len(messages)} queued messages")
            for msg in messages:
                await self._handle_message(msg)

        elif message_type == "error":
            error_msg = message.get("message", "Unknown error")
            logger.error(f"Server error: {error_msg}")
            if self.on_error:
                await self._safe_callback(self.on_error, error_msg)

        elif message_type == "rate_limit_exceeded":
            remaining = message.get("remaining", 0)
            logger.warning(f"Rate limit exceeded, remaining: {remaining}")

        # Call general message callback
        if self.on_message:
            await self._safe_callback(self.on_message, message)

    async def _handle_connection_lost(self) -> None:
        """Handle lost connection."""
        if self.state == ConnectionState.CLOSED:
            return

        self.state = ConnectionState.DISCONNECTED
        self.websocket = None

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()

        # Call disconnect callback
        if self.on_disconnect:
            await self._safe_callback(self.on_disconnect)

        # Schedule reconnection
        if self.config.auto_reconnect:
            await self._schedule_reconnect()

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the server."""
        self.state = ConnectionState.RECONNECTING

        while self.state == ConnectionState.RECONNECTING:
            delay = self.reconnection_strategy.get_next_delay()
            logger.info(
                f"Reconnecting in {delay} seconds (attempt {self.reconnection_strategy.attempts})"
            )

            await asyncio.sleep(delay)

            if self.state != ConnectionState.RECONNECTING:
                break

            if await self.connect():
                logger.info("Reconnection successful")
                break

    async def _flush_message_queue(self) -> None:
        """Send all queued messages."""
        messages_to_send = list(self.message_queue)
        self.message_queue.clear()

        for message in messages_to_send:
            await self.send_message(message)

    async def _safe_callback(self, callback: Callable, *args, **kwargs) -> None:
        """Safely execute a callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}")


# Example usage and testing
async def example_usage():
    """Example of using the WebSocket client."""

    # Message handlers
    async def on_connect():
        print("Connected to WebSocket server!")

    async def on_disconnect():
        print("Disconnected from WebSocket server!")

    async def on_message(message):
        print(f"Received message: {message}")

    async def on_domain_event(event_type, data):
        print(f"Domain event - {event_type}: {data}")

    async def on_metrics(metrics):
        print(f"Metrics update: {metrics}")

    async def on_error(error):
        print(f"Error: {error}")

    # Create client configuration
    config = ClientConfig(
        url="ws://localhost:8000/ws/dashboard",
        token="your_jwt_token_here",
        auto_reconnect=True,
        reconnect_delay=1.0,
        max_reconnect_delay=30.0,
        topics=["dashboard", "all_events", "alerts"],
    )

    # Create client
    client = WebSocketClient(config)

    # Set callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_domain_event = on_domain_event
    client.on_metrics_update = on_metrics
    client.on_error = on_error

    # Connect
    await client.connect()

    # Send some messages
    await client.get_stats()
    await client.get_metrics()

    # Subscribe to additional topics
    await client.subscribe(["jobs", "tasks"])

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
            print(f"Connection info: {client.get_connection_info()}")
    except KeyboardInterrupt:
        print("Shutting down...")
        await client.disconnect()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
