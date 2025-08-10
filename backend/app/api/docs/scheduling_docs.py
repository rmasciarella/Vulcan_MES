"""
API Documentation for Scheduling Domain

Comprehensive OpenAPI documentation for the scheduling domain functionality.
Provides detailed descriptions, examples, and response schemas.
"""

from typing import Any

# OpenAPI tags for better organization
SCHEDULING_TAGS = [
    {
        "name": "scheduling",
        "description": "Core scheduling operations including jobs, tasks, and resources",
    },
    {
        "name": "domain-scheduling",
        "description": "Domain-driven scheduling features using rich domain models and services",
    },
    {
        "name": "websockets",
        "description": "WebSocket endpoints for real-time scheduling updates and notifications",
    },
]

# Enhanced OpenAPI documentation
SCHEDULING_OPENAPI_EXTRAS = {
    "info": {
        "title": "Vulcan Engine Scheduling API",
        "description": """
# Manufacturing Scheduling Domain API

This API provides comprehensive scheduling functionality for manufacturing operations,
built using Domain-Driven Design principles.

## Key Features

- **Job Management**: Create and manage manufacturing jobs with complex operation sequences
- **Resource Scheduling**: Optimize allocation of machines and operators based on skills and availability
- **Real-time Updates**: WebSocket support for live scheduling dashboard integration
- **Constraint Validation**: Comprehensive business rule validation for feasible schedules
- **Critical Path Analysis**: Identify bottlenecks and optimize production flow

## Domain Model

The API exposes a rich domain model including:

### Entities
- **Job**: Aggregate root for manufacturing work orders
- **Task**: Individual operations within jobs
- **Machine**: Production equipment with capabilities
- **Operator**: Workers with specific skill sets
- **Schedule**: Resource allocation and timing coordination

### Value Objects
- **Duration**: High-precision time calculations using Decimal arithmetic
- **MachineOption**: Flexible routing options for tasks
- **SkillProficiency**: Operator capabilities with certification tracking
- **BusinessCalendar**: Working hours and holiday management
- **TimeWindow**: Time interval calculations with overlap detection

### Domain Services
- **SkillMatcher**: Match operators to machines based on skill requirements
- **CriticalSequenceManager**: Analyze and optimize critical path operations
- **ScheduleValidator**: Comprehensive constraint checking

## API Organization

### Core Scheduling (`/scheduling/`)
Infrastructure-focused endpoints for basic CRUD operations and data access.

### Domain Scheduling (`/scheduling/domain/`)
Domain-driven endpoints exposing rich business logic and domain services.

### WebSocket Support (`/ws/`)
Real-time event streaming for live scheduling dashboards and notifications.

## Authentication

All endpoints require appropriate authentication. See the authentication documentation for details.

## Rate Limiting

API requests are rate-limited to ensure system stability. See individual endpoint documentation for specific limits.
        """,
        "version": "1.0.0",
        "contact": {
            "name": "Vulcan Engine API Support",
            "email": "support@vulcanengine.com",
        },
    },
    "servers": [
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.vulcanengine.com", "description": "Production server"},
    ],
}

# Detailed response examples
RESPONSE_EXAMPLES = {
    "job_summary": {
        "summary": "Job Summary Example",
        "value": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "job_number": "JOB-2024-001",
            "task_count": 100,
            "priority": "normal",
            "due_date": "2024-12-31T23:59:59",
            "critical_task_count": 10,
            "estimated_duration_hours": 168.5,
        },
    },
    "business_calendar": {
        "summary": "Business Calendar Response",
        "value": {
            "is_working_time": True,
            "next_working_time": None,
            "calendar_description": "Mon-Fri: 07:00 - 16:00",
        },
    },
    "skill_analysis": {
        "summary": "Skill Analysis Response",
        "value": {
            "operators_analyzed": 25,
            "total_skills": 47,
            "skill_gaps": [
                {
                    "skill_type": "welding",
                    "required_level": 3,
                    "operators_with_gap": 8,
                    "training_priority": "high",
                }
            ],
            "training_priorities": [
                {"skill_type": "inspection", "gap_count": 12, "urgency": "critical"}
            ],
            "coverage_percentage": 85.5,
        },
    },
    "critical_path": {
        "summary": "Critical Path Analysis",
        "value": {
            "critical_sequences_count": 3,
            "total_critical_tasks": 23,
            "critical_path_duration_hours": 48.2,
            "bottleneck_operations": [
                {
                    "operation_type": "precision_machining",
                    "bottleneck_severity": "high",
                    "affected_jobs": 5,
                }
            ],
        },
    },
    "validation_result": {
        "summary": "Schedule Validation Result",
        "value": {
            "is_valid": False,
            "violations": [
                "Task T-001 starts before predecessor T-002 completes",
                "Machine M-005 has overlapping assignments",
            ],
            "warnings": ["Job JOB-001 may miss due date by 2.5 hours"],
            "validation_timestamp": "2024-08-07T10:30:00Z",
        },
    },
    "websocket_stats": {
        "summary": "WebSocket Connection Statistics",
        "value": {
            "total_connections": 8,
            "topic_subscriptions": {
                "all": 3,
                "tasks": 4,
                "jobs": 2,
                "resources": 1,
                "critical_path": 2,
            },
            "connections": {
                "schedule_1691404200": {
                    "connected_at": "2024-08-07T10:30:00Z",
                    "topics": ["all", "tasks"],
                    "messages_sent": 47,
                }
            },
        },
    },
}

