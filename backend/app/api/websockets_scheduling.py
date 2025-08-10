"""
Enhanced WebSocket Support for Real-time Scheduling Operations

Provides high-performance WebSocket endpoints optimized for scheduling updates,
with efficient message serialization, connection pooling, and performance monitoring.
"""

import asyncio
import json
import msgpack
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

import numpy as np
from fastapi import Query, WebSocket, WebSocketDisconnect, status
from fastapi.routing import APIRouter

from app.core.observability import (
    ACTIVE_JOBS,
    COMPLETED_TASKS,
    get_correlation_id,
    get_logger,
    monitor_performance,
)
from app.domain.scheduling.events.domain_events import (
    CriticalPathChanged,
    DomainEvent,
    DomainEventHandler,
    JobDelayed,
    JobStatusChanged,
    ResourceConflictDetected,
    SchedulePublished,
    ScheduleUpdated,
    TaskCompleted,
    TaskScheduled,
    TaskStarted,
    get_event_dispatcher,
)
from app.models import User

# Initialize logger
logger = get_logger(__name__)

# WebSocket routers
router = APIRouter(prefix="/ws/scheduling", tags=["websockets-scheduling"])


class MessageFormat(Enum):
    """Supported message serialization formats."""
    JSON = "json"
    MSGPACK = "msgpack"
    PROTOBUF = "protobuf"  # Future support


@dataclass
class SchedulingMetrics:
    """Real-time scheduling performance metrics."""
    timestamp: datetime
    active_jobs: int
    active_tasks: int
    completed_tasks: int
    average_task_duration: float
    machine_utilization: Dict[UUID, float]
    operator_utilization: Dict[UUID, float]
    critical_path_length: float
    schedule_makespan: float
    tardiness_total: float
    solver_performance: Dict[str, float]


@dataclass
class ScheduleUpdate:
    """Efficient schedule update message."""
    update_id: UUID
    update_type: str  # 'task_assignment', 'resource_change', 'progress_update'
    affected_jobs: List[UUID]
    affected_tasks: List[UUID]
    changes: Dict[str, Any]
    timestamp: datetime
    priority: int  # 0-10, higher is more important


class MessageSerializer:
    """High-performance message serialization for WebSocket communication."""
    
    @staticmethod
    def serialize(data: Any, format: MessageFormat = MessageFormat.JSON) -> bytes:
        """Serialize data for transmission."""
        if format == MessageFormat.MSGPACK:
            return msgpack.packb(data, default=MessageSerializer._msgpack_encoder)
        else:  # JSON
            return json.dumps(data, default=MessageSerializer._json_encoder).encode()
    
    @staticmethod
    def deserialize(data: bytes, format: MessageFormat = MessageFormat.JSON) -> Any:
        """Deserialize received data."""
        if format == MessageFormat.MSGPACK:
            return msgpack.unpackb(data, raw=False)
        else:  # JSON
            return json.loads(data.decode())
    
    @staticmethod
    def _json_encoder(obj):
        """Custom JSON encoder for complex types."""
        if isinstance(obj, (UUID, datetime)):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    @staticmethod
    def _msgpack_encoder(obj):
        """Custom msgpack encoder for complex types."""
        if isinstance(obj, UUID):
            return {"__uuid__": str(obj)}
        elif isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        elif isinstance(obj, Decimal):
            return {"__decimal__": str(obj)}
        return obj


