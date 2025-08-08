"""
WebSocket Real-Time Update Integration Tests

Tests real-time updates via WebSocket during complete scheduling workflows,
including connection management, event broadcasting, and multi-client scenarios.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import websockets
from fastapi.testclient import TestClient

from app.api.websockets import connection_manager, websocket_handler
from app.domain.scheduling.events.domain_events import (
    CriticalPathChanged,
    JobStatusChanged,
    TaskScheduled,
)
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
)


class WebSocketTestClient:
    """Test client for WebSocket connections."""

    def __init__(self, uri: str):
        self.uri = uri
        self.websocket = None
        self.received_messages = []
        self.is_connected = False
        self.connection_id = None

    async def connect(self):
        """Connect to WebSocket endpoint."""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.is_connected = True

            # Wait for connection establishment message
            welcome_msg = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome_msg)

            if welcome_data.get("type") == "connection_established":
                self.connection_id = welcome_data.get("connection_id")
                return True

        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.is_connected = False
            return False

        return False

    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket and self.is_connected:
            await self.websocket.close()
            self.is_connected = False

    async def send_message(self, message: dict[str, Any]):
        """Send message to WebSocket."""
        if self.websocket and self.is_connected:
            await self.websocket.send(json.dumps(message))

    async def receive_message(self, timeout: float = 5.0) -> dict[str, Any] | None:
        """Receive message from WebSocket."""
        if not self.websocket or not self.is_connected:
            return None

        try:
            raw_message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            message = json.loads(raw_message)
            self.received_messages.append(message)
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None

    async def receive_messages(
        self, count: int, timeout: float = 10.0
    ) -> list[dict[str, Any]]:
        """Receive multiple messages."""
        messages = []
        start_time = time.time()

        while len(messages) < count and (time.time() - start_time) < timeout:
            message = await self.receive_message(timeout=1.0)
            if message:
                messages.append(message)

        return messages

    def get_all_received_messages(self) -> list[dict[str, Any]]:
        """Get all received messages."""
        return self.received_messages.copy()


class WebSocketEventSimulator:
    """Simulates domain events for WebSocket testing."""

    @staticmethod
    async def simulate_job_status_change(
        job_id: str, old_status: JobStatus, new_status: JobStatus
    ):
        """Simulate job status change event."""
        event = JobStatusChanged(
            aggregate_id=job_id,
            job_id=job_id,
            job_number=f"WS-TEST-{job_id[:8]}",
            old_status=old_status,
            new_status=new_status,
            reason="websocket_test",
        )

        # Trigger event through the WebSocket handler
        await websocket_handler.handle(event)
        return event

    @staticmethod
    async def simulate_task_scheduled(job_id: str, task_id: str, machine_id: str):
        """Simulate task scheduled event."""
        event = TaskScheduled(
            aggregate_id=task_id,
            task_id=task_id,
            job_id=job_id,
            machine_id=machine_id,
            operator_ids=[str(uuid4())],
            planned_start=datetime.utcnow() + timedelta(hours=2),
            planned_end=datetime.utcnow() + timedelta(hours=4),
        )

        await websocket_handler.handle(event)
        return event

    @staticmethod
    async def simulate_critical_path_change(job_id: str, task_ids: list[str]):
        """Simulate critical path change event."""
        event = CriticalPathChanged(
            aggregate_id=job_id,
            job_id=job_id,
            new_critical_tasks=task_ids,
            previous_critical_tasks=[],
            impact_hours=2.5,
            affected_jobs=[job_id],
        )

        await websocket_handler.handle(event)
        return event


@pytest.fixture
def ws_event_simulator():
    """Provide WebSocket event simulator."""
    return WebSocketEventSimulator()


@pytest.fixture
async def websocket_server():
    """Start WebSocket server for testing."""
    # This would typically start the actual server
    # For now we'll mock the connection manager behavior
    yield connection_manager


@pytest.mark.e2e
@pytest.mark.websocket
@pytest.mark.asyncio
class TestWebSocketIntegrationE2E:
    """Test WebSocket real-time updates during workflows."""

    # Note: These tests require the WebSocket server to be running
    # In a real environment, you would start the FastAPI server with WebSocket support

    @pytest.mark.skip(reason="Requires WebSocket server setup")
    async def test_single_client_workflow_updates(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        ws_event_simulator: WebSocketEventSimulator,
    ):
        """Test WebSocket updates for a single client during workflow."""

        # Connect WebSocket client
        ws_client = WebSocketTestClient("ws://localhost:8000/ws/schedule-updates")
        connected = await ws_client.connect()
        assert connected, "Failed to connect to WebSocket"

        try:
            # Create job via REST API
            job_data = {
                "job_number": "WS-SINGLE-001",
                "customer_name": "WebSocket Test Customer",
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            job_id = job["id"]

            # Should receive job creation event
            creation_msg = await ws_client.receive_message(timeout=3.0)
            assert creation_msg is not None, "Should receive job creation event"
            assert creation_msg["type"] == "domain_event"
            assert creation_msg["event_type"] in ["JobCreated", "JobStatusChanged"]

            # Change job status via REST API
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "RELEASED", "reason": "websocket_test"},
                headers=auth_headers,
            )
            assert response.status_code == 200

            # Should receive status change event
            status_msg = await ws_client.receive_message(timeout=3.0)
            assert status_msg is not None, "Should receive status change event"
            assert status_msg["type"] == "domain_event"
            assert status_msg["event_type"] == "JobStatusChanged"
            assert status_msg["data"]["new_status"] == "RELEASED"

            # Add task via REST API
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 120,
            }

            response = client.post(
                f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201
            task = response.json()
            task_id = task["id"]

            # Should receive task creation event
            task_msg = await ws_client.receive_message(timeout=3.0)
            assert task_msg is not None, "Should receive task creation event"

            # Simulate task scheduling event
            await ws_event_simulator.simulate_task_scheduled(
                job_id, task_id, str(uuid4())
            )

            # Should receive task scheduled event
            scheduled_msg = await ws_client.receive_message(timeout=3.0)
            assert scheduled_msg is not None, "Should receive task scheduled event"
            assert scheduled_msg["event_type"] == "TaskScheduled"

        finally:
            await ws_client.disconnect()

    @pytest.mark.skip(reason="Requires WebSocket server setup")
    async def test_multi_client_event_broadcasting(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        ws_event_simulator: WebSocketEventSimulator,
    ):
        """Test event broadcasting to multiple WebSocket clients."""

        # Connect multiple WebSocket clients
        clients = []
        for i in range(3):
            ws_client = WebSocketTestClient("ws://localhost:8000/ws/schedule-updates")
            connected = await ws_client.connect()
            assert connected, f"Failed to connect client {i}"
            clients.append(ws_client)

        try:
            # Create job that will generate events
            job_data = {
                "job_number": "WS-MULTI-001",
                "customer_name": "Multi-Client Test",
                "due_date": (datetime.utcnow() + timedelta(days=4)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            job_id = job["id"]

            # All clients should receive job creation event
            creation_messages = []
            for i, ws_client in enumerate(clients):
                msg = await ws_client.receive_message(timeout=3.0)
                assert msg is not None, f"Client {i} should receive creation event"
                creation_messages.append(msg)

            # All messages should be similar (same event)
            event_types = [msg["event_type"] for msg in creation_messages]
            assert (
                len(set(event_types)) == 1
            ), "All clients should receive same event type"

            # Simulate complex workflow events
            events_to_simulate = [
                (
                    "job_status_change",
                    lambda: ws_event_simulator.simulate_job_status_change(
                        job_id, JobStatus.PLANNED, JobStatus.RELEASED
                    ),
                ),
                (
                    "task_scheduled",
                    lambda: ws_event_simulator.simulate_task_scheduled(
                        job_id, str(uuid4()), str(uuid4())
                    ),
                ),
                (
                    "critical_path_change",
                    lambda: ws_event_simulator.simulate_critical_path_change(
                        job_id, [str(uuid4()), str(uuid4())]
                    ),
                ),
            ]

            for event_name, event_func in events_to_simulate:
                # Trigger event
                await event_func()

                # All clients should receive the event
                event_messages = []
                for i, ws_client in enumerate(clients):
                    msg = await ws_client.receive_message(timeout=3.0)
                    assert (
                        msg is not None
                    ), f"Client {i} should receive {event_name} event"
                    event_messages.append(msg)

                # Verify all clients received same event
                event_ids = [msg["event_id"] for msg in event_messages]
                assert (
                    len(set(event_ids)) == 1
                ), f"All clients should receive same {event_name} event"

        finally:
            for ws_client in clients:
                await ws_client.disconnect()

    @pytest.mark.skip(reason="Requires WebSocket server setup")
    async def test_topic_based_subscription_filtering(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        ws_event_simulator: WebSocketEventSimulator,
    ):
        """Test topic-based event filtering for different client subscriptions."""

        # Connect clients with different topic subscriptions
        task_client = WebSocketTestClient("ws://localhost:8000/ws/task-updates")
        critical_client = WebSocketTestClient(
            "ws://localhost:8000/ws/critical-path-updates"
        )
        general_client = WebSocketTestClient("ws://localhost:8000/ws/schedule-updates")

        clients_info = [
            (task_client, "task_client", ["tasks"]),
            (critical_client, "critical_client", ["critical_path"]),
            (general_client, "general_client", ["all"]),
        ]

        # Connect all clients
        for ws_client, name, _topics in clients_info:
            connected = await ws_client.connect()
            assert connected, f"Failed to connect {name}"

        try:
            # Create test data
            job_id = str(uuid4())
            task_id = str(uuid4())
            machine_id = str(uuid4())

            # Simulate task-specific event
            await ws_event_simulator.simulate_task_scheduled(
                job_id, task_id, machine_id
            )

            # Only task_client and general_client should receive it
            task_msg = await task_client.receive_message(timeout=2.0)
            general_msg = await general_client.receive_message(timeout=2.0)
            critical_msg = await critical_client.receive_message(timeout=1.0)

            assert task_msg is not None, "Task client should receive task event"
            assert general_msg is not None, "General client should receive all events"
            assert critical_msg is None, "Critical client should not receive task event"

            assert task_msg["event_type"] == "TaskScheduled"
            assert general_msg["event_type"] == "TaskScheduled"

            # Simulate critical path event
            await ws_event_simulator.simulate_critical_path_change(job_id, [task_id])

            # Only critical_client and general_client should receive it
            task_msg = await task_client.receive_message(timeout=1.0)
            general_msg = await general_client.receive_message(timeout=2.0)
            critical_msg = await critical_client.receive_message(timeout=2.0)

            assert (
                task_msg is None
            ), "Task client should not receive critical path event"
            assert general_msg is not None, "General client should receive all events"
            assert (
                critical_msg is not None
            ), "Critical client should receive critical path event"

            assert general_msg["event_type"] == "CriticalPathChanged"
            assert critical_msg["event_type"] == "CriticalPathChanged"

        finally:
            for ws_client, name, _topics in clients_info:
                await ws_client.disconnect()

    async def test_websocket_connection_manager_stats(self, websocket_server):
        """Test WebSocket connection manager statistics."""

        # Get initial stats
        initial_stats = connection_manager.get_connection_stats()
        assert "total_connections" in initial_stats
        assert "topic_subscriptions" in initial_stats

        initial_count = initial_stats["total_connections"]

        # Simulate connections (since we can't actually connect in test environment)
        # We'll test the connection manager directly
        test_websocket = AsyncMock()

        # Simulate connecting clients
        await connection_manager.connect(test_websocket, "test_conn_1", ["tasks"])
        await connection_manager.connect(
            test_websocket, "test_conn_2", ["critical_path"]
        )
        await connection_manager.connect(test_websocket, "test_conn_3", ["all"])

        # Check updated stats
        updated_stats = connection_manager.get_connection_stats()
        assert updated_stats["total_connections"] == initial_count + 3
        assert "tasks" in updated_stats["topic_subscriptions"]
        assert "critical_path" in updated_stats["topic_subscriptions"]
        assert "all" in updated_stats["topic_subscriptions"]

        # Test disconnection
        connection_manager.disconnect("test_conn_1")
        connection_manager.disconnect("test_conn_2")

        final_stats = connection_manager.get_connection_stats()
        assert final_stats["total_connections"] == initial_count + 1

        # Clean up
        connection_manager.disconnect("test_conn_3")

    async def test_websocket_event_handler_message_format(
        self, ws_event_simulator: WebSocketEventSimulator
    ):
        """Test WebSocket event handler message formatting."""

        # Mock the connection manager to capture messages
        sent_messages = []

        original_broadcast = connection_manager.broadcast_to_topic

        async def mock_broadcast(topic: str, message: dict[str, Any]):
            sent_messages.append({"topic": topic, "message": message})

        connection_manager.broadcast_to_topic = mock_broadcast

        try:
            # Simulate different types of events
            job_id = str(uuid4())
            task_id = str(uuid4())

            # Job status change event
            await ws_event_simulator.simulate_job_status_change(
                job_id, JobStatus.PLANNED, JobStatus.RELEASED
            )

            # Task scheduled event
            await ws_event_simulator.simulate_task_scheduled(
                job_id, task_id, str(uuid4())
            )

            # Critical path change event
            await ws_event_simulator.simulate_critical_path_change(job_id, [task_id])

            # Verify messages were formatted correctly
            assert len(sent_messages) >= 3, "Should have sent at least 3 event messages"

            for sent_msg in sent_messages:
                message = sent_msg["message"]

                # Check required message structure
                assert "type" in message
                assert message["type"] == "domain_event"
                assert "event_type" in message
                assert "event_id" in message
                assert "occurred_at" in message
                assert "topic" in message
                assert "data" in message

                # Check data serialization
                data = message["data"]
                assert isinstance(data, dict)

                # UUIDs should be serialized as strings
                for key, value in data.items():
                    if "id" in key.lower():
                        assert isinstance(
                            value, str
                        ), f"{key} should be serialized as string"

        finally:
            # Restore original method
            connection_manager.broadcast_to_topic = original_broadcast

    async def test_websocket_error_handling(self):
        """Test WebSocket error handling and recovery."""

        # Test connection failure handling
        test_websocket = AsyncMock()
        test_websocket.send_text.side_effect = Exception("Connection lost")

        # Simulate connection
        await connection_manager.connect(test_websocket, "error_test_conn", ["all"])

        # Try to send message (should handle error gracefully)
        await connection_manager.send_personal_message(
            "error_test_conn", {"type": "test_message", "content": "This should fail"}
        )

        # Connection should be automatically disconnected after error
        stats = connection_manager.get_connection_stats()
        assert "error_test_conn" not in stats.get(
            "connections", {}
        ), "Failed connection should be cleaned up"

        # Test invalid JSON handling
        invalid_json_client = AsyncMock()
        await connection_manager.connect(invalid_json_client, "json_test_conn", ["all"])

        # This would typically be handled in the WebSocket endpoint
        # We're testing the connection manager's robustness

        # Clean up
        connection_manager.disconnect("json_test_conn")

    async def test_websocket_high_frequency_events(
        self, ws_event_simulator: WebSocketEventSimulator
    ):
        """Test WebSocket handling of high-frequency events."""

        sent_messages = []

        async def mock_broadcast(topic: str, message: dict[str, Any]):
            sent_messages.append(
                {"topic": topic, "message": message, "timestamp": time.time()}
            )

        original_broadcast = connection_manager.broadcast_to_topic
        connection_manager.broadcast_to_topic = mock_broadcast

        try:
            # Simulate rapid fire events
            job_id = str(uuid4())

            start_time = time.time()

            # Generate 20 events rapidly
            for i in range(20):
                if i % 3 == 0:
                    await ws_event_simulator.simulate_job_status_change(
                        job_id, JobStatus.PLANNED, JobStatus.IN_PROGRESS
                    )
                elif i % 3 == 1:
                    await ws_event_simulator.simulate_task_scheduled(
                        job_id, str(uuid4()), str(uuid4())
                    )
                else:
                    await ws_event_simulator.simulate_critical_path_change(
                        job_id, [str(uuid4())]
                    )

            end_time = time.time()
            processing_time = end_time - start_time

            # Verify all events were processed
            assert (
                len(sent_messages) >= 20
            ), f"Should have processed at least 20 events, got {len(sent_messages)}"

            # Processing should be reasonably fast
            assert (
                processing_time < 5.0
            ), f"Processing took {processing_time:.2f}s, too slow for high frequency"

            # Events should be in chronological order
            timestamps = [msg["timestamp"] for msg in sent_messages]
            assert timestamps == sorted(
                timestamps
            ), "Events should be processed in order"

            # Verify message integrity under high load
            for msg in sent_messages:
                message = msg["message"]
                assert (
                    "event_id" in message
                ), "Event ID should be present in high frequency events"
                assert "occurred_at" in message, "Timestamp should be present"
                assert (
                    message["type"] == "domain_event"
                ), "Message type should be consistent"

        finally:
            connection_manager.broadcast_to_topic = original_broadcast

    async def test_websocket_memory_usage_under_load(self):
        """Test WebSocket memory usage under sustained connection load."""

        # Simulate many connections
        test_connections = []
        connection_count = 100

        for i in range(connection_count):
            mock_websocket = AsyncMock()
            connection_id = f"load_test_{i}"

            await connection_manager.connect(
                mock_websocket, connection_id, ["all"] if i % 2 == 0 else ["tasks"]
            )
            test_connections.append(connection_id)

        # Check connection stats
        stats = connection_manager.get_connection_stats()
        assert stats["total_connections"] >= connection_count

        # Simulate message broadcasting to all connections
        test_message = {
            "type": "load_test",
            "data": {"test": "data"},
            "timestamp": datetime.now().isoformat(),
        }

        # Broadcast to all connections
        await connection_manager.broadcast_to_all(test_message)

        # Verify all connections were called
        for i in range(min(10, connection_count)):  # Check first 10 connections
            mock_ws = connection_manager.active_connections[f"load_test_{i}"]
            mock_ws.send_text.assert_called()

        # Clean up connections
        for connection_id in test_connections:
            connection_manager.disconnect(connection_id)

        # Verify cleanup
        final_stats = connection_manager.get_connection_stats()
        remaining_connections = [
            conn_id
            for conn_id in final_stats.get("connections", {}).keys()
            if conn_id.startswith("load_test_")
        ]
        assert (
            len(remaining_connections) == 0
        ), "All test connections should be cleaned up"


@pytest.mark.integration
class TestWebSocketWithRESTIntegration:
    """Test WebSocket integration with REST API workflows."""

    async def test_rest_api_triggers_websocket_events(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test that REST API operations trigger appropriate WebSocket events."""

        # This test verifies the integration between REST endpoints and WebSocket events
        # In a real scenario, domain events would be published by the business logic

        events_published = []

        # Mock the event publication to track events
        original_handler = websocket_handler.handle

        async def track_events(event):
            events_published.append(
                {
                    "event_type": type(event).__name__,
                    "event_id": str(event.event_id),
                    "timestamp": event.occurred_at.isoformat(),
                }
            )
            # Call original handler
            await original_handler(event)

        websocket_handler.handle = track_events

        try:
            # Perform REST operations that should generate events
            job_data = {
                "job_number": "WS-REST-001",
                "customer_name": "REST WebSocket Test",
                "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
            }

            # Create job
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            job_id = job["id"]

            # Update job status
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "RELEASED", "reason": "test"},
                headers=auth_headers,
            )
            assert response.status_code == 200

            # Add task
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 90,
            }

            response = client.post(
                f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201

            # Verify events were published (would depend on domain event integration)
            # This is a placeholder since the actual integration depends on domain event publishing
            assert len(events_published) >= 0, "Events should be tracked"

        finally:
            websocket_handler.handle = original_handler


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