# Error response schemas
ERROR_RESPONSES = {
    400: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "Validation Error",
                    "message": "Invalid job_number: must be non-empty string",
                    "details": {
                        "field": "job_number",
                        "value": "",
                        "error_code": "VALIDATION_ERROR",
                    },
                }
            }
        },
    },
    422: {
        "description": "Business Rule Violation",
        "content": {
            "application/json": {
                "example": {
                    "error": "Business Rule Violation",
                    "message": "Cannot schedule task before predecessors complete",
                    "details": {
                        "rule": "precedence_constraint",
                        "violated_by": "task_id_123",
                    },
                }
            }
        },
    },
    409: {
        "description": "Resource Conflict",
        "content": {
            "application/json": {
                "example": {
                    "error": "Resource Conflict",
                    "message": "Machine M-001 is already allocated during this time period",
                    "details": {
                        "resource_type": "machine",
                        "resource_id": "M-001",
                        "conflict_period": "2024-08-07T10:00:00Z to 2024-08-07T12:00:00Z",
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            }
        },
    },
}

# WebSocket message schemas
WEBSOCKET_MESSAGE_EXAMPLES = {
    "connection_established": {
        "type": "connection_established",
        "connection_id": "schedule_1691404200",
        "subscribed_topics": ["all", "tasks", "jobs"],
        "timestamp": "2024-08-07T10:30:00Z",
    },
    "domain_event": {
        "type": "domain_event",
        "event_type": "TaskScheduled",
        "event_id": "evt_550e8400-e29b-41d4-a716-446655440000",
        "occurred_at": "2024-08-07T10:30:15Z",
        "aggregate_id": "job_550e8400-e29b-41d4-a716-446655440001",
        "topic": "tasks",
        "data": {
            "task_id": "task_550e8400-e29b-41d4-a716-446655440002",
            "job_id": "job_550e8400-e29b-41d4-a716-446655440001",
            "machine_id": "machine_001",
            "operator_ids": ["operator_001", "operator_002"],
            "planned_start": "2024-08-07T14:00:00Z",
            "planned_end": "2024-08-07T16:30:00Z",
        },
    },
    "client_message": {"type": "ping", "timestamp": "2024-08-07T10:30:00Z"},
    "server_response": {"type": "pong", "timestamp": "2024-08-07T10:30:01Z"},
}

# Documentation strings for complex domain concepts
DOMAIN_CONCEPT_DOCS = {
    "job_factory": """
    ## Job Factory Patterns

    The JobFactory provides several factory methods for creating jobs with different characteristics:

    - **create_standard_job()**: Creates a job with 100 operations, 90% single machine options, 10% dual options
    - **create_rush_job()**: High-priority job with reduced processing times for urgent orders
    - **create_complex_job()**: Large job with varied skill requirements and multiple machine options
    - **create_simple_job()**: Basic job with minimal complexity for testing or training

    Each factory method ensures proper domain model consistency and business rule compliance.
    """,
    "skill_system": """
    ## Skill Management System

    The skill system models operator capabilities and machine requirements:

    ### Skill Types
    - MACHINING: CNC operation, manual machining
    - WELDING: Arc welding, TIG welding, MIG welding
    - INSPECTION: Quality control, dimensional inspection
    - ASSEMBLY: Component assembly, final assembly
    - PROGRAMMING: CNC programming, robot programming

    ### Proficiency Levels
    - Level 1: Basic/Beginner
    - Level 2: Intermediate
    - Level 3: Expert/Advanced

    Skills include certification dates and expiry tracking for compliance management.
    """,
    "business_calendar": """
    ## Business Calendar System

    Manages working hours and holiday schedules for accurate scheduling:

    ### Standard Calendar
    - Monday-Friday: 7:00 AM - 4:00 PM
    - Weekends: Non-working
    - Configurable lunch breaks and holidays

    ### Calendar Validation
    - Ensures tasks are scheduled during working hours
    - Automatically adjusts schedule times to next working period
    - Validates against holiday calendars and maintenance windows
    """,
    "critical_path": """
    ## Critical Path Management

    Identifies and manages critical sequences that determine project duration:

    ### Critical Sequence Identification
    - Analyzes task dependencies and durations
    - Identifies bottleneck operations and resources
    - Calculates critical path duration and slack time

    ### Bottleneck Analysis
    - Resource utilization patterns
    - Skill constraint analysis
    - Machine capacity optimization opportunities
    """,
    "real_time_updates": """
    ## Real-Time WebSocket Updates

    WebSocket endpoints provide live updates for scheduling dashboards:

    ### Event Topics
    - **all**: All scheduling events
    - **tasks**: Task status and assignment changes
    - **jobs**: Job progress and delay notifications
    - **resources**: Resource allocation and conflicts
    - **critical_path**: Critical path and bottleneck updates

    ### Message Types
    - **domain_event**: Business events from domain model
    - **connection_established**: Initial connection confirmation
    - **ping/pong**: Connection keepalive
    - **error**: Error notifications and validation failures
    """,
}


def get_enhanced_openapi_schema(base_schema: dict[str, Any]) -> dict[str, Any]:
    """Enhance the base OpenAPI schema with scheduling-specific documentation."""

    # Add scheduling tags
    if "tags" not in base_schema:
        base_schema["tags"] = []
    base_schema["tags"].extend(SCHEDULING_TAGS)

    # Enhance info section
    if "info" in base_schema and "info" in SCHEDULING_OPENAPI_EXTRAS:
        base_schema["info"].update(SCHEDULING_OPENAPI_EXTRAS["info"])

    # Add servers if not present
    if "servers" not in base_schema and "servers" in SCHEDULING_OPENAPI_EXTRAS:
        base_schema["servers"] = SCHEDULING_OPENAPI_EXTRAS["servers"]

    # Add custom components
    if "components" not in base_schema:
        base_schema["components"] = {}

    if "examples" not in base_schema["components"]:
        base_schema["components"]["examples"] = {}

    base_schema["components"]["examples"].update(RESPONSE_EXAMPLES)

    return base_schema