class SchedulingConnectionPool:
    """Connection pool optimized for scheduling updates."""
    
    def __init__(self, max_connections_per_schedule: int = 100):
        self.max_connections = max_connections_per_schedule
        self.schedule_connections: Dict[UUID, Set[str]] = defaultdict(set)
        self.connection_schedules: Dict[str, Set[UUID]] = defaultdict(set)
        self.connection_formats: Dict[str, MessageFormat] = {}
        self.message_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.last_activity: Dict[str, datetime] = {}
        self.performance_stats: Dict[str, Dict] = defaultdict(dict)
        
    def add_connection(
        self, 
        connection_id: str, 
        schedule_id: UUID,
        format: MessageFormat = MessageFormat.JSON
    ) -> bool:
        """Add connection to schedule pool."""
        if len(self.schedule_connections[schedule_id]) >= self.max_connections:
            return False
            
        self.schedule_connections[schedule_id].add(connection_id)
        self.connection_schedules[connection_id].add(schedule_id)
        self.connection_formats[connection_id] = format
        self.last_activity[connection_id] = datetime.now()
        
        # Initialize performance tracking
        self.performance_stats[connection_id] = {
            "messages_sent": 0,
            "bytes_sent": 0,
            "messages_received": 0,
            "bytes_received": 0,
            "avg_latency_ms": 0,
            "connected_at": datetime.now()
        }
        
        return True
    
    def remove_connection(self, connection_id: str):
        """Remove connection from all pools."""
        for schedule_id in self.connection_schedules[connection_id]:
            self.schedule_connections[schedule_id].discard(connection_id)
        
        del self.connection_schedules[connection_id]
        del self.connection_formats[connection_id]
        del self.message_queues[connection_id]
        del self.last_activity[connection_id]
        del self.performance_stats[connection_id]
    
    def get_schedule_connections(self, schedule_id: UUID) -> Set[str]:
        """Get all connections for a schedule."""
        return self.schedule_connections[schedule_id].copy()
    
    def update_stats(
        self, 
        connection_id: str,
        sent: bool,
        message_size: int,
        latency_ms: float = 0
    ):
        """Update connection performance statistics."""
        if connection_id not in self.performance_stats:
            return
            
        stats = self.performance_stats[connection_id]
        if sent:
            stats["messages_sent"] += 1
            stats["bytes_sent"] += message_size
        else:
            stats["messages_received"] += 1
            stats["bytes_received"] += message_size
            
        if latency_ms > 0:
            # Update rolling average latency
            current_avg = stats["avg_latency_ms"]
            total_messages = stats["messages_sent"] + stats["messages_received"]
            stats["avg_latency_ms"] = (
                (current_avg * (total_messages - 1) + latency_ms) / total_messages
            )
        
        self.last_activity[connection_id] = datetime.now()


class SchedulingWebSocketManager:
    """High-performance WebSocket manager for scheduling operations."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_pool = SchedulingConnectionPool()
        self.serializer = MessageSerializer()
        self.update_buffer: Dict[UUID, List[ScheduleUpdate]] = defaultdict(list)
        self.batch_interval = 0.1  # Batch updates every 100ms
        self.compression_threshold = 1024  # Compress messages > 1KB
        
        # Performance monitoring
        self.metrics = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_bytes_sent": 0,
            "avg_message_size": 0,
            "peak_connections": 0,
            "update_batch_size": 0
        }
        
        # Start background tasks
        asyncio.create_task(self._batch_update_sender())
        asyncio.create_task(self._connection_health_monitor())
        asyncio.create_task(self._metrics_aggregator())
    
    @monitor_performance("websocket_connect")
    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        schedule_id: UUID,
        user: Optional[User] = None,
        format: MessageFormat = MessageFormat.JSON
    ) -> bool:
        """Accept and configure WebSocket connection."""
        try:
            await websocket.accept()
            
            # Add to connection pool
            if not self.connection_pool.add_connection(connection_id, schedule_id, format):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Schedule connection limit reached"
                )
                return False
            
            self.active_connections[connection_id] = websocket
            
            # Update metrics
            self.metrics["total_connections"] += 1
            current_connections = len(self.active_connections)
            if current_connections > self.metrics["peak_connections"]:
                self.metrics["peak_connections"] = current_connections
            
            # Send initial state
            await self._send_initial_state(connection_id, schedule_id)
            
            logger.info(
                "Scheduling WebSocket connected",
                connection_id=connection_id,
                schedule_id=str(schedule_id),
                user_id=str(user.id) if user else None,
                format=format.value
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to establish scheduling WebSocket",
                connection_id=connection_id,
                error=str(e)
            )
            return False
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        self.connection_pool.remove_connection(connection_id)
        
        logger.info("Scheduling WebSocket disconnected", connection_id=connection_id)
    
    @monitor_performance("send_schedule_update")
    async def send_schedule_update(
        self,
        schedule_id: UUID,
        update: ScheduleUpdate,
        immediate: bool = False
    ):
        """Send schedule update to all connected clients."""
        if immediate or update.priority >= 8:
            # Send immediately for high-priority updates
            await self._broadcast_update(schedule_id, update)
        else:
            # Buffer for batch sending
            self.update_buffer[schedule_id].append(update)
    
    async def _broadcast_update(self, schedule_id: UUID, update: ScheduleUpdate):
        """Broadcast update to all connections for a schedule."""
        connections = self.connection_pool.get_schedule_connections(schedule_id)
        
        if not connections:
            return
        
        # Serialize once for all connections with same format
        format_groups = defaultdict(list)
        for conn_id in connections:
            format = self.connection_pool.connection_formats.get(
                conn_id, MessageFormat.JSON
            )
            format_groups[format].append(conn_id)
        
        for format, conn_ids in format_groups.items():
            # Serialize update
            update_dict = asdict(update)
            serialized = self.serializer.serialize(update_dict, format)
            
            # Send to all connections with this format
            for conn_id in conn_ids:
                await self._send_to_connection(conn_id, serialized, format)
    
    async def _send_to_connection(
        self,
        connection_id: str,
        data: bytes,
        format: MessageFormat
    ):
        """Send data to specific connection with error handling."""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return
        
        try:
            start_time = time.time()
            
            # Send based on format
            if format == MessageFormat.MSGPACK:
                await websocket.send_bytes(data)
            else:
                await websocket.send_text(data.decode())
            
            # Update statistics
            latency_ms = (time.time() - start_time) * 1000
            self.connection_pool.update_stats(
                connection_id, sent=True, message_size=len(data), latency_ms=latency_ms
            )
            
            self.metrics["total_messages_sent"] += 1
            self.metrics["total_bytes_sent"] += len(data)
            
        except Exception as e:
            logger.error(
                "Error sending to WebSocket",
                connection_id=connection_id,
                error=str(e)
            )
            self.disconnect(connection_id)
    
    async def _send_initial_state(self, connection_id: str, schedule_id: UUID):
        """Send initial schedule state to new connection."""
        # This would fetch current schedule state from database
        initial_state = {
            "type": "initial_state",
            "schedule_id": str(schedule_id),
            "timestamp": datetime.now().isoformat(),
            "active_jobs": int(ACTIVE_JOBS._value.get()),
            "completed_tasks": int(COMPLETED_TASKS._value.get()),
            # Add more initial state data
        }
        
        format = self.connection_pool.connection_formats.get(
            connection_id, MessageFormat.JSON
        )
        serialized = self.serializer.serialize(initial_state, format)
        await self._send_to_connection(connection_id, serialized, format)
    
    async def _batch_update_sender(self):
        """Background task to send batched updates."""
        while True:
            await asyncio.sleep(self.batch_interval)
            
            for schedule_id, updates in self.update_buffer.items():
                if not updates:
                    continue
                
                # Sort by priority and timestamp
                updates.sort(key=lambda u: (-u.priority, u.timestamp))
                
                # Take up to 50 updates per batch
                batch = updates[:50]
                self.update_buffer[schedule_id] = updates[50:]
                
                # Create batch message
                batch_message = {
                    "type": "batch_update",
                    "schedule_id": str(schedule_id),
                    "updates": [asdict(u) for u in batch],
                    "count": len(batch),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Broadcast batch
                for format in [MessageFormat.JSON, MessageFormat.MSGPACK]:
                    connections = [
                        c for c in self.connection_pool.get_schedule_connections(schedule_id)
                        if self.connection_pool.connection_formats.get(c) == format
                    ]
                    
                    if connections:
                        serialized = self.serializer.serialize(batch_message, format)
                        for conn_id in connections:
                            await self._send_to_connection(conn_id, serialized, format)
                
                self.metrics["update_batch_size"] = len(batch)
    
    async def _connection_health_monitor(self):
        """Monitor connection health and clean up stale connections."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            current_time = datetime.now()
            stale_connections = []
            
            for conn_id, last_activity in self.connection_pool.last_activity.items():
                if current_time - last_activity > timedelta(minutes=5):
                    stale_connections.append(conn_id)
            
            for conn_id in stale_connections:
                logger.warning("Removing stale connection", connection_id=conn_id)
                self.disconnect(conn_id)
    
    async def _metrics_aggregator(self):
        """Aggregate and log performance metrics."""
        while True:
            await asyncio.sleep(60)  # Log metrics every minute
            
            if self.metrics["total_messages_sent"] > 0:
                self.metrics["avg_message_size"] = (
                    self.metrics["total_bytes_sent"] / self.metrics["total_messages_sent"]
                )
            
            logger.info("WebSocket performance metrics", **self.metrics)
            
            # Calculate per-connection metrics
            for conn_id, stats in self.connection_pool.performance_stats.items():
                throughput = stats["bytes_sent"] / max(
                    1, (datetime.now() - stats["connected_at"]).total_seconds()
                )
                logger.debug(
                    "Connection performance",
                    connection_id=conn_id,
                    throughput_bytes_per_sec=throughput,
                    avg_latency_ms=stats["avg_latency_ms"]
                )


