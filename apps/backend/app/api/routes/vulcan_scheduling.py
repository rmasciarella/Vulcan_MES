"""
Vulcan MES Scheduling API Endpoints

Production-ready scheduling endpoints with OR-Tools optimization.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4
import asyncio
import json

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import redis
from redis import asyncio as aioredis

from app.services.vulcan_scheduling_service import (
    VulcanSchedulingService,
    SchedulingSolution,
    ScheduleStatus,
    TaskSchedule
)
from app.core.config import settings
from app.infrastructure.database.dependencies import get_db
from app.core.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Redis for caching and WebSocket pub/sub
redis_client = None

async def get_redis():
    """Get Redis connection for caching."""
    global redis_client
    if not redis_client:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL or "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


class ScheduleRequest(BaseModel):
    """Request model for creating a schedule."""
    job_ids: Optional[List[int]] = Field(None, description="Specific job IDs to schedule")
    horizon_days: int = Field(14, ge=1, le=90, description="Planning horizon in days")
    time_limit_seconds: int = Field(60, ge=1, le=600, description="Solver time limit")
    optimize_for: str = Field("makespan", description="Optimization objective: makespan, cost, tardiness")
    use_cache: bool = Field(True, description="Use cached data if available")


class ScheduleResponse(BaseModel):
    """Response model for schedule creation."""
    schedule_id: str
    status: ScheduleStatus
    created_at: datetime
    makespan_minutes: int
    makespan_hours: float
    scheduled_tasks_count: int
    unscheduled_tasks_count: int
    solve_time_seconds: float
    machine_utilization_avg: float
    operator_utilization_avg: float
    tasks: Optional[List[Dict[str, Any]]] = None


class SchedulePersistence(BaseModel):
    """Model for persisting schedules to database."""
    schedule_id: str
    created_at: datetime
    created_by: str
    status: str
    solution_json: str
    makespan_minutes: int
    task_count: int
    solve_time_seconds: float
    parameters: Dict[str, Any]


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)


manager = ConnectionManager()


@router.post("/schedule", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create an optimized production schedule.
    
    This endpoint triggers the OR-Tools optimization solver to create
    a production schedule based on current jobs, resources, and constraints.
    """
    try:
        schedule_id = str(uuid4())
        logger.info(f"Creating schedule {schedule_id} with params: {request.dict()}")
        
        # Check cache if enabled
        redis = await get_redis()
        cache_key = f"schedule:{json.dumps(request.dict(), sort_keys=True)}"
        
        if request.use_cache:
            cached = await redis.get(cache_key)
            if cached:
                logger.info(f"Returning cached schedule for {cache_key}")
                return JSONResponse(json.loads(cached))
        
        # Create scheduling service
        db_config = {
            'host': settings.POSTGRES_SERVER,
            'database': settings.POSTGRES_DB,
            'user': settings.POSTGRES_USER,
            'password': settings.POSTGRES_PASSWORD
        }
        
        service = VulcanSchedulingService(db_config)
        
        # Fetch data and create model
        data = service.fetch_scheduling_data(request.job_ids)
        
        if not data['tasks']:
            raise HTTPException(status_code=404, detail="No tasks found to schedule")
        
        service.create_scheduling_model(data, request.horizon_days)
        
        # Add background task for long-running optimization
        if request.time_limit_seconds > 30:
            background_tasks.add_task(
                run_optimization_async,
                schedule_id,
                service,
                request,
                cache_key
            )
            
            return ScheduleResponse(
                schedule_id=schedule_id,
                status=ScheduleStatus.PENDING,
                created_at=datetime.now(),
                makespan_minutes=0,
                makespan_hours=0,
                scheduled_tasks_count=0,
                unscheduled_tasks_count=len(data['tasks']),
                solve_time_seconds=0,
                machine_utilization_avg=0,
                operator_utilization_avg=0
            )
        
        # Solve synchronously for short time limits
        solution = service.solve(request.time_limit_seconds)
        
        # Calculate averages
        machine_util_avg = sum(solution.machine_utilization.values()) / len(solution.machine_utilization) if solution.machine_utilization else 0
        operator_util_avg = sum(solution.operator_utilization.values()) / len(solution.operator_utilization) if solution.operator_utilization else 0
        
        response = ScheduleResponse(
            schedule_id=schedule_id,
            status=solution.status,
            created_at=datetime.now(),
            makespan_minutes=solution.makespan_minutes,
            makespan_hours=solution.makespan_minutes / 60,
            scheduled_tasks_count=len(solution.scheduled_tasks),
            unscheduled_tasks_count=len(solution.unscheduled_tasks),
            solve_time_seconds=solution.solve_time_seconds,
            machine_utilization_avg=machine_util_avg,
            operator_utilization_avg=operator_util_avg,
            tasks=[task.dict() for task in solution.scheduled_tasks[:10]]  # First 10 tasks
        )
        
        # Cache the result
        await redis.setex(cache_key, 3600, json.dumps(response.dict(), default=str))
        
        # Persist to database
        await persist_schedule(schedule_id, solution, request.dict())
        
        # Broadcast to WebSocket clients
        await manager.broadcast(json.dumps({
            "event": "schedule_created",
            "schedule_id": schedule_id,
            "status": solution.status.value,
            "makespan_hours": solution.makespan_minutes / 60
        }))
        
        return response
        
    except Exception as e:
        logger.error(f"Error creating schedule: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule/{schedule_id}")
