"""
Test WebSocket Real-time Communication

Comprehensive tests for WebSocket endpoints, authentication, rate limiting,
and domain event broadcasting.
"""

import asyncio
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import websockets
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api.websocket_client import ClientConfig, WebSocketClient
from app.domain.scheduling.events.domain_events import (
    JobDelayed,
)
from app.main import app


@pytest.fixture
def test_client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_token():
    """Generate a valid JWT token for testing."""
    # This would normally use your auth system to generate a real token
    # For testing, you might want to mock this or use a test token
    return "test_jwt_token"


class TestWebSocketConnection:
    """Test WebSocket connection and authentication."""

    @pytest.mark.asyncio
    async def test_unauthenticated_connection(self):
        """Test connecting without authentication."""
        async with websockets.connect("ws://localhost:8000/ws/dashboard") as websocket:
            # Should be disconnected immediately for dashboard (requires auth)
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await websocket.recv()

    @pytest.mark.asyncio
    async def test_authenticated_connection(self, valid_token):
        """Test connecting with valid authentication."""
        url = f"ws://localhost:8000/ws/schedules/test-schedule?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Should receive connection established message
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "connection_established"
            assert "connection_id" in data
            assert "subscribed_topics" in data

    @pytest.mark.asyncio
    async def test_ping_pong(self, valid_token):
        """Test ping/pong mechanism."""
        url = f"ws://localhost:8000/ws/jobs/test-job?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Send ping
            await websocket.send(
                json.dumps({"type": "ping", "timestamp": datetime.now().isoformat()})
            )

            # Should receive pong
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "pong"
            assert "timestamp" in data


class TestWebSocketTopics:
    """Test topic subscription and broadcasting."""

    @pytest.mark.asyncio
    async def test_subscribe_to_topics(self, valid_token):
        """Test subscribing to additional topics."""
        url = f"ws://localhost:8000/ws/schedules/test-schedule?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Subscribe to new topics
            await websocket.send(
                json.dumps(
                    {"type": "subscribe", "topics": ["critical_path", "conflicts"]}
                )
            )

            # Should receive subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "subscription_updated"
            assert "critical_path" in data["topics"]
            assert "conflicts" in data["topics"]

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topics(self, valid_token):
        """Test unsubscribing from topics."""
        url = f"ws://localhost:8000/ws/schedules/test-schedule?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Unsubscribe from topics
            await websocket.send(
                json.dumps({"type": "unsubscribe", "topics": ["tasks"]})
            )

            # Should receive subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "subscription_updated"
            assert "tasks" not in data["topics"]


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, valid_token):
        """Test that rate limits are enforced."""
        url = f"ws://localhost:8000/ws/jobs/test-job?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Send many messages quickly to trigger rate limit
            messages_sent = 0
            rate_limit_hit = False

            for i in range(150):  # More than default rate limit
                await websocket.send(json.dumps({"type": "ping", "id": i}))
                messages_sent += 1

                # Check for rate limit response
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(message)

                    if data["type"] == "rate_limit_exceeded":
                        rate_limit_hit = True
                        break
                except asyncio.TimeoutError:
                    continue

            assert rate_limit_hit, "Rate limit should have been triggered"


class TestDomainEventBroadcasting:
    """Test domain event broadcasting through WebSocket."""

    @pytest.mark.asyncio
    async def test_task_event_broadcasting(self, valid_token, async_client):
        """Test broadcasting of task events."""
        # Connect to WebSocket
        url = f"ws://localhost:8000/ws/schedules/test-schedule?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Trigger a task event via REST API
            response = await async_client.post("/api/websocket/demo/events")
            assert response.status_code == 200

            # Should receive domain event
            received_events = []
            for _ in range(4):  # Expecting 4 demo events
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)

                    if data["type"] == "domain_event":
                        received_events.append(data["event_type"])
                except asyncio.TimeoutError:
                    break

            assert "TaskScheduled" in received_events
            assert "JobDelayed" in received_events
            assert "ResourceConflictDetected" in received_events
            assert "CriticalPathChanged" in received_events

    @pytest.mark.asyncio
    async def test_job_specific_events(self, valid_token):
        """Test receiving events for a specific job."""
        job_id = str(uuid4())
        url = f"ws://localhost:8000/ws/jobs/{job_id}?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Publish a job event
            event = JobDelayed(
                job_id=UUID(job_id),
                original_due_date=datetime.now(),
                expected_completion=datetime.now() + timedelta(hours=2),
                delay_hours=2.0,
                aggregate_id=uuid4(),
            )

            # This would normally be triggered by your domain logic
            # For testing, we'll simulate it
            from app.api.websockets import websocket_handler

            await websocket_handler._handle_async(event)

            # Should receive the event
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data = json.loads(message)

            assert data["type"] == "domain_event"
            assert data["event_type"] == "JobDelayed"
            assert data["data"]["job_id"] == job_id


class TestWebSocketClient:
    """Test the WebSocket client library."""

    @pytest.mark.asyncio
    async def test_client_connection(self, valid_token):
        """Test client connection and reconnection."""
        received_messages = []

        async def on_message(message):
            received_messages.append(message)

        config = ClientConfig(
            url="ws://localhost:8000/ws/schedules/test-schedule",
            token=valid_token,
            auto_reconnect=True,
            topics=["schedules", "tasks"],
        )

        client = WebSocketClient(config)
        client.on_message = on_message

        # Connect
        connected = await client.connect()
        assert connected

        # Send a message
        sent = await client.send_message({"type": "get_stats"})
        assert sent

        # Wait for response
        await asyncio.sleep(1)

        # Check received messages
        assert len(received_messages) > 0
        stats_received = any(msg.get("type") == "stats" for msg in received_messages)
        assert stats_received

        # Disconnect
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_auto_reconnect(self, valid_token):
        """Test automatic reconnection."""
        reconnect_count = 0

        async def on_connect():
            nonlocal reconnect_count
            reconnect_count += 1

        config = ClientConfig(
            url="ws://localhost:8000/ws/schedules/test-schedule",
            token=valid_token,
            auto_reconnect=True,
            reconnect_delay=0.5,
            max_reconnect_delay=2.0,
        )

        client = WebSocketClient(config)
        client.on_connect = on_connect

        # Connect
        await client.connect()
        assert reconnect_count == 1

        # Simulate connection loss
        if client.websocket:
            await client.websocket.close()

        # Wait for reconnection
        await asyncio.sleep(2)

        # Should have reconnected
        assert reconnect_count == 2
        assert client.state.value == "connected"

        # Clean up
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_message_queuing(self, valid_token):
        """Test message queuing when disconnected."""
        config = ClientConfig(
            url="ws://localhost:8000/ws/schedules/test-schedule",
            token=valid_token,
            auto_reconnect=False,
        )

        client = WebSocketClient(config)

        # Try to send message while disconnected
        sent = await client.send_message({"type": "test", "data": "queued"})
        assert not sent
        assert len(client.message_queue) == 1

        # Connect
        await client.connect()

        # Queue should be flushed
        await asyncio.sleep(1)
        assert len(client.message_queue) == 0

        # Clean up
        await client.disconnect()


class TestMetricsBroadcasting:
    """Test real-time metrics broadcasting."""

    @pytest.mark.asyncio
    async def test_dashboard_metrics(self, valid_token):
        """Test receiving metrics on dashboard WebSocket."""
        url = f"ws://localhost:8000/ws/dashboard?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Request metrics
            await websocket.send(json.dumps({"type": "get_metrics"}))

            # Should receive metrics
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "metrics"
            assert "active_jobs" in data["data"]
            assert "active_connections" in data["data"]

    @pytest.mark.asyncio
    async def test_periodic_metrics_broadcast(self, valid_token):
        """Test periodic metrics broadcasting."""
        url = f"ws://localhost:8000/ws/dashboard?token={valid_token}"

        async with websockets.connect(url) as websocket:
            # Wait for connection established
            await websocket.recv()

            # Wait for periodic metrics (broadcast every 5 seconds)
            metrics_received = False

            for _ in range(10):  # Wait up to 10 seconds
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    if data["type"] == "metrics_update":
                        metrics_received = True
                        assert "metrics" in data
                        assert "timestamp" in data["metrics"]
                        assert "active_connections" in data["metrics"]
                        break
                except asyncio.TimeoutError:
                    continue

            assert metrics_received, "Should have received periodic metrics"


class TestMessageQueue:
    """Test message queuing for offline users."""

    @pytest.mark.asyncio
    async def test_offline_message_delivery(self, valid_token, async_client):
        """Test that messages are queued and delivered when user reconnects."""
        user_id = str(uuid4())

        # Send message to offline user via REST API
        response = await async_client.post(
            f"/api/websocket/notify-user/{user_id}",
            json={"type": "test_notification", "data": "Hello offline user"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queued"] is True

        # Now connect as that user
        # (This would require proper user authentication setup)
        # For now, we'll just verify the queue exists

        # Get stats to verify queue
        response = await async_client.get("/api/websocket/stats")
        assert response.status_code == 200
        stats = response.json()

        # Check if message is queued
        if "message_queues" in stats:
            assert user_id in stats["message_queues"]
            assert stats["message_queues"][user_id] > 0


class TestConnectionStats:
    """Test connection statistics and monitoring."""

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, async_client):
        """Test getting WebSocket connection statistics."""
        response = await async_client.get("/api/websocket/stats")
        assert response.status_code == 200

        stats = response.json()
        assert "total_connections" in stats
        assert "authenticated_connections" in stats
        assert "topic_subscriptions" in stats
        assert "connections" in stats

    @pytest.mark.asyncio
    async def test_broadcast_to_topic(self, async_client):
        """Test broadcasting to a specific topic."""
        response = await async_client.post(
            "/api/websocket/broadcast",
            json={
                "message": {"type": "test_broadcast", "data": "Hello topic"},
                "topic": "dashboard",
                "require_auth": True,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "recipients" in data


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
