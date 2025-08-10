"""
WebSocket Support for Real-time Schedule Updates

Provides comprehensive WebSocket endpoints for real-time scheduling notifications,
system monitoring, and domain event broadcasting with authentication, rate limiting,
and automatic reconnection support.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from fastapi import Query, WebSocket, WebSocketDisconnect, status
from fastapi.routing import APIRouter
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.observability import (
    ACTIVE_JOBS,
    get_correlation_id,
    get_logger,
)
from app.core.rsa_keys import rsa_key_manager
from app.domain.scheduling.events.domain_events import (
    CriticalPathChanged,
    DomainEvent,
    DomainEventHandler,
    JobDelayed,
    JobStatusChanged,
    MachineStatusChanged,
    OperatorStatusChanged,
    ResourceConflictDetected,
    SchedulePublished,
    ScheduleUpdated,
    TaskCompleted,
    TaskScheduled,
    TaskStarted,
    get_event_dispatcher,
)
from app.models import TokenPayload, User

# Initialize logger
logger = get_logger(__name__)

# WebSocket routers
router = APIRouter(prefix="/ws", tags=["websockets"])
rest_router = APIRouter(prefix="/api/websocket", tags=["websocket-info"])


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    connection_id: str
    user_id: str | None
    user_email: str | None
    connected_at: datetime
    last_activity: datetime
    topics: set[str]
    messages_sent: int
    messages_received: int
    rate_limit_remaining: int
    is_authenticated: bool


@dataclass
class MetricsSnapshot:
    """Real-time metrics snapshot for broadcasting."""

    timestamp: datetime
    active_jobs: int
    completed_tasks: int
    solver_operations: int
    avg_solve_time: float
    system_load: float
    memory_usage: float
    active_connections: int


class RateLimiter:
    """Token bucket rate limiter for WebSocket connections."""

    def __init__(self, rate: int = 100, per: float = 60.0):
        """
        Initialize rate limiter.

        Args:
            rate: Number of allowed messages
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(time.time)

    def is_allowed(self, connection_id: str) -> tuple[bool, int]:
        """
        Check if a connection is allowed to send a message.

        Returns:
            Tuple of (is_allowed, remaining_tokens)
        """
        current = time.time()
        time_passed = current - self.last_check[connection_id]
        self.last_check[connection_id] = current

        # Replenish tokens
        self.allowance[connection_id] += time_passed * (self.rate / self.per)
        if self.allowance[connection_id] > self.rate:
            self.allowance[connection_id] = self.rate

        # Check if allowed
        if self.allowance[connection_id] < 1.0:
            return False, int(self.allowance[connection_id])

        self.allowance[connection_id] -= 1.0
        return True, int(self.allowance[connection_id])


class MessageQueue:
    """Queue for storing messages when clients are offline or disconnected."""

    def __init__(self, max_size: int = 1000):
        """Initialize message queue with maximum size."""
        self.queues: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_size))
        self.max_size = max_size

    def add_message(self, user_id: str, message: dict[str, Any]) -> None:
        """Add a message to a user's queue."""
        self.queues[user_id].append(
            {**message, "queued_at": datetime.now().isoformat()}
        )

    def get_messages(self, user_id: str) -> list[dict[str, Any]]:
        """Get and clear all queued messages for a user."""
        messages = list(self.queues[user_id])
        self.queues[user_id].clear()
        return messages

    def has_messages(self, user_id: str) -> bool:
        """Check if a user has queued messages."""
        return len(self.queues[user_id]) > 0


