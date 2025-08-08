"""
Real-time WebSocket endpoint that bridges FastAPI and Supabase real-time.
Provides unified real-time updates for the application.
"""

import json
import asyncio
from typing import Dict, List, Set, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
import redis.asyncio as redis

from app.core.config import settings
from app.core.db import get_db
from app.core.supabase import supabase
from app.core.auth_dual import verify_token, CurrentUser
from app import models, crud


router = APIRouter()

# Store active connections
class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.supabase_channels: Dict[str, Any] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
            self.user_subscriptions[user_id] = set()
        
        self.active_connections[user_id].append(websocket)
        
        # Initialize Redis connection if configured
        if settings.REDIS_URL and not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                # Clean up if no more connections for this user
                del self.active_connections[user_id]
                del self.user_subscriptions[user_id]
                
                # Clean up Supabase channels
                for channel_name in list(self.supabase_channels.keys()):
                    if channel_name.startswith(f"{user_id}:"):
                        await self.unsubscribe_from_supabase(channel_name)
    
    async def subscribe(self, user_id: str, channel: str):
        """Subscribe a user to a channel."""
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].add(channel)
            
            # Subscribe to Supabase real-time if available
            if settings.SUPABASE_URL:
                await self.subscribe_to_supabase(user_id, channel)
    
    async def unsubscribe(self, user_id: str, channel: str):
        """Unsubscribe a user from a channel."""
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(channel)
            
            # Unsubscribe from Supabase
            channel_name = f"{user_id}:{channel}"
            await self.unsubscribe_from_supabase(channel_name)
    
    async def subscribe_to_supabase(self, user_id: str, channel: str):
        """Subscribe to Supabase real-time channel."""
        if not settings.SUPABASE_URL:
            return
        
        channel_name = f"{user_id}:{channel}"
        
        if channel_name in self.supabase_channels:
            return  # Already subscribed
        
        try:
            # Create Supabase channel based on the subscription type
            if channel == "tasks":
                sb_channel = (
                    supabase.client
                    .channel(channel_name)
                    .on(
                        "postgres_changes",
                        {
                            "event": "*",
                            "schema": "public",
                            "table": "task",
                        },
                        lambda payload: asyncio.create_task(
                            self.handle_supabase_event(user_id, "tasks", payload)
                        )
                    )
                    .subscribe()
                )
            elif channel == "schedules":
                sb_channel = (
                    supabase.client
                    .channel(channel_name)
                    .on(
                        "postgres_changes",
                        {
                            "event": "*",
                            "schema": "public",
                            "table": "schedule",
                        },
                        lambda payload: asyncio.create_task(
                            self.handle_supabase_event(user_id, "schedules", payload)
                        )
                    )
                    .subscribe()
                )
            elif channel == "notifications":
                sb_channel = (
                    supabase.client
                    .channel(channel_name)
                    .on(
                        "postgres_changes",
                        {
                            "event": "*",
                            "schema": "public",
                            "table": "notification",
                            "filter": f"user_id=eq.{user_id}",
                        },
                        lambda payload: asyncio.create_task(
                            self.handle_supabase_event(user_id, "notifications", payload)
                        )
                    )
                    .subscribe()
                )
            else:
                return
            
            self.supabase_channels[channel_name] = sb_channel
        except Exception as e:
            print(f"Error subscribing to Supabase channel {channel_name}: {e}")
    
    async def unsubscribe_from_supabase(self, channel_name: str):
        """Unsubscribe from Supabase real-time channel."""
        if channel_name in self.supabase_channels:
            try:
                await self.supabase_channels[channel_name].unsubscribe()
                del self.supabase_channels[channel_name]
            except Exception as e:
                print(f"Error unsubscribing from Supabase channel {channel_name}: {e}")
    
    async def handle_supabase_event(self, user_id: str, channel: str, payload: Dict):
        """Handle events from Supabase real-time."""
        message = {
            "type": "realtime_update",
            "channel": channel,
            "event": payload.get("eventType", "unknown"),
            "data": payload.get("new") or payload.get("old"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.send_to_user(user_id, message)
    
    async def send_to_user(self, user_id: str, message: Dict):
        """Send a message to all connections for a user."""
        if user_id in self.active_connections:
            message_text = json.dumps(message)
            
            # Send to all active connections for this user
            disconnected = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(message_text)
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for ws in disconnected:
                await self.disconnect(ws, user_id)
    
    async def broadcast_to_channel(self, channel: str, message: Dict):
        """Broadcast a message to all users subscribed to a channel."""
        for user_id, subscriptions in self.user_subscriptions.items():
            if channel in subscriptions:
                await self.send_to_user(user_id, message)
    
    async def handle_redis_message(self, channel: str, message: str):
        """Handle messages from Redis pub/sub."""
        try:
            data = json.loads(message)
            await self.broadcast_to_channel(channel, {
                "type": "redis_update",
                "channel": channel,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            print(f"Error handling Redis message: {e}")


# Create global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time updates.
    Supports both FastAPI and Supabase authentication.
    """
    try:
        # Verify authentication token
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await verify_token(credentials, db)
        
        # Verify user_id matches authenticated user
        if str(user.id) != user_id:
            await websocket.close(code=1008, reason="Invalid user ID")
            return
        
        # Connect the WebSocket
        await manager.connect(websocket, user_id)
        
        # Send initial connection success message
        await manager.send_to_user(user_id, {
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "subscribe":
                channel = message.get("channel")
                if channel:
                    await manager.subscribe(user_id, channel)
                    await manager.send_to_user(user_id, {
                        "type": "subscription",
                        "status": "subscribed",
                        "channel": channel,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            
            elif message.get("type") == "unsubscribe":
                channel = message.get("channel")
                if channel:
                    await manager.unsubscribe(user_id, channel)
                    await manager.send_to_user(user_id, {
                        "type": "subscription",
                        "status": "unsubscribed",
                        "channel": channel,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            
            elif message.get("type") == "ping":
                await manager.send_to_user(user_id, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        await manager.disconnect(websocket, user_id)
        await websocket.close(code=1011, reason="Internal server error")


@router.post("/notify/{channel}")
async def send_notification(
    channel: str,
    message: Dict[str, Any],
    current_user: CurrentUser,
):
    """
    Send a notification to a channel.
    This can be used to trigger real-time updates from the backend.
    """
    if not current_user.is_active:
        return {"error": "User not active"}
    
    notification = {
        "type": "notification",
        "channel": channel,
        "data": message,
        "sender_id": str(current_user.id),
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    await manager.broadcast_to_channel(channel, notification)
    
    # Also publish to Redis if available
    if manager.redis_client:
        await manager.redis_client.publish(
            channel,
            json.dumps(notification)
        )
    
    return {"status": "sent", "channel": channel}