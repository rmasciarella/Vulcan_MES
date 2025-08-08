import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.routes import (
    domain_scheduling,
    health,
    jobs,
    login,
    private,
    resources,
    schedules,
    scheduling,
    status,
    users,
    utils,
)
from app.api.websockets import rest_router as websocket_rest_router
from app.api.websockets import router as websocket_router
from app.core.config import settings
from app.core.development import dev_router

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(health.router, tags=["health"])

# Scheduling routes - Core production scheduling functionality
api_router.include_router(jobs.router, prefix="/scheduling", tags=["jobs"])
api_router.include_router(schedules.router, prefix="/scheduling", tags=["schedules"])
api_router.include_router(resources.router, prefix="/scheduling", tags=["resources"])
api_router.include_router(status.router, prefix="/scheduling", tags=["status"])

# Legacy scheduling routes (for backward compatibility)
api_router.include_router(scheduling.router, prefix="/scheduling", tags=["scheduling"])
api_router.include_router(
    domain_scheduling.router, prefix="/scheduling", tags=["domain-scheduling"]
)
api_router.include_router(websocket_rest_router, tags=["websockets"])

# WebSocket routes (will be added to main app separately)
api_router.include_router(websocket_router)


# WebSocket demo page (development only)
@api_router.get("/websocket-demo", include_in_schema=False)
async def websocket_demo():
    """Serve the WebSocket demo page."""
    demo_file = os.path.join(
        os.path.dirname(__file__), "..", "static", "websocket_demo.html"
    )
    if os.path.exists(demo_file):
        return FileResponse(demo_file)
    return {"error": "Demo page not found"}


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
    api_router.include_router(dev_router, tags=["debug"])
