# Vulcan Engine Developer Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Domain Model](#domain-model)
4. [API Development](#api-development)
5. [Testing Strategy](#testing-strategy)
6. [Extension Points](#extension-points)
7. [Performance Considerations](#performance-considerations)
8. [Contributing Guidelines](#contributing-guidelines)

## Architecture Overview

### System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App]
        MOB[Mobile App]
        API_CLIENT[API Clients]
    end

    subgraph "API Gateway"
        NGINX[Nginx/Traefik]
        AUTH[Auth Service]
    end

    subgraph "Application Layer"
        FASTAPI[FastAPI Server]
        WS[WebSocket Server]
        WORKER[Background Workers]
    end

    subgraph "Domain Layer"
        ENTITIES[Domain Entities]
        SERVICES[Domain Services]
        REPOS[Repository Interfaces]
    end

    subgraph "Infrastructure Layer"
        DB[PostgreSQL]
        REDIS[Redis Cache]
        SOLVER[OR-Tools Solver]
    end

    WEB --> NGINX
    MOB --> NGINX
    API_CLIENT --> NGINX

    NGINX --> AUTH
    NGINX --> FASTAPI
    NGINX --> WS

    FASTAPI --> ENTITIES
    FASTAPI --> SERVICES
    SERVICES --> REPOS

    REPOS --> DB
    SERVICES --> REDIS
    SERVICES --> SOLVER

    WORKER --> SERVICES
```

### Domain-Driven Design

The system follows Domain-Driven Design principles:

```
backend/
├── app/
│   ├── domain/           # Domain layer (pure business logic)
│   │   ├── scheduling/    # Scheduling bounded context
│   │   │   ├── entities/      # Domain entities
│   │   │   ├── value_objects/ # Value objects
│   │   │   ├── services/      # Domain services
│   │   │   └── repositories/  # Repository interfaces
│   │   └── shared/        # Shared kernel
│   ├── application/       # Application services
│   │   └── scheduling/    # Use cases and orchestration
│   ├── infrastructure/    # Infrastructure implementations
│   │   ├── database/      # Database repositories
│   │   ├── solver/        # OR-Tools integration
│   │   └── cache/         # Redis implementation
│   └── api/              # API layer
│       ├── routes/        # FastAPI routes
│       ├── dependencies/  # Dependency injection
│       └── websockets/    # WebSocket handlers
```

### Key Design Patterns

1. **Repository Pattern**: Abstract data access
2. **Factory Pattern**: Complex object creation
3. **Strategy Pattern**: Interchangeable algorithms
4. **Observer Pattern**: Event-driven updates
5. **Dependency Injection**: Loose coupling

## Development Setup

### Prerequisites

```bash
# System requirements
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose
- Git

# Python tools
pip install uv  # Fast Python package manager
```

### Local Development

```bash
# Clone repository
git clone https://github.com/vulcan-engine/backend.git
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
uv sync

# Setup database
docker-compose up -d postgres redis
alembic upgrade head

# Run development server
fastapi dev app/main.py --reload

# Access API
open http://localhost:8000/docs
```

### Docker Development

```bash
# Start full stack with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Watch mode (auto-rebuild on changes)
docker-compose watch

# Run specific service
docker-compose up backend

# Execute commands in container
docker-compose exec backend bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend pytest
```

### Environment Configuration

```bash
# .env.local
DATABASE_URL=postgresql://vulcan:password@localhost:5432/vulcan_dev
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=local-development-secret-key
ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=DEBUG

# Solver settings
SOLVER_MAX_TIME_SECONDS=60
SOLVER_NUM_WORKERS=2

# Development features
ENABLE_METRICS=true
ENABLE_PROFILING=true
ENABLE_DEBUG_TOOLBAR=true
```

## Domain Model

### Core Entities

```python
from domain.scheduling.entities import Job, Task, Machine, Operator, Schedule

# Job: Aggregate root for work orders
job = Job(
    job_number="JOB-2025-001",
    priority=PriorityLevel.HIGH,
    due_date=datetime(2025, 8, 15, 16, 0)
)

# Task: Individual operation within a job
task = Task(
    job_id=job.id,
    operation_number=10,
    machine_options=[
        MachineOption(machine_id=cnc_01.id, duration=Duration(60))
    ],
    skill_requirements=[
        SkillRequirement(SkillType.MACHINING, minimum_level=2)
    ]
)

# Machine: Production resource
machine = Machine(
    name="CNC-01",
    zone="Zone-A",
    skill_requirements=[SkillRequirement(SkillType.MACHINING, 2)],
    is_attended=True
)

# Operator: Human resource with skills
operator = Operator(
    name="John Smith",
    employee_id="EMP001",
    skills=[
        SkillProficiency(SkillType.MACHINING, level=3)
    ]
)

# Schedule: Resource assignments
schedule = Schedule(version=1, calendar=BusinessCalendar.standard())
schedule.assign_task(
    task=task,
    machine_id=machine.id,
    operator_ids=[operator.id],
    start_time=datetime.now(),
    duration=Duration(60)
)
```

### Value Objects

```python
from domain.scheduling.value_objects import (
    Duration, TimeWindow, SkillProficiency, BusinessCalendar
)

# Duration: Immutable time duration
duration = Duration.from_hours(2.5)
total = duration + Duration(30)  # 180 minutes total

# TimeWindow: Time interval
window = TimeWindow(
    start=datetime(2025, 8, 10, 9, 0),
    end=datetime(2025, 8, 10, 11, 0)
)
overlaps = window.overlaps(other_window)

# SkillProficiency: Operator skill level
skill = SkillProficiency(
    skill_type=SkillType.WELDING,
    level=2,
    certified_date=date(2023, 1, 15),
    expiry_date=date(2026, 1, 15)
)
is_valid = skill.is_valid_on(date.today())

# BusinessCalendar: Working hours and holidays
calendar = BusinessCalendar.standard_calendar()
is_working = calendar.is_working_time(datetime.now())
next_available = calendar.next_working_time(datetime.now())
```

### Domain Services

```python
from domain.scheduling.services import (
    SkillMatcher, ScheduleValidator, ResourceAllocator
)

# SkillMatcher: Match operators to machines
skill_matcher = SkillMatcher()
qualified_operators = skill_matcher.find_qualified_operators(
    machine=machine,
    operators=all_operators,
    check_date=date.today()
)

# ScheduleValidator: Validate schedule constraints
validator = ScheduleValidator(calendar)
is_valid, violations = validator.validate_complete(job, schedule)

# ResourceAllocator: Allocate resources to tasks
allocator = ResourceAllocator(machines, operators, skill_matcher)
allocation = allocator.allocate_resources_for_task(
    task=task,
    schedule=schedule,
    preferred_start=datetime.now()
)
```

## API Development

### Creating New Endpoints

```python
# app/api/routes/custom_scheduling.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.domain.scheduling.services import SchedulingService
from app.schemas.scheduling import ScheduleRequest, ScheduleResponse

router = APIRouter(prefix="/custom", tags=["custom-scheduling"])

@router.post("/optimize", response_model=ScheduleResponse)
async def optimize_schedule(
    request: ScheduleRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create optimized schedule with custom constraints.

    - **request**: Scheduling problem definition
    - **return**: Optimized schedule with assignments
    """
    try:
        # Initialize service
        service = SchedulingService(db)

        # Validate request
        validation_errors = service.validate_request(request)
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": validation_errors}
            )

        # Solve scheduling problem
        schedule = await service.optimize_schedule(
            jobs=request.jobs,
            resources=request.resources,
            constraints=request.constraints,
            objectives=request.objectives
        )

        # Return response
        return ScheduleResponse.from_domain(schedule)

    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Scheduling failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scheduling optimization failed"
        )
```

### Request/Response Schemas

```python
# app/schemas/scheduling.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID

class TaskRequest(BaseModel):
    operation_number: int = Field(..., ge=0)
    machine_options: List[str]
    duration_minutes: int = Field(..., gt=0)
    skill_requirements: Dict[str, int]
    predecessors: List[str] = []

    @validator('skill_requirements')
    def validate_skill_levels(cls, v):
        for skill, level in v.items():
            if level not in [1, 2, 3]:
                raise ValueError(f"Skill level must be 1-3, got {level}")
        return v

class JobRequest(BaseModel):
    job_number: str = Field(..., min_length=1, max_length=50)
    tasks: List[TaskRequest]
    priority: int = Field(0, ge=0, le=2)
    due_date: Optional[datetime] = None

    @validator('due_date')
    def validate_future_date(cls, v):
        if v and v < datetime.now():
            raise ValueError("Due date must be in the future")
        return v

class ScheduleRequest(BaseModel):
    jobs: List[JobRequest]
    optimization_time_limit: int = Field(60, ge=1, le=600)
    objectives: Dict[str, float] = {
        "makespan": 0.4,
        "cost": 0.3,
        "tardiness": 0.3
    }

    @validator('objectives')
    def validate_weights(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Objective weights must sum to 1.0, got {total}")
        return v

class ScheduleResponse(BaseModel):
    schedule_id: UUID
    status: str
    makespan_hours: float
    total_cost: float
    assignments: List[Dict]
    metrics: Dict[str, Any]

    class Config:
        orm_mode = True
```

### Dependency Injection

```python
# app/api/deps.py
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import SessionLocal
from app.domain.scheduling.repositories import JobRepository
from app.infrastructure.database.repositories import SQLJobRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token")

def get_db() -> Generator:
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Get current authenticated user."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user

def get_job_repository(db: Session = Depends(get_db)) -> JobRepository:
    """Get job repository instance."""
    return SQLJobRepository(db)

def get_solver_service():
    """Get solver service instance."""
    from app.infrastructure.solver import ORToolsSolver
    return ORToolsSolver(
        max_time_seconds=settings.SOLVER_MAX_TIME_SECONDS,
        num_workers=settings.SOLVER_NUM_WORKERS
    )
```

### WebSocket Implementation

```python
# app/api/websockets.py
from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]

    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except:
                    dead_connections.add(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.active_connections[channel].discard(conn)

manager = ConnectionManager()

@router.websocket("/ws/schedule/{schedule_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    schedule_id: str,
    token: str = Query(None)
):
    # Verify authentication
    if not verify_token(token):
        await websocket.close(code=1008)
        return

    channel = f"schedule.{schedule_id}"
    await manager.connect(websocket, channel)

    try:
        # Send initial status
        await websocket.send_json({
            "event": "connected",
            "channel": channel
        })

        # Keep connection alive
        while True:
            # Wait for messages
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "ping":
                await websocket.send_json({"event": "pong"})
            elif message.get("action") == "subscribe":
                # Handle subscription
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
```

## Testing Strategy

### Unit Tests

```python
# tests/domain/test_entities.py
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.domain.scheduling.entities import Job, Task
from app.domain.scheduling.value_objects import Duration

class TestJob:
    def test_create_job(self):
        """Test job creation with valid data."""
        job = Job(
            job_number="JOB-001",
            priority=1,
            due_date=datetime.now() + timedelta(days=7)
        )

        assert job.job_number == "JOB-001"
        assert job.priority == 1
        assert job.due_date is not None

    def test_add_task(self):
        """Test adding tasks to job."""
        job = Job(job_number="JOB-001")

        task1 = Task(
            job_id=job.id,
            operation_number=10,
            machine_options=[],
            skill_requirements=[]
        )

        job.add_task(task1)

        assert len(job.get_tasks_in_sequence()) == 1
        assert job.get_task(task1.id) == task1

    def test_task_sequencing(self):
        """Test tasks are ordered by operation number."""
        job = Job(job_number="JOB-001")

        # Add tasks out of order
        task20 = Task(job_id=job.id, operation_number=20)
        task10 = Task(job_id=job.id, operation_number=10)
        task30 = Task(job_id=job.id, operation_number=30)

        job.add_task(task20)
        job.add_task(task10)
        job.add_task(task30)

        tasks = job.get_tasks_in_sequence()
        assert tasks[0].operation_number == 10
        assert tasks[1].operation_number == 20
        assert tasks[2].operation_number == 30

    def test_invalid_priority(self):
        """Test job creation with invalid priority."""
        with pytest.raises(ValueError):
            Job(job_number="JOB-001", priority=-1)
```

### Integration Tests

```python
# tests/api/test_scheduling.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from app.main import app
from app.core.database import get_db
from tests.utils import create_test_user, get_auth_headers

client = TestClient(app)

class TestSchedulingAPI:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test data."""
        self.user = create_test_user(db)
        self.headers = get_auth_headers(self.user)

    def test_create_standard_job(self, db):
        """Test creating a standard job."""
        response = client.post(
            "/api/v1/scheduling/domain/jobs/standard",
            json={
                "job_number": "TEST-001",
                "operation_count": 10,
                "priority": 1,
                "due_date": (datetime.now() + timedelta(days=7)).isoformat()
            },
            headers=self.headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_number"] == "TEST-001"
        assert data["task_count"] == 10

    def test_solve_scheduling_problem(self, db):
        """Test solving a scheduling problem."""
        # Create test data
        problem = {
            "jobs": [...],
            "machines": [...],
            "operators": [...],
            "optimization_parameters": {
                "max_solving_time": 10
            }
        }

        response = client.post(
            "/api/v1/scheduling/solve",
            json=problem,
            headers=self.headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "schedule_id" in data
        assert data["status"] in ["optimal", "feasible"]

    @pytest.mark.asyncio
    async def test_websocket_updates(self, db):
        """Test WebSocket schedule updates."""
        from fastapi.testclient import TestClient

        with client.websocket_connect(
            f"/ws/schedule/test-schedule?token={self.user.token}"
        ) as websocket:
            # Receive initial connection message
            data = websocket.receive_json()
            assert data["event"] == "connected"

            # Send ping
            websocket.send_json({"action": "ping"})

            # Receive pong
            data = websocket.receive_json()
            assert data["event"] == "pong"
```

### Performance Tests

```python
# tests/performance/test_solver.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

from app.infrastructure.solver import ORToolsSolver
from tests.factories import create_large_problem

class TestSolverPerformance:
    @pytest.mark.performance
    def test_large_problem_solving(self):
        """Test solver performance with large problem."""
        problem = create_large_problem(
            num_jobs=50,
            tasks_per_job=100,
            num_machines=20,
            num_operators=30
        )

        solver = ORToolsSolver(max_time_seconds=60)

        start_time = time.time()
        solution = solver.solve(problem)
        solve_time = time.time() - start_time

        assert solution is not None
        assert solve_time < 60
        print(f"Solved in {solve_time:.2f} seconds")
        print(f"Makespan: {solution.makespan_hours} hours")

    @pytest.mark.performance
    def test_concurrent_solving(self):
        """Test multiple concurrent solve requests."""
        problems = [
            create_large_problem(num_jobs=10)
            for _ in range(5)
        ]

        solver = ORToolsSolver()

        with ThreadPoolExecutor(max_workers=5) as executor:
            start_time = time.time()
            futures = [
                executor.submit(solver.solve, problem)
                for problem in problems
            ]

            solutions = [f.result() for f in futures]
            total_time = time.time() - start_time

        assert all(s is not None for s in solutions)
        assert total_time < 30  # Should complete in 30 seconds
        print(f"Solved {len(problems)} problems in {total_time:.2f}s")
```

## Extension Points

### Custom Constraints

```python
# app/domain/scheduling/constraints/custom.py
from abc import ABC, abstractmethod
from typing import List
from ortools.sat.python import cp_model

class SchedulingConstraint(ABC):
    """Base class for custom scheduling constraints."""

    @abstractmethod
    def apply(self, model: cp_model.CpModel, variables: dict):
        """Apply constraint to the model."""
        pass

class SequenceDependentSetupConstraint(SchedulingConstraint):
    """Constraint for sequence-dependent setup times."""

    def __init__(self, setup_matrix: dict):
        self.setup_matrix = setup_matrix

    def apply(self, model: cp_model.CpModel, variables: dict):
        """Apply sequence-dependent setup constraints."""
        for machine_id, tasks in variables['machine_tasks'].items():
            for i in range(len(tasks) - 1):
                task1 = tasks[i]
                task2 = tasks[i + 1]

                # Get setup time from matrix
                setup_time = self.setup_matrix.get(
                    (task1.product_type, task2.product_type),
                    0
                )

                # Add constraint: task2 starts after task1 ends + setup
                model.Add(
                    variables['starts'][task2] >=
                    variables['ends'][task1] + setup_time
                )

class PreferredTimeWindowConstraint(SchedulingConstraint):
    """Soft constraint for preferred time windows."""

    def __init__(self, preferences: dict, penalty_weight: int = 100):
        self.preferences = preferences
        self.penalty_weight = penalty_weight

    def apply(self, model: cp_model.CpModel, variables: dict):
        """Apply preferred time window constraints."""
        penalties = []

        for task_id, window in self.preferences.items():
            if task_id in variables['starts']:
                # Create boolean for within window
                in_window = model.NewBoolVar(f'in_window_{task_id}')

                # Task starts within preferred window
                model.Add(
                    variables['starts'][task_id] >= window.start
                ).OnlyEnforceIf(in_window)
                model.Add(
                    variables['starts'][task_id] <= window.end
                ).OnlyEnforceIf(in_window)

                # Add penalty if not in window
                penalty = model.NewIntVar(0, self.penalty_weight, f'penalty_{task_id}')
                model.Add(penalty == self.penalty_weight).OnlyEnforceIf(in_window.Not())
                model.Add(penalty == 0).OnlyEnforceIf(in_window)

                penalties.append(penalty)

        # Add to objective
        if penalties:
            variables['objectives']['window_penalties'] = sum(penalties)

# Usage
solver = CustomSolver()
solver.add_constraint(SequenceDependentSetupConstraint(setup_matrix))
solver.add_constraint(PreferredTimeWindowConstraint(preferences))
```

### Custom Objectives

```python
# app/domain/scheduling/objectives/custom.py
class CustomObjective(ABC):
    """Base class for custom optimization objectives."""

    @abstractmethod
    def calculate(self, model: cp_model.CpModel, variables: dict) -> cp_model.IntVar:
        """Calculate objective value."""
        pass

class MinimizeChangeovers(CustomObjective):
    """Minimize product changeovers on machines."""

    def calculate(self, model: cp_model.CpModel, variables: dict):
        changeovers = []

        for machine_id, tasks in variables['machine_tasks'].items():
            for i in range(len(tasks) - 1):
                # Check if products are different
                is_changeover = model.NewBoolVar(f'changeover_{machine_id}_{i}')

                if tasks[i].product != tasks[i+1].product:
                    model.Add(is_changeover == 1)
                else:
                    model.Add(is_changeover == 0)

                changeovers.append(is_changeover)

        return sum(changeovers)

class BalanceWorkload(CustomObjective):
    """Balance workload across operators."""

    def calculate(self, model: cp_model.CpModel, variables: dict):
        operator_loads = {}

        for op_id in variables['operators']:
            # Calculate total work time for operator
            work_time = sum(
                variables['durations'][task] * variables['assignments'][(task, op_id)]
                for task in variables['tasks']
                if (task, op_id) in variables['assignments']
            )
            operator_loads[op_id] = work_time

        # Calculate variance
        mean_load = sum(operator_loads.values()) // len(operator_loads)
        variance = sum(
            model.NewIntVar(0, 10000, f'var_{op}')
            for op in operator_loads
        )

        for op_id, load in operator_loads.items():
            diff = load - mean_load
            model.AddMultiplicationEquality(
                variables[f'var_{op_id}'],
                [diff, diff]
            )

        return variance
```

### Plugin System

```python
# app/core/plugins.py
from typing import Protocol, List, Dict, Any
from importlib import import_module
import os

class SchedulingPlugin(Protocol):
    """Protocol for scheduling plugins."""

    name: str
    version: str

    def initialize(self, config: Dict[str, Any]):
        """Initialize plugin with configuration."""
        ...

    def pre_solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-process problem before solving."""
        ...

    def post_solve(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process solution after solving."""
        ...

class PluginManager:
    """Manage scheduling plugins."""

    def __init__(self):
        self.plugins: Dict[str, SchedulingPlugin] = {}

    def load_plugins(self, plugin_dir: str = "plugins"):
        """Load all plugins from directory."""
        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                module = import_module(f"{plugin_dir}.{module_name}")

                # Find plugin class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, SchedulingPlugin) and
                        attr != SchedulingPlugin):

                        plugin = attr()
                        self.plugins[plugin.name] = plugin
                        print(f"Loaded plugin: {plugin.name} v{plugin.version}")

    def execute_pre_solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """Execute pre-solve hooks for all plugins."""
        for plugin in self.plugins.values():
            problem = plugin.pre_solve(problem)
        return problem

    def execute_post_solve(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Execute post-solve hooks for all plugins."""
        for plugin in self.plugins.values():
            solution = plugin.post_solve(solution)
        return solution

# Example plugin
class MaintenancePlugin:
    """Plugin to handle preventive maintenance scheduling."""

    name = "maintenance"
    version = "1.0.0"

    def initialize(self, config: Dict[str, Any]):
        self.maintenance_interval = config.get("interval_hours", 168)

    def pre_solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """Add maintenance tasks to problem."""
        for machine in problem.get("machines", []):
            # Add maintenance task every week
            maintenance_task = {
                "id": f"maint_{machine['id']}",
                "type": "maintenance",
                "machine_id": machine["id"],
                "duration": 120,  # 2 hours
                "fixed_time": True,
                "recurrence": "weekly"
            }
            problem.setdefault("maintenance_tasks", []).append(maintenance_task)

        return problem

    def post_solve(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Add maintenance windows to solution."""
        maintenance_windows = []

        for assignment in solution.get("assignments", []):
            if assignment.get("task_type") == "maintenance":
                maintenance_windows.append({
                    "machine_id": assignment["machine_id"],
                    "start": assignment["start"],
                    "end": assignment["end"],
                    "type": "preventive"
                })

        solution["maintenance_windows"] = maintenance_windows
        return solution
```

## Performance Considerations

### Query Optimization

```python
# app/infrastructure/database/optimized_queries.py
from sqlalchemy import and_, or_, exists, select, func
from sqlalchemy.orm import selectinload, joinedload, subqueryload

class OptimizedJobRepository:
    """Repository with optimized queries."""

    def get_jobs_with_tasks(self, job_ids: List[UUID]):
        """Get jobs with tasks using eager loading."""
        return (
            self.db.query(JobModel)
            .options(
                selectinload(JobModel.tasks)
                .selectinload(TaskModel.machine_options)
            )
            .filter(JobModel.id.in_(job_ids))
            .all()
        )

    def get_available_machines(self, time_window: TimeWindow):
        """Get available machines using efficient filtering."""
        # Subquery for busy machines
        busy_machines = (
            self.db.query(AssignmentModel.machine_id)
            .filter(
                and_(
                    AssignmentModel.start_time < time_window.end,
                    AssignmentModel.end_time > time_window.start
                )
            )
            .subquery()
        )

        # Main query excluding busy machines
        return (
            self.db.query(MachineModel)
            .filter(
                ~MachineModel.id.in_(select(busy_machines)),
                MachineModel.is_available == True
            )
            .all()
        )

    def get_schedule_summary(self, schedule_id: UUID):
        """Get schedule summary with aggregated data."""
        return (
            self.db.query(
                ScheduleModel.id,
                ScheduleModel.version,
                func.count(AssignmentModel.id).label('total_assignments'),
                func.min(AssignmentModel.start_time).label('start_time'),
                func.max(AssignmentModel.end_time).label('end_time'),
                func.count(distinct(AssignmentModel.machine_id)).label('machines_used'),
                func.count(distinct(AssignmentModel.operator_id)).label('operators_used')
            )
            .join(AssignmentModel)
            .filter(ScheduleModel.id == schedule_id)
            .group_by(ScheduleModel.id, ScheduleModel.version)
            .first()
        )
```

### Caching Strategy

```python
# app/infrastructure/cache/cache_manager.py
from functools import lru_cache, wraps
from typing import Optional, Callable
import hashlib
import json
import redis

class CacheManager:
    """Manage application caching."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.default_ttl = 300  # 5 minutes

    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = {"args": args, "kwargs": kwargs}
        key_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
        return f"{prefix}:{key_hash}"

    def cached(
        self,
        prefix: str,
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
    ):
        """Decorator for caching function results."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self.cache_key(prefix, *args, **kwargs)

                # Try to get from cache
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)

                # Execute function
                result = await func(*args, **kwargs)

                # Store in cache
                self.redis.setex(
                    cache_key,
                    ttl or self.default_ttl,
                    json.dumps(result)
                )

                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Similar logic for synchronous functions
                cache_key = self.cache_key(prefix, *args, **kwargs)
                cached = self.redis.get(cache_key)

                if cached:
                    return json.loads(cached)

                result = func(*args, **kwargs)
                self.redis.setex(
                    cache_key,
                    ttl or self.default_ttl,
                    json.dumps(result)
                )

                return result

            # Return appropriate wrapper
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    def invalidate(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)

# Usage
cache_manager = CacheManager(redis_client)

@cache_manager.cached("machine_availability", ttl=600)
async def get_machine_availability(machine_id: str, date: str):
    # Expensive database query
    pass

# Invalidate related cache
cache_manager.invalidate("machine_availability:*")
```

### Async Processing

```python
# app/core/async_processing.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Coroutine

class AsyncProcessor:
    """Handle asynchronous processing."""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def run_in_executor(self, func, *args):
        """Run blocking function in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)

    async def gather_with_concurrency(
        self,
        tasks: List[Coroutine],
        max_concurrent: int = 10
    ):
        """Execute tasks with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_task(task):
            async with semaphore:
                return await task

        return await asyncio.gather(
            *[bounded_task(task) for task in tasks]
        )

    async def batch_process(
        self,
        items: List,
        processor: Callable,
        batch_size: int = 100
    ):
        """Process items in batches."""
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[processor(item) for item in batch]
            )
            results.extend(batch_results)

            # Brief pause between batches
            await asyncio.sleep(0.1)

        return results

# Usage
processor = AsyncProcessor()

# Run CPU-intensive solver in executor
solution = await processor.run_in_executor(
    solver.solve,
    problem
)

# Process multiple schedules concurrently
schedules = await processor.gather_with_concurrency(
    [optimize_schedule(job) for job in jobs],
    max_concurrent=5
)
```

## Contributing Guidelines

### Code Style

```python
# Follow PEP 8 and use type hints
from typing import List, Optional, Dict, Any
from datetime import datetime

def calculate_makespan(
    tasks: List[Task],
    assignments: Dict[str, Assignment],
    calendar: Optional[BusinessCalendar] = None
) -> float:
    """
    Calculate makespan for scheduled tasks.

    Args:
        tasks: List of tasks to consider
        assignments: Task assignments with start/end times
        calendar: Business calendar for working hours

    Returns:
        Makespan in hours

    Raises:
        ValueError: If tasks have no assignments
    """
    if not assignments:
        raise ValueError("No assignments provided")

    earliest_start = min(a.start_time for a in assignments.values())
    latest_end = max(a.end_time for a in assignments.values())

    if calendar:
        # Adjust for business hours
        return calendar.working_hours_between(earliest_start, latest_end)
    else:
        # Raw time difference
        return (latest_end - earliest_start).total_seconds() / 3600
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-constraint

# Make changes and commit
git add .
git commit -m "feat: Add sequence-dependent setup constraint

- Implement SequenceDependentSetupConstraint class
- Add setup time matrix support
- Include tests for new constraint"

# Push and create PR
git push origin feature/new-constraint

# After review and approval, merge
git checkout main
git merge --no-ff feature/new-constraint
git push origin main
```

### Documentation

```python
"""
Module: scheduling.constraints.sequence

This module implements sequence-dependent constraints for scheduling.

Classes:
    SequenceDependentSetupConstraint: Enforces setup times between tasks

Example:
    >>> from scheduling.constraints import SequenceDependentSetupConstraint
    >>>
    >>> setup_matrix = {
    >>>     ('A', 'B'): 30,
    >>>     ('B', 'A'): 45,
    >>>     ('B', 'C'): 15
    >>> }
    >>> constraint = SequenceDependentSetupConstraint(setup_matrix)
    >>> model.add_constraint(constraint)
"""
```

### Testing Requirements

```python
# Every new feature needs:
# 1. Unit tests (test isolated functionality)
# 2. Integration tests (test with other components)
# 3. Performance tests (for critical paths)
# 4. Documentation tests (doctests for examples)

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest -m "not performance"  # Skip performance tests
pytest -m integration  # Only integration tests

# Run mutation testing
mutmut run --paths-to-mutate=app/domain

# Run type checking
mypy app

# Run linting
ruff check app
black --check app
```
