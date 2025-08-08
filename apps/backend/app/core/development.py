"""
Development Tooling and Debugging Utilities

Comprehensive development tools for debugging, testing, profiling, and
development environment setup for the scheduling system.
"""

import asyncio
import cProfile
import io
import pstats
import random
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psutil
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from ..domain.scheduling.value_objects.enums import Priority, SkillLevel, TaskType
from .config import settings
from .health import health_checker
from .observability import get_correlation_id, get_logger, log_performance_metrics

logger = get_logger(__name__)


class DevelopmentTools:
    """Collection of development and debugging utilities."""

    def __init__(self):
        self.profiler_sessions = {}
        self.debug_data_cache = {}

    def start_profiler(self, session_id: str = None) -> str:
        """Start a profiling session."""
        if session_id is None:
            session_id = str(uuid4())

        profiler = cProfile.Profile()
        profiler.enable()

        self.profiler_sessions[session_id] = {
            "profiler": profiler,
            "start_time": time.time(),
        }

        logger.info("Profiling session started", session_id=session_id)
        return session_id

    def stop_profiler(self, session_id: str) -> dict[str, Any]:
        """Stop profiling and return statistics."""
        if session_id not in self.profiler_sessions:
            raise ValueError(f"Profiling session {session_id} not found")

        session = self.profiler_sessions[session_id]
        profiler = session["profiler"]

        profiler.disable()

        # Get statistics
        stats_stream = io.StringIO()
        ps = pstats.Stats(profiler, stream=stats_stream)
        ps.sort_stats("cumulative")
        ps.print_stats(50)  # Top 50 functions

        duration = time.time() - session["start_time"]

        result = {
            "session_id": session_id,
            "duration_seconds": duration,
            "stats": stats_stream.getvalue(),
        }

        # Clean up
        del self.profiler_sessions[session_id]

        logger.info(
            "Profiling session completed",
            session_id=session_id,
            duration_seconds=duration,
        )

        return result


# Global development tools instance
dev_tools = DevelopmentTools()