class WebSocketConnectionManager:
    """Enhanced WebSocket connection manager with authentication and rate limiting."""

    def __init__(self):
        # Active connections by connection ID
        self.active_connections: dict[str, WebSocket] = {}
        # Connection info
        self.connection_info: dict[str, ConnectionInfo] = {}
        # Subscriptions by topic
        self.topic_subscriptions: dict[str, set[str]] = defaultdict(set)
        # User to connection mapping
        self.user_connections: dict[str, set[str]] = defaultdict(set)
        # Rate limiter
        self.rate_limiter = RateLimiter(rate=100, per=60.0)
        # Message queue for offline users
        self.message_queue = MessageQueue(max_size=1000)
        # Connection health check
        self.last_ping: dict[str, datetime] = {}
        # Start periodic tasks
        asyncio.create_task(self._periodic_health_check())
        asyncio.create_task(self._periodic_metrics_broadcast())

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user: User | None = None,
        topics: list[str] | None = None,
    ) -> bool:
        """
        Accept a WebSocket connection with optional authentication.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await websocket.accept()

            # Store connection
            self.active_connections[connection_id] = websocket

            # Create connection info
            info = ConnectionInfo(
                connection_id=connection_id,
                user_id=str(user.id) if user else None,
                user_email=user.email if user else None,
                connected_at=datetime.now(),
                last_activity=datetime.now(),
                topics=set(topics) if topics else set(),
                messages_sent=0,
                messages_received=0,
                rate_limit_remaining=100,
                is_authenticated=user is not None,
            )
            self.connection_info[connection_id] = info

            # Map user to connection
            if user:
                self.user_connections[str(user.id)].add(connection_id)

            # Set up topic subscriptions
            if topics:
                for topic in topics:
                    self.topic_subscriptions[topic].add(connection_id)

            # Send connection confirmation
            await self.send_personal_message(
                connection_id,
                {
                    "type": "connection_established",
                    "connection_id": connection_id,
                    "authenticated": user is not None,
                    "user_email": user.email if user else None,
                    "subscribed_topics": list(topics) if topics else [],
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Send any queued messages
            if user:
                queued_messages = self.message_queue.get_messages(str(user.id))
                if queued_messages:
                    await self.send_personal_message(
                        connection_id,
                        {
                            "type": "queued_messages",
                            "messages": queued_messages,
                            "count": len(queued_messages),
                            "timestamp": datetime.now().isoformat(),
                        },
                    )

            logger.info(
                "WebSocket connection established",
                connection_id=connection_id,
                user_id=str(user.id) if user else None,
                topics=topics,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to establish WebSocket connection",
                connection_id=connection_id,
                error=str(e),
            )
            return False

    def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection and clean up resources."""
        # Get connection info
        info = self.connection_info.get(connection_id)

        # Remove from active connections
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # Remove from topic subscriptions
        for _topic, connections in self.topic_subscriptions.items():
            connections.discard(connection_id)

        # Remove from user connections
        if info and info.user_id:
            self.user_connections[info.user_id].discard(connection_id)
            if not self.user_connections[info.user_id]:
                del self.user_connections[info.user_id]

        # Remove connection info
        if connection_id in self.connection_info:
            del self.connection_info[connection_id]

        # Remove from health check
        if connection_id in self.last_ping:
            del self.last_ping[connection_id]

        logger.info(
            "WebSocket connection closed",
            connection_id=connection_id,
            user_id=info.user_id if info else None,
        )

    async def send_personal_message(
        self, connection_id: str, message: dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific connection.

        Returns:
            True if message sent successfully, False otherwise
        """
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            # Queue message if user is known
            info = self.connection_info.get(connection_id)
            if info and info.user_id:
                self.message_queue.add_message(info.user_id, message)
            return False

        try:
            # Add correlation ID
            message["correlation_id"] = get_correlation_id() or str(uuid4())

            # Send message
            await websocket.send_text(json.dumps(message, default=str))

            # Update connection info
            if connection_id in self.connection_info:
                self.connection_info[connection_id].messages_sent += 1
                self.connection_info[connection_id].last_activity = datetime.now()

            return True

        except Exception as e:
            logger.error(
                "Error sending WebSocket message",
                connection_id=connection_id,
                error=str(e),
            )
            self.disconnect(connection_id)
            return False

    async def broadcast_to_topic(
        self, topic: str, message: dict[str, Any], exclude_connection: str | None = None
    ) -> int:
        """
        Broadcast a message to all connections subscribed to a topic.

        Returns:
            Number of successful sends
        """
        connection_ids = self.topic_subscriptions.get(topic, set()).copy()

        if exclude_connection:
            connection_ids.discard(exclude_connection)

        successful_sends = 0
        for connection_id in connection_ids:
            if await self.send_personal_message(connection_id, message):
                successful_sends += 1

        return successful_sends

    async def broadcast_to_user(self, user_id: str, message: dict[str, Any]) -> int:
        """
        Broadcast a message to all connections for a specific user.

        Returns:
            Number of successful sends
        """
        connection_ids = self.user_connections.get(user_id, set()).copy()

        successful_sends = 0
        for connection_id in connection_ids:
            if await self.send_personal_message(connection_id, message):
                successful_sends += 1

        # Queue message if user has no active connections
        if successful_sends == 0:
            self.message_queue.add_message(user_id, message)

        return successful_sends

    async def broadcast_to_all(
        self, message: dict[str, Any], require_auth: bool = False
    ) -> int:
        """
        Broadcast a message to all active connections.

        Returns:
            Number of successful sends
        """
        successful_sends = 0
        for connection_id in list(self.active_connections.keys()):
            info = self.connection_info.get(connection_id)

            # Skip unauthenticated connections if required
            if require_auth and (not info or not info.is_authenticated):
                continue

            if await self.send_personal_message(connection_id, message):
                successful_sends += 1

        return successful_sends

    def subscribe_to_topic(self, connection_id: str, topic: str) -> None:
        """Subscribe a connection to a topic."""
        self.topic_subscriptions[topic].add(connection_id)
        if connection_id in self.connection_info:
            self.connection_info[connection_id].topics.add(topic)

    def unsubscribe_from_topic(self, connection_id: str, topic: str) -> None:
        """Unsubscribe a connection from a topic."""
        self.topic_subscriptions[topic].discard(connection_id)
        if connection_id in self.connection_info:
            self.connection_info[connection_id].topics.discard(topic)

    def check_rate_limit(self, connection_id: str) -> tuple[bool, int]:
        """
        Check if a connection is within rate limits.

        Returns:
            Tuple of (is_allowed, remaining_tokens)
        """
        allowed, remaining = self.rate_limiter.is_allowed(connection_id)

        if connection_id in self.connection_info:
            self.connection_info[connection_id].rate_limit_remaining = remaining

        return allowed, remaining

    def get_connection_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics about active connections."""
        total_connections = len(self.active_connections)
        authenticated_connections = sum(
            1 for info in self.connection_info.values() if info.is_authenticated
        )

        topic_stats = {
            topic: len(connections)
            for topic, connections in self.topic_subscriptions.items()
        }

        user_stats = {
            user_id: len(connections)
            for user_id, connections in self.user_connections.items()
        }

        return {
            "total_connections": total_connections,
            "authenticated_connections": authenticated_connections,
            "unauthenticated_connections": total_connections
            - authenticated_connections,
            "topic_subscriptions": topic_stats,
            "users_connected": len(user_stats),
            "user_connections": user_stats,
            "message_queues": {
                user_id: len(queue)
                for user_id, queue in self.message_queue.queues.items()
            },
            "connections": [
                {
                    "connection_id": info.connection_id,
                    "user_email": info.user_email,
                    "connected_at": info.connected_at.isoformat(),
                    "last_activity": info.last_activity.isoformat(),
                    "topics": list(info.topics),
                    "messages_sent": info.messages_sent,
                    "messages_received": info.messages_received,
                    "rate_limit_remaining": info.rate_limit_remaining,
                    "is_authenticated": info.is_authenticated,
                }
                for info in self.connection_info.values()
            ],
        }

    async def _periodic_health_check(self) -> None:
        """Periodically check connection health and clean up stale connections."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            current_time = datetime.now()
            stale_connections = []

            for connection_id, last_ping in self.last_ping.items():
                if current_time - last_ping > timedelta(minutes=2):
                    stale_connections.append(connection_id)

            # Send ping to all connections
            for connection_id in list(self.active_connections.keys()):
                await self.send_personal_message(
                    connection_id,
                    {"type": "ping", "timestamp": current_time.isoformat()},
                )

            # Clean up stale connections
            for connection_id in stale_connections:
                logger.warning(
                    "Removing stale WebSocket connection", connection_id=connection_id
                )
                self.disconnect(connection_id)

    async def _periodic_metrics_broadcast(self) -> None:
        """Periodically broadcast system metrics to dashboard subscribers."""
        while True:
            await asyncio.sleep(5)  # Broadcast every 5 seconds

            # Collect metrics
            metrics = MetricsSnapshot(
                timestamp=datetime.now(),
                active_jobs=int(ACTIVE_JOBS._value.get()),
                completed_tasks=0,  # Would need to track this
                solver_operations=0,  # Would need to track this
                avg_solve_time=0.0,  # Would need to calculate this
                system_load=0.0,  # Would need psutil for this
                memory_usage=0.0,  # Would need psutil for this
                active_connections=len(self.active_connections),
            )

            # Broadcast to dashboard topic
            await self.broadcast_to_topic(
                "dashboard", {"type": "metrics_update", "metrics": asdict(metrics)}
            )


# Global connection manager
connection_manager = WebSocketConnectionManager()


class WebSocketEventHandler(DomainEventHandler):
    """Enhanced domain event handler with topic-based broadcasting."""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager
        self.event_count = 0

    def can_handle(self, event: DomainEvent) -> bool:
        """Handle all domain events."""
        return True

    def handle(self, event: DomainEvent) -> None:
        """Handle domain event synchronously (called from sync context)."""
        # Create async task to handle the event
        asyncio.create_task(self._handle_async(event))

    async def _handle_async(self, event: DomainEvent) -> None:
        """Handle domain event by broadcasting to WebSocket subscribers."""
        try:
            self.event_count += 1

            # Determine topics based on event type
            topics = self._get_topics_for_event(event)

            # Create message
            message = {
                "type": "domain_event",
                "event_type": type(event).__name__,
                "event_id": str(event.event_id),
                "occurred_at": event.occurred_at.isoformat(),
                "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
                "event_count": self.event_count,
                "data": self._serialize_event_data(event),
            }

            # Broadcast to relevant topics
            for topic in topics:
                await self.connection_manager.broadcast_to_topic(
                    topic, {**message, "topic": topic}
                )

            # Special handling for critical events
            if isinstance(event, JobDelayed | ResourceConflictDetected):
                # Also broadcast to all authenticated users
                await self.connection_manager.broadcast_to_all(
                    {**message, "priority": "high", "alert": True}, require_auth=True
                )

            logger.debug(
                "Domain event broadcasted",
                event_type=type(event).__name__,
                event_id=str(event.event_id),
                topics=topics,
            )

        except Exception as e:
            logger.error(
                "Error broadcasting domain event",
                event_id=str(event.event_id),
                error=str(e),
            )

    def _get_topics_for_event(self, event: DomainEvent) -> list[str]:
        """Determine the topics for an event."""
        topics = ["all_events"]

        # Add specific topics based on event type
        if isinstance(event, TaskScheduled | TaskStarted | TaskCompleted):
            topics.extend(["tasks", f"task_{event.task_id}", f"job_{event.job_id}"])
        elif isinstance(event, JobDelayed | JobStatusChanged):
            topics.extend(["jobs", f"job_{event.job_id}"])
        elif isinstance(event, ResourceConflictDetected):
            topics.extend(["resources", "conflicts"])
        elif isinstance(event, CriticalPathChanged):
            topics.extend(["critical_path", f"job_{event.job_id}"])
        elif isinstance(event, MachineStatusChanged):
            topics.extend(["machines", f"machine_{event.machine_id}"])
        elif isinstance(event, OperatorStatusChanged):
            topics.extend(["operators", f"operator_{event.operator_id}"])
        elif isinstance(event, SchedulePublished | ScheduleUpdated):
            topics.extend(["schedules", f"schedule_{event.schedule_id}"])
        else:
            topics.append("general")

        return topics

    def _serialize_event_data(self, event: DomainEvent) -> dict[str, Any]:
        """Serialize event data for JSON transmission."""
        data = {}
        for field_name in dir(event):
            if field_name.startswith("_") or field_name in ["can_handle", "handle"]:
                continue

            field_value = getattr(event, field_name)

            if callable(field_value):
                continue

            if isinstance(field_value, UUID):
                data[field_name] = str(field_value)
            elif isinstance(field_value, datetime):
                data[field_name] = field_value.isoformat()
            elif isinstance(field_value, list):
                data[field_name] = [
                    str(item) if isinstance(item, UUID) else item
                    for item in field_value
                ]
            elif hasattr(field_value, "__dict__"):
                # Handle value objects
                data[field_name] = str(field_value)
            else:
                data[field_name] = field_value

        return data


# Register the WebSocket event handler
websocket_handler = WebSocketEventHandler(connection_manager)
get_event_dispatcher().register_handler(websocket_handler)


# Authentication helper
async def authenticate_websocket(token: str | None = None) -> User | None:
    """
    Authenticate a WebSocket connection using JWT token.

    Args:
        token: JWT access token

    Returns:
        User object if authenticated, None otherwise
    """
    if not token:
        return None

    try:
        # Get public keys for verification
        keys_to_try = []
        if security.ALGORITHM == "RS256":
            keys_to_try = rsa_key_manager.get_public_keys_for_verification()
        else:
            keys_to_try = [settings.SECRET_KEY]

        payload = None
        for key in keys_to_try:
            try:
                payload = jwt.decode(token, key, algorithms=[security.ALGORITHM])
                break
            except jwt.InvalidTokenError:
                continue

        if not payload or payload.get("type") != "access":
            return None

        token_data = TokenPayload(**payload)

        # Get user from database
        with Session(engine) as session:
            user = session.get(User, token_data.sub)
            if user and user.is_active:
                return user

    except Exception as e:
        logger.warning("WebSocket authentication failed", error=str(e))

    return None


# WebSocket Endpoints


@router.websocket("/schedules/{schedule_id}")
async def websocket_schedule(
    websocket: WebSocket, schedule_id: str, token: str | None = Query(None)
):
    """
    WebSocket endpoint for real-time schedule updates.

    Subscribes to events related to a specific schedule.
    """
    connection_id = f"schedule_{schedule_id}_{datetime.now().timestamp()}"

    # Authenticate
    user = await authenticate_websocket(token)

    # Set up topics
    topics = [f"schedule_{schedule_id}", "schedules", "tasks", "jobs", "resources"]

    # Connect
    if not await connection_manager.connect(websocket, connection_id, user, topics):
        await websocket.close()
        return

    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_text()

            # Check rate limit
            allowed, remaining = connection_manager.check_rate_limit(connection_id)
            if not allowed:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "rate_limit_exceeded",
                        "remaining": remaining,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                continue

            # Update activity
            if connection_id in connection_manager.connection_info:
                connection_manager.connection_info[connection_id].messages_received += 1

            # Handle message
            try:
                message = json.loads(data)
                await handle_client_message(connection_id, message)
            except json.JSONDecodeError:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": datetime.now().isoformat(),
                    },
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)


@router.websocket("/jobs/{job_id}")
async def websocket_job(
    websocket: WebSocket, job_id: str, token: str | None = Query(None)
):
    """
    WebSocket endpoint for job progress notifications.

    Subscribes to events related to a specific job.
    """
    connection_id = f"job_{job_id}_{datetime.now().timestamp()}"

    # Authenticate
    user = await authenticate_websocket(token)

    # Set up topics
    topics = [f"job_{job_id}", "jobs", "tasks", "critical_path"]

    # Connect
    if not await connection_manager.connect(websocket, connection_id, user, topics):
        await websocket.close()
        return

    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_text()

            # Check rate limit
            allowed, remaining = connection_manager.check_rate_limit(connection_id)
            if not allowed:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "rate_limit_exceeded",
                        "remaining": remaining,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                continue

            # Handle message
            try:
                message = json.loads(data)
                await handle_client_message(connection_id, message)
            except json.JSONDecodeError:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": datetime.now().isoformat(),
                    },
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)


@router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str | None = Query(None)):
    """
    WebSocket endpoint for overall system status dashboard.

    Provides real-time metrics, alerts, and system-wide events.
    """
    connection_id = f"dashboard_{datetime.now().timestamp()}"

    # Authenticate (dashboard requires authentication)
    user = await authenticate_websocket(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Set up topics for dashboard
    topics = ["dashboard", "all_events", "critical_path", "conflicts", "alerts"]

    # Connect
    if not await connection_manager.connect(websocket, connection_id, user, topics):
        await websocket.close()
        return

    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_text()

            # Check rate limit
            allowed, remaining = connection_manager.check_rate_limit(connection_id)
            if not allowed:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "rate_limit_exceeded",
                        "remaining": remaining,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                continue

            # Handle message
            try:
                message = json.loads(data)
                await handle_client_message(connection_id, message)
            except json.JSONDecodeError:
                await connection_manager.send_personal_message(
                    connection_id,
                    {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": datetime.now().isoformat(),
                    },
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)


async def handle_client_message(connection_id: str, message: dict[str, Any]) -> None:
    """Handle messages from WebSocket clients."""
    message_type = message.get("type")

    if message_type == "ping":
        # Update last ping time
        connection_manager.last_ping[connection_id] = datetime.now()
        await connection_manager.send_personal_message(
            connection_id, {"type": "pong", "timestamp": datetime.now().isoformat()}
        )

    elif message_type == "subscribe":
        # Handle dynamic subscription changes
        topics = message.get("topics", [])
        for topic in topics:
            connection_manager.subscribe_to_topic(connection_id, topic)

        await connection_manager.send_personal_message(
            connection_id,
            {
                "type": "subscription_updated",
                "topics": list(
                    connection_manager.connection_info[connection_id].topics
                ),
                "timestamp": datetime.now().isoformat(),
            },
        )

    elif message_type == "unsubscribe":
        # Handle unsubscription
        topics = message.get("topics", [])
        for topic in topics:
            connection_manager.unsubscribe_from_topic(connection_id, topic)

        await connection_manager.send_personal_message(
            connection_id,
            {
                "type": "subscription_updated",
                "topics": list(
                    connection_manager.connection_info[connection_id].topics
                ),
                "timestamp": datetime.now().isoformat(),
            },
        )

    elif message_type == "get_stats":
        # Get connection statistics
        stats = connection_manager.get_connection_stats()
        await connection_manager.send_personal_message(
            connection_id,
            {"type": "stats", "data": stats, "timestamp": datetime.now().isoformat()},
        )

    elif message_type == "get_metrics":
        # Get system metrics
        metrics = {
            "active_jobs": int(ACTIVE_JOBS._value.get()),
            "active_connections": len(connection_manager.active_connections),
            "timestamp": datetime.now().isoformat(),
        }
        await connection_manager.send_personal_message(
            connection_id,
            {
                "type": "metrics",
                "data": metrics,
                "timestamp": datetime.now().isoformat(),
            },
        )

    else:
        await connection_manager.send_personal_message(
            connection_id,
            {
                "type": "error",
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.now().isoformat(),
            },
        )


# REST API Endpoints for WebSocket Management


@rest_router.get("/stats")
async def get_websocket_stats():
    """Get comprehensive WebSocket connection statistics."""
    return connection_manager.get_connection_stats()


@rest_router.post("/broadcast")
async def broadcast_message(
    message: dict[str, Any], topic: str | None = None, require_auth: bool = True
):
    """
    Broadcast a message to WebSocket clients.

    Args:
        message: Message to broadcast
        topic: Optional topic to broadcast to
        require_auth: Whether to require authenticated connections
    """
    if topic:
        count = await connection_manager.broadcast_to_topic(topic, message)
        return {
            "success": True,
            "topic": topic,
            "recipients": count,
            "timestamp": datetime.now().isoformat(),
        }
    else:
        count = await connection_manager.broadcast_to_all(message, require_auth)
        return {
            "success": True,
            "recipients": count,
            "timestamp": datetime.now().isoformat(),
        }


@rest_router.post("/notify-user/{user_id}")
async def notify_user(user_id: str, message: dict[str, Any]):
    """
    Send a notification to a specific user.

    Message will be queued if user is offline.
    """
    count = await connection_manager.broadcast_to_user(user_id, message)
    return {
        "success": True,
        "user_id": user_id,
        "connections_notified": count,
        "queued": count == 0,
        "timestamp": datetime.now().isoformat(),
    }


# Demo/Testing Endpoints


@rest_router.post("/demo/events")
async def trigger_demo_events():
    """Trigger various demo events for testing WebSocket functionality."""
    from decimal import Decimal

    from app.domain.scheduling.events.domain_events import (
        CriticalPathChanged,
        JobDelayed,
        ResourceConflictDetected,
        TaskScheduled,
    )

    events_triggered = []

    # Task scheduled event
    task_event = TaskScheduled(
        task_id=uuid4(),
        job_id=uuid4(),
        machine_id=uuid4(),
        operator_ids=[uuid4(), uuid4()],
        planned_start=datetime.now(),
        planned_end=datetime.now() + timedelta(hours=2),
        aggregate_id=uuid4(),
    )
    await websocket_handler._handle_async(task_event)
    events_triggered.append("TaskScheduled")

    # Job delayed event
    job_delay = JobDelayed(
        job_id=uuid4(),
        original_due_date=datetime.now(),
        expected_completion=datetime.now() + timedelta(hours=4),
        delay_hours=Decimal("4.0"),
        aggregate_id=uuid4(),
    )
    await websocket_handler._handle_async(job_delay)
    events_triggered.append("JobDelayed")

    # Resource conflict event
    conflict_event = ResourceConflictDetected(
        resource_type="machine",
        resource_id=uuid4(),
        conflicting_tasks=[uuid4(), uuid4()],
        conflict_time_start=datetime.now(),
        conflict_time_end=datetime.now() + timedelta(hours=1),
        aggregate_id=uuid4(),
    )
    await websocket_handler._handle_async(conflict_event)
    events_triggered.append("ResourceConflictDetected")

    # Critical path changed event
    critical_path = CriticalPathChanged(
        job_id=uuid4(),
        old_critical_tasks=[uuid4(), uuid4()],
        new_critical_tasks=[uuid4(), uuid4(), uuid4()],
        new_makespan_hours=Decimal("24.5"),
        aggregate_id=uuid4(),
    )
    await websocket_handler._handle_async(critical_path)
    events_triggered.append("CriticalPathChanged")

    return {
        "success": True,
        "events_triggered": events_triggered,
        "timestamp": datetime.now().isoformat(),
    }