async def get_schedule(schedule_id: str):
    """Get a specific schedule by ID."""
    try:
        redis = await get_redis()
        schedule_data = await redis.get(f"schedule:result:{schedule_id}")
        
        if not schedule_data:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return JSONResponse(json.loads(schedule_data))
        
    except Exception as e:
        logger.error(f"Error fetching schedule {schedule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules")
async def list_schedules(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[ScheduleStatus] = None
):
    """List recent schedules with pagination."""
    try:
        # In production, this would query from database
        # For now, return mock data
        schedules = []
        
        return {
            "schedules": schedules,
            "total": len(schedules),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listing schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedule/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a schedule."""
    try:
        redis = await get_redis()
        deleted = await redis.delete(f"schedule:result:{schedule_id}")
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"message": f"Schedule {schedule_id} deleted"}
        
    except Exception as e:
        logger.error(f"Error deleting schedule {schedule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time scheduling updates.
    
    Clients can connect to receive real-time updates about:
    - Schedule creation progress
    - Optimization status updates
    - Solution improvements
    - Resource allocation changes
    """
    await manager.connect(websocket, client_id)
    
    try:
        # Send initial connection message
        await websocket.send_text(json.dumps({
            "event": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        }))
        
        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
            elif message.get("type") == "subscribe":
                # Subscribe to specific schedule updates
                schedule_id = message.get("schedule_id")
                await subscribe_to_schedule(client_id, schedule_id)
            
            elif message.get("type") == "status":
                # Send current solver status
                await send_solver_status(websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        manager.disconnect(client_id)


async def run_optimization_async(
    schedule_id: str,
    service: VulcanSchedulingService,
    request: ScheduleRequest,
    cache_key: str
):
    """Run optimization in background and update via WebSocket."""
    try:
        logger.info(f"Starting async optimization for schedule {schedule_id}")
        
        # Solve the problem
        solution = service.solve(request.time_limit_seconds)
        
        # Store result in Redis
        redis = await get_redis()
        result_data = {
            "schedule_id": schedule_id,
            "status": solution.status.value,
            "makespan_minutes": solution.makespan_minutes,
            "scheduled_tasks": len(solution.scheduled_tasks),
            "solve_time": solution.solve_time_seconds
        }
        
        await redis.setex(
            f"schedule:result:{schedule_id}",
            86400,  # 24 hours
            json.dumps(result_data, default=str)
        )
        
        # Cache the result
        await redis.setex(cache_key, 3600, json.dumps(result_data, default=str))
        
        # Persist to database
        await persist_schedule(schedule_id, solution, request.dict())
        
        # Notify via WebSocket
        await manager.broadcast(json.dumps({
            "event": "optimization_complete",
            "schedule_id": schedule_id,
            "status": solution.status.value,
            "makespan_hours": solution.makespan_minutes / 60,
            "scheduled_tasks": len(solution.scheduled_tasks)
        }))
        
        logger.info(f"Completed async optimization for schedule {schedule_id}")
        
    except Exception as e:
        logger.error(f"Error in async optimization: {str(e)}", exc_info=True)
        
        # Notify error via WebSocket
        await manager.broadcast(json.dumps({
            "event": "optimization_error",
            "schedule_id": schedule_id,
            "error": str(e)
        }))


async def persist_schedule(schedule_id: str, solution: SchedulingSolution, parameters: Dict):
    """Persist schedule to database."""
    try:
        # In production, this would save to PostgreSQL
        # For now, just log
        logger.info(f"Persisting schedule {schedule_id} with {len(solution.scheduled_tasks)} tasks")
        
        # Store in Redis as backup
        redis = await get_redis()
        await redis.setex(
            f"schedule:persisted:{schedule_id}",
            86400 * 7,  # 1 week
            json.dumps({
                "schedule_id": schedule_id,
                "created_at": datetime.now().isoformat(),
                "solution": solution.dict(),
                "parameters": parameters
            }, default=str)
        )
        
    except Exception as e:
        logger.error(f"Error persisting schedule: {str(e)}")


async def subscribe_to_schedule(client_id: str, schedule_id: str):
    """Subscribe a client to schedule updates."""
    redis = await get_redis()
    await redis.sadd(f"schedule:subscribers:{schedule_id}", client_id)
    logger.info(f"Client {client_id} subscribed to schedule {schedule_id}")


async def send_solver_status(websocket: WebSocket):
    """Send current solver status to WebSocket client."""
    status = {
        "event": "solver_status",
        "timestamp": datetime.now().isoformat(),
        "active_schedules": 0,  # Would query from service
        "queue_length": 0
    }
    await websocket.send_text(json.dumps(status))


@router.get("/metrics")
async def get_scheduling_metrics():
    """Get scheduling system metrics."""
    try:
        redis = await get_redis()
        
        # Get metrics from Redis
        total_schedules = await redis.get("metrics:total_schedules") or 0
        avg_makespan = await redis.get("metrics:avg_makespan") or 0
        avg_solve_time = await redis.get("metrics:avg_solve_time") or 0
        
        return {
            "total_schedules_created": int(total_schedules),
            "average_makespan_hours": float(avg_makespan),
            "average_solve_time_seconds": float(avg_solve_time),
            "cache_hit_rate": 0.0,  # Would calculate from Redis stats
            "active_websocket_connections": len(manager.active_connections)
        }
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        return {
            "error": "Unable to fetch metrics",
            "total_schedules_created": 0,
            "active_websocket_connections": len(manager.active_connections)
        }