class TestDataGenerator:
    """Generate test data for development and testing."""

    def __init__(self):
        self.task_types = list(TaskType)
        self.priorities = list(Priority)
        self.skill_levels = list(SkillLevel)

        # Sample skill names
        self.skill_names = [
            "Welding",
            "Machining",
            "Assembly",
            "Inspection",
            "Painting",
            "Electrical",
            "Hydraulics",
            "Programming",
            "Quality Control",
            "Material Handling",
            "Packaging",
            "Testing",
        ]

    def generate_jobs(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate sample jobs for testing."""
        jobs = []

        for i in range(count):
            job_id = uuid4()
            due_date = datetime.now() + timedelta(days=random.randint(5, 30))

            job = {
                "id": str(job_id),
                "name": f"Job-{i+1:03d}",
                "description": f"Test job {i+1} for development",
                "priority": random.choice(self.priorities).value,
                "due_date": due_date.isoformat(),
                "created_at": datetime.now().isoformat(),
                "tasks": self.generate_tasks_for_job(job_id, random.randint(3, 8)),
            }
            jobs.append(job)

        return jobs

    def generate_tasks_for_job(
        self, job_id: UUID, count: int = 5
    ) -> list[dict[str, Any]]:
        """Generate tasks for a specific job."""
        tasks = []

        for i in range(count):
            task = {
                "id": str(uuid4()),
                "job_id": str(job_id),
                "name": f"Task-{i+1}",
                "description": f"Task {i+1} for job {job_id}",
                "position_in_job": i,
                "task_type": random.choice(self.task_types).value,
                "estimated_duration_minutes": random.randint(30, 240),
                "setup_duration_minutes": random.randint(5, 30),
                "required_skills": [
                    {
                        "name": random.choice(self.skill_names),
                        "level": random.choice(self.skill_levels).value,
                        "required": True,
                    }
                ],
                "priority": random.choice(self.priorities).value,
            }
            tasks.append(task)

        return tasks

    def generate_machines(self, count: int = 10) -> list[dict[str, Any]]:
        """Generate sample machines."""
        machines = []
        machine_types = [
            "CNC",
            "Lathe",
            "Mill",
            "Welder",
            "Press",
            "Grinder",
            "Drill",
            "Saw",
        ]

        for i in range(count):
            machine_type = random.choice(machine_types)
            machine = {
                "id": str(uuid4()),
                "name": f"{machine_type}-{i+1:02d}",
                "machine_type": machine_type,
                "capabilities": random.sample(self.task_types, k=random.randint(1, 4)),
                "hourly_cost": random.uniform(50, 200),
                "setup_time_minutes": random.randint(5, 30),
                "availability_start": "07:00",
                "availability_end": "17:00",
                "maintenance_schedule": [],
            }
            machines.append(machine)

        return machines

    def generate_operators(self, count: int = 15) -> list[dict[str, Any]]:
        """Generate sample operators."""
        operators = []

        for i in range(count):
            operator = {
                "id": str(uuid4()),
                "name": f"Operator-{i+1:02d}",
                "employee_id": f"EMP{1000+i}",
                "skills": [
                    {
                        "name": skill,
                        "level": random.choice(self.skill_levels).value,
                        "years_experience": random.randint(1, 15),
                    }
                    for skill in random.sample(self.skill_names, k=random.randint(2, 5))
                ],
                "hourly_rate": random.uniform(15, 45),
                "availability_start": "07:00",
                "availability_end": "16:00",
                "max_concurrent_tasks": random.randint(1, 3),
            }
            operators.append(operator)

        return operators

    def generate_complete_scenario(
        self, job_count: int = 5, machine_count: int = 10, operator_count: int = 15
    ) -> dict[str, Any]:
        """Generate a complete test scenario with all entities."""
        return {
            "scenario_id": str(uuid4()),
            "name": f"Test Scenario - {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Auto-generated test scenario for development",
            "created_at": datetime.now().isoformat(),
            "jobs": self.generate_jobs(job_count),
            "machines": self.generate_machines(machine_count),
            "operators": self.generate_operators(operator_count),
            "statistics": {
                "total_jobs": job_count,
                "total_tasks": sum(
                    len(job["tasks"]) for job in self.generate_jobs(job_count)
                ),
                "total_machines": machine_count,
                "total_operators": operator_count,
            },
        }


# Global test data generator
test_data_generator = TestDataGenerator()


class DebugMiddleware:
    """Debugging middleware for development environment."""

    def __init__(self):
        self.request_logs = []
        self.max_logs = 1000

    def log_request(self, request: Request, response_time: float):
        """Log request for debugging."""
        if settings.ENVIRONMENT != "local":
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "response_time_ms": response_time * 1000,
            "correlation_id": get_correlation_id(),
        }

        self.request_logs.append(log_entry)

        # Keep only recent logs
        if len(self.request_logs) > self.max_logs:
            self.request_logs.pop(0)

    def get_recent_requests(self, count: int = 100) -> list[dict[str, Any]]:
        """Get recent request logs."""
        return self.request_logs[-count:]


# Global debug middleware
debug_middleware = DebugMiddleware()


def get_system_info() -> dict[str, Any]:
    """Get comprehensive system information."""
    try:
        process = psutil.Process()

        return {
            "process": {
                "pid": process.pid,
                "name": process.name(),
                "status": process.status(),
                "create_time": datetime.fromtimestamp(
                    process.create_time()
                ).isoformat(),
                "memory_info": process.memory_info()._asdict(),
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
            },
            "system": {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": psutil.disk_usage("/")._asdict(),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "load_average": psutil.getloadavg()
                if hasattr(psutil, "getloadavg")
                else None,
            },
            "python": {
                "version": psutil.version_info,
                "platform": psutil.LINUX or psutil.MACOS or psutil.WINDOWS,
            },
        }
    except Exception as e:
        logger.error("Failed to get system info", error=str(e))
        return {"error": str(e)}


def benchmark_operation(operation_name: str, iterations: int = 100):
    """Decorator to benchmark operation performance."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            times = []

            logger.info(f"Starting benchmark: {operation_name}")

            for _i in range(iterations):
                start_time = time.time()

                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                duration = time.time() - start_time
                times.append(duration)

            # Calculate statistics
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            benchmark_results = {
                "operation": operation_name,
                "iterations": iterations,
                "avg_time_seconds": avg_time,
                "min_time_seconds": min_time,
                "max_time_seconds": max_time,
                "total_time_seconds": sum(times),
                "operations_per_second": iterations / sum(times),
            }

            logger.info("Benchmark completed", **benchmark_results)

            # Log performance metrics
            log_performance_metrics(
                operation=f"benchmark_{operation_name}",
                duration_seconds=avg_time,
                metadata=benchmark_results,
            )

            return result

        return wrapper

    return decorator


# Development API Router
dev_router = APIRouter()


@dev_router.get("/debug/system-info")
async def get_system_info_endpoint():
    """Get system information for debugging."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    return get_system_info()


@dev_router.get("/debug/request-logs")
async def get_request_logs(count: int = Query(100, le=1000)):
    """Get recent request logs for debugging."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    return {
        "logs": debug_middleware.get_recent_requests(count),
        "total_stored": len(debug_middleware.request_logs),
    }


@dev_router.post("/debug/profiler/start")
async def start_profiler_session():
    """Start a new profiling session."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    session_id = dev_tools.start_profiler()
    return {"session_id": session_id, "message": "Profiling session started"}


@dev_router.post("/debug/profiler/{session_id}/stop")
async def stop_profiler_session(session_id: str):
    """Stop a profiling session and get results."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    try:
        results = dev_tools.stop_profiler(session_id)
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@dev_router.get("/debug/test-data/scenario")
async def generate_test_scenario(
    jobs: int = Query(5, ge=1, le=20),
    machines: int = Query(10, ge=1, le=50),
    operators: int = Query(15, ge=1, le=100),
):
    """Generate test data scenario for development."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    scenario = test_data_generator.generate_complete_scenario(jobs, machines, operators)
    return scenario


@dev_router.get("/debug/health-history")
async def get_health_check_history():
    """Get health check history for debugging."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    return {
        "last_results": {
            name: result.to_dict()
            for name, result in health_checker.last_results.items()
        },
        "registered_checks": list(health_checker.checks.keys()),
    }


@dev_router.get("/debug/environment")
async def get_environment_info():
    """Get environment configuration for debugging."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    # Safe environment info (no secrets)
    env_info = {
        "environment": settings.ENVIRONMENT,
        "log_level": settings.LOG_LEVEL,
        "log_format": settings.LOG_FORMAT,
        "enable_metrics": settings.ENABLE_METRICS,
        "enable_tracing": settings.ENABLE_TRACING,
        "metrics_port": settings.METRICS_PORT,
        "api_v1_str": settings.API_V1_STR,
        "frontend_host": settings.FRONTEND_HOST,
        "cors_origins_count": len(settings.all_cors_origins),
        "database_host": settings.POSTGRES_SERVER,
        "database_port": settings.POSTGRES_PORT,
        "database_name": settings.POSTGRES_DB,
        "sentry_configured": bool(settings.SENTRY_DSN),
        "emails_enabled": settings.emails_enabled,
    }

    return env_info


@dev_router.get("/debug/dashboard", response_class=HTMLResponse)
async def debug_dashboard():
    """Development debugging dashboard."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints only available in local environment",
        )

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vulcan Engine - Development Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
            .metric-card { background: #f5f5f5; padding: 10px; border-radius: 3px; }
            button { padding: 8px 16px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; }
            button:hover { background: #0056b3; }
            pre { background: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>🌋 Vulcan Engine - Development Dashboard</h1>

        <div class="section">
            <h2>Quick Actions</h2>
            <button onclick="loadSystemInfo()">Load System Info</button>
            <button onclick="loadHealthStatus()">Check Health</button>
            <button onclick="generateTestData()">Generate Test Data</button>
            <button onclick="startProfiler()">Start Profiler</button>
        </div>

        <div class="section">
            <h2>System Metrics</h2>
            <div id="metrics" class="metrics">Loading...</div>
        </div>

        <div class="section">
            <h2>Health Status</h2>
            <div id="health-status">Click "Check Health" to load...</div>
        </div>

        <div class="section">
            <h2>Environment Info</h2>
            <div id="environment">Loading...</div>
        </div>

        <script>
            async function loadSystemInfo() {
                const response = await fetch('/api/v1/debug/system-info');
                const data = await response.json();
                const metricsDiv = document.getElementById('metrics');
                metricsDiv.innerHTML = `
                    <div class="metric-card">
                        <h4>CPU Usage</h4>
                        <p>${data.system.cpu_percent}%</p>
                    </div>
                    <div class="metric-card">
                        <h4>Memory Usage</h4>
                        <p>${((data.system.memory.used / data.system.memory.total) * 100).toFixed(1)}%</p>
                    </div>
                    <div class="metric-card">
                        <h4>Process Memory</h4>
                        <p>${(data.process.memory_info.rss / 1024 / 1024).toFixed(1)} MB</p>
                    </div>
                    <div class="metric-card">
                        <h4>Threads</h4>
                        <p>${data.process.num_threads}</p>
                    </div>
                `;
            }

            async function loadHealthStatus() {
                const response = await fetch('/health');
                const data = await response.json();
                const healthDiv = document.getElementById('health-status');
                healthDiv.innerHTML = `
                    <p><strong>Overall Status:</strong> ${data.status}</p>
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                `;
            }

            async function generateTestData() {
                const response = await fetch('/api/v1/debug/test-data/scenario?jobs=3&machines=5&operators=8');
                const data = await response.json();
                alert('Test data generated! Check console for details.');
                console.log('Generated test data:', data);
            }

            async function startProfiler() {
                const response = await fetch('/api/v1/debug/profiler/start', { method: 'POST' });
                const data = await response.json();
                alert(`Profiler started! Session ID: ${data.session_id}`);
            }

            async function loadEnvironment() {
                const response = await fetch('/api/v1/debug/environment');
                const data = await response.json();
                const envDiv = document.getElementById('environment');
                envDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            }

            // Load initial data
            loadSystemInfo();
            loadEnvironment();
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


def setup_development_tools():
    """Setup development tools and utilities."""
    if settings.ENVIRONMENT != "local":
        logger.info("Development tools disabled in non-local environment")
        return

    logger.info("Development tools enabled")
    logger.info("Debug dashboard available at: /api/v1/debug/dashboard")