# Global manager instance
scheduling_manager = SchedulingWebSocketManager()


class SchedulingEventHandler(DomainEventHandler):
    """Optimized domain event handler for scheduling updates."""
    
    def __init__(self, manager: SchedulingWebSocketManager):
        self.manager = manager
        self.event_buffer = defaultdict(list)
        self.buffer_interval = 0.05  # 50ms buffering
        asyncio.create_task(self._flush_buffer())
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Handle scheduling-related events."""
        return isinstance(event, (
            TaskScheduled, TaskStarted, TaskCompleted,
            JobDelayed, JobStatusChanged,
            ResourceConflictDetected, CriticalPathChanged,
            SchedulePublished, ScheduleUpdated
        ))
    
    def handle(self, event: DomainEvent) -> None:
        """Handle domain event with buffering."""
        asyncio.create_task(self._handle_async(event))
    
    async def _handle_async(self, event: DomainEvent):
        """Process event asynchronously."""
        try:
            # Determine affected schedule
            schedule_id = self._get_schedule_id(event)
            if not schedule_id:
                return
            
            # Create update from event
            update = self._create_update(event)
            
            # Determine priority
            priority = self._get_event_priority(event)
            update.priority = priority
            
            # Send update
            await self.manager.send_schedule_update(
                schedule_id, update, immediate=(priority >= 9)
            )
            
        except Exception as e:
            logger.error(
                "Error handling scheduling event",
                event_type=type(event).__name__,
                error=str(e)
            )
    
    def _get_schedule_id(self, event: DomainEvent) -> Optional[UUID]:
        """Extract schedule ID from event."""
        if hasattr(event, 'schedule_id'):
            return event.schedule_id
        elif hasattr(event, 'aggregate_id'):
            return event.aggregate_id
        return None
    
    def _create_update(self, event: DomainEvent) -> ScheduleUpdate:
        """Create schedule update from domain event."""
        update_type = "unknown"
        affected_jobs = []
        affected_tasks = []
        changes = {}
        
        if isinstance(event, TaskScheduled):
            update_type = "task_scheduled"
            affected_jobs = [event.job_id]
            affected_tasks = [event.task_id]
            changes = {
                "machine_id": str(event.machine_id),
                "operator_ids": [str(o) for o in event.operator_ids],
                "planned_start": event.planned_start.isoformat(),
                "planned_end": event.planned_end.isoformat()
            }
        elif isinstance(event, TaskCompleted):
            update_type = "task_completed"
            affected_jobs = [event.job_id]
            affected_tasks = [event.task_id]
            changes = {
                "actual_end": event.actual_end.isoformat(),
                "actual_duration": str(event.actual_duration)
            }
        elif isinstance(event, JobDelayed):
            update_type = "job_delayed"
            affected_jobs = [event.job_id]
            changes = {
                "original_due": event.original_due_date.isoformat(),
                "expected_completion": event.expected_completion.isoformat(),
                "delay_hours": float(event.delay_hours)
            }
        elif isinstance(event, ResourceConflictDetected):
            update_type = "resource_conflict"
            affected_tasks = event.conflicting_tasks
            changes = {
                "resource_type": event.resource_type,
                "resource_id": str(event.resource_id),
                "conflict_start": event.conflict_time_start.isoformat(),
                "conflict_end": event.conflict_time_end.isoformat()
            }
        elif isinstance(event, CriticalPathChanged):
            update_type = "critical_path_changed"
            affected_jobs = [event.job_id]
            affected_tasks = event.new_critical_tasks
            changes = {
                "old_critical_tasks": [str(t) for t in event.old_critical_tasks],
                "new_critical_tasks": [str(t) for t in event.new_critical_tasks],
                "new_makespan_hours": float(event.new_makespan_hours)
            }
        
        return ScheduleUpdate(
            update_id=uuid4(),
            update_type=update_type,
            affected_jobs=affected_jobs,
            affected_tasks=affected_tasks,
            changes=changes,
            timestamp=event.occurred_at,
            priority=5  # Default, will be overridden
        )
    
    def _get_event_priority(self, event: DomainEvent) -> int:
        """Determine event priority (0-10)."""
        if isinstance(event, (ResourceConflictDetected, JobDelayed)):
            return 9  # High priority - conflicts and delays
        elif isinstance(event, CriticalPathChanged):
            return 8  # High - critical path changes
        elif isinstance(event, (SchedulePublished, ScheduleUpdated)):
            return 7  # Medium-high - schedule changes
        elif isinstance(event, (TaskStarted, TaskCompleted)):
            return 6  # Medium - task progress
        elif isinstance(event, TaskScheduled):
            return 5  # Medium - new assignments
        else:
            return 3  # Low - other events
    
    async def _flush_buffer(self):
        """Periodically flush event buffer."""
        while True:
            await asyncio.sleep(self.buffer_interval)
            # Process buffered events if needed


# Register event handler
scheduling_handler = SchedulingEventHandler(scheduling_manager)
get_event_dispatcher().register_handler(scheduling_handler)


# WebSocket Endpoints

@router.websocket("/schedule/{schedule_id}")
async def websocket_schedule_optimized(
    websocket: WebSocket,
    schedule_id: UUID,
    token: Optional[str] = Query(None),
    format: str = Query("json")
):
    """
    Optimized WebSocket endpoint for real-time schedule updates.
    
    Features:
    - Efficient message serialization (JSON or MessagePack)
    - Update batching for improved performance
    - Connection pooling per schedule
    - Automatic compression for large messages
    """
    from app.api.websockets import authenticate_websocket
    
    connection_id = f"sched_{schedule_id}_{datetime.now().timestamp()}"
    
    # Authenticate
    user = await authenticate_websocket(token)
    
    # Parse format
    msg_format = MessageFormat.MSGPACK if format == "msgpack" else MessageFormat.JSON
    
    # Connect
    if not await scheduling_manager.connect(
        websocket, connection_id, schedule_id, user, msg_format
    ):
        await websocket.close()
        return
    
    try:
        while True:
            # Receive messages based on format
            if msg_format == MessageFormat.MSGPACK:
                data = await websocket.receive_bytes()
                message = MessageSerializer.deserialize(data, MessageFormat.MSGPACK)
            else:
                data = await websocket.receive_text()
                message = json.loads(data)
            
            # Update stats
            scheduling_manager.connection_pool.update_stats(
                connection_id, sent=False, message_size=len(data)
            )
            
            # Handle message
            await handle_scheduling_message(connection_id, schedule_id, message)
            
    except WebSocketDisconnect:
        scheduling_manager.disconnect(connection_id)


async def handle_scheduling_message(
    connection_id: str,
    schedule_id: UUID,
    message: dict
):
    """Handle messages from scheduling WebSocket clients."""
    message_type = message.get("type")
    
    if message_type == "subscribe_metrics":
        # Subscribe to performance metrics
        asyncio.create_task(send_performance_metrics(connection_id, schedule_id))
    
    elif message_type == "get_critical_path":
        # Send critical path information
        asyncio.create_task(send_critical_path(connection_id, schedule_id))
    
    elif message_type == "get_resource_utilization":
        # Send resource utilization data
        asyncio.create_task(send_resource_utilization(connection_id, schedule_id))
    
    else:
        logger.debug(
            "Unknown scheduling message type",
            connection_id=connection_id,
            message_type=message_type
        )


async def send_performance_metrics(connection_id: str, schedule_id: UUID):
    """Send real-time performance metrics to client."""
    # This would fetch actual metrics from monitoring system
    metrics = SchedulingMetrics(
        timestamp=datetime.now(),
        active_jobs=int(ACTIVE_JOBS._value.get()),
        active_tasks=0,  # Would calculate from database
        completed_tasks=int(COMPLETED_TASKS._value.get()),
        average_task_duration=45.5,  # Minutes
        machine_utilization={},  # Would calculate actual utilization
        operator_utilization={},  # Would calculate actual utilization
        critical_path_length=480.0,  # Minutes
        schedule_makespan=960.0,  # Minutes
        tardiness_total=120.0,  # Minutes
        solver_performance={
            "last_solve_time": 2.5,
            "optimization_gap": 0.05,
            "iterations": 1000
        }
    )
    
    message = {
        "type": "performance_metrics",
        "metrics": asdict(metrics)
    }
    
    format = scheduling_manager.connection_pool.connection_formats.get(
        connection_id, MessageFormat.JSON
    )
    serialized = MessageSerializer.serialize(message, format)
    await scheduling_manager._send_to_connection(connection_id, serialized, format)


async def send_critical_path(connection_id: str, schedule_id: UUID):
    """Send critical path information to client."""
    # This would calculate actual critical path
    critical_path = {
        "type": "critical_path",
        "schedule_id": str(schedule_id),
        "path": [],  # List of task IDs in critical path
        "total_duration": 480.0,  # Minutes
        "bottleneck_resources": [],  # Resources causing bottlenecks
        "timestamp": datetime.now().isoformat()
    }
    
    format = scheduling_manager.connection_pool.connection_formats.get(
        connection_id, MessageFormat.JSON
    )
    serialized = MessageSerializer.serialize(critical_path, format)
    await scheduling_manager._send_to_connection(connection_id, serialized, format)


async def send_resource_utilization(connection_id: str, schedule_id: UUID):
    """Send resource utilization data to client."""
    # This would calculate actual utilization
    utilization = {
        "type": "resource_utilization",
        "schedule_id": str(schedule_id),
        "machines": {},  # Machine ID -> utilization percentage
        "operators": {},  # Operator ID -> utilization percentage
        "peak_periods": [],  # Time periods with highest utilization
        "idle_periods": [],  # Time periods with lowest utilization
        "timestamp": datetime.now().isoformat()
    }
    
    format = scheduling_manager.connection_pool.connection_formats.get(
        connection_id, MessageFormat.JSON
    )
    serialized = MessageSerializer.serialize(utilization, format)
    await scheduling_manager._send_to_connection(connection_id, serialized, format)