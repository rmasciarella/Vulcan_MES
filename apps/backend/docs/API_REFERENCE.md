# Vulcan Engine API Reference

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Domain Models](#domain-models)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [WebSocket Events](#websocket-events)

## Overview

The Vulcan Engine API provides a comprehensive scheduling optimization service for manufacturing execution systems. It offers endpoints for job creation, schedule optimization, resource management, and real-time schedule monitoring.

### Base URL

```
Production: https://api.vulcan-engine.com/api/v1
Staging: https://staging-api.vulcan-engine.com/api/v1
Development: http://localhost:8000/api/v1
```

### API Version

Current Version: `1.0.0`

The API uses semantic versioning. Breaking changes will result in a new major version.

### Content Types

- Request: `application/json`
- Response: `application/json`
- WebSocket: `application/json`

## Authentication

The API uses JWT (JSON Web Token) authentication with refresh tokens.

### Obtaining Tokens

#### Login

```http
POST /login/access-token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secret
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Using Tokens

Include the access token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Token Refresh

```http
POST /login/refresh
Authorization: Bearer {refresh_token}
```

### Token Expiry

- Access Token: 30 minutes
- Refresh Token: 7 days

## API Endpoints

### Health & Monitoring

#### Health Check

```http
GET /health
```

Returns system health status and component availability.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-07T10:30:00Z",
  "checks": {
    "database": "healthy",
    "solver": "healthy",
    "cache": "healthy"
  },
  "version": "1.0.0",
  "environment": "production"
}
```

#### Metrics

```http
GET /metrics
```

Returns Prometheus-formatted metrics for monitoring.

### Scheduling Operations

#### Create Standard Job

```http
POST /scheduling/domain/jobs/standard
Content-Type: application/json
Authorization: Bearer {token}

{
  "job_number": "JOB-2025-001",
  "operation_count": 100,
  "priority": 1,
  "due_date": "2025-08-15T16:00:00Z"
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "job_number": "JOB-2025-001",
  "task_count": 100,
  "priority": "HIGH",
  "due_date": "2025-08-15T16:00:00Z",
  "critical_task_count": 10,
  "estimated_duration_hours": 45.5
}
```

#### Submit Scheduling Problem

```http
POST /scheduling/solve
Content-Type: application/json
Authorization: Bearer {token}

{
  "problem": {
    "jobs": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "job_number": "JOB-2025-001",
        "tasks": [
          {
            "id": "task-001",
            "operation_number": 10,
            "machine_options": [
              {
                "machine_id": "cnc-01",
                "setup_duration": 15,
                "processing_duration": 45,
                "requires_operator_full_duration": true
              }
            ],
            "skill_requirements": [
              {
                "skill_type": "MACHINING",
                "minimum_level": 2
              }
            ],
            "predecessor_ids": []
          }
        ],
        "priority": 1,
        "due_date": "2025-08-15T16:00:00Z"
      }
    ],
    "machines": [
      {
        "id": "cnc-01",
        "name": "CNC Machine 01",
        "zone": "Zone-A",
        "skill_requirements": [
          {
            "skill_type": "MACHINING",
            "minimum_level": 2
          }
        ],
        "is_attended": true,
        "is_available": true
      }
    ],
    "operators": [
      {
        "id": "op-001",
        "name": "John Smith",
        "employee_id": "EMP001",
        "skills": [
          {
            "skill_type": "MACHINING",
            "level": 3,
            "certified_date": "2023-01-15",
            "expiry_date": "2026-01-15"
          }
        ],
        "shift_pattern": "day"
      }
    ],
    "calendar": {
      "weekday_hours": {
        "0": {"start_time": "07:00", "end_time": "16:00"},
        "1": {"start_time": "07:00", "end_time": "16:00"},
        "2": {"start_time": "07:00", "end_time": "16:00"},
        "3": {"start_time": "07:00", "end_time": "16:00"},
        "4": {"start_time": "07:00", "end_time": "16:00"}
      },
      "holidays": ["2025-12-25", "2025-12-26"]
    }
  },
  "optimization_parameters": {
    "max_solving_time": 300,
    "objective_weights": {
      "makespan": 0.4,
      "total_cost": 0.3,
      "tardiness": 0.3
    },
    "enable_parallelization": true
  }
}
```

**Response:**
```json
{
  "schedule_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "optimal",
  "solving_time_seconds": 45.2,
  "makespan_hours": 120.5,
  "total_cost": 15000.00,
  "utilization_rates": {
    "machines": 0.85,
    "operators": 0.78
  },
  "assignments": [
    {
      "task_id": "task-001",
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "machine_id": "cnc-01",
      "operator_ids": ["op-001"],
      "planned_start": "2025-08-08T07:00:00Z",
      "planned_end": "2025-08-08T08:00:00Z"
    }
  ],
  "critical_path": [
    {
      "task_id": "task-001",
      "duration_minutes": 60,
      "slack_minutes": 0
    }
  ],
  "warnings": [],
  "metrics": {
    "variables_count": 5000,
    "constraints_count": 12000,
    "search_nodes": 45000
  }
}
```

#### Get Schedule Status

```http
GET /scheduling/schedules/{schedule_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "version": 1,
  "status": "active",
  "effective_date": "2025-08-08T00:00:00Z",
  "created_at": "2025-08-07T10:30:00Z",
  "makespan_hours": 120.5,
  "completion_rate": 0.45,
  "active_tasks": 5,
  "completed_tasks": 45,
  "total_tasks": 100
}
```

#### Optimize Resources for Fixed Schedule

```http
POST /scheduling/optimize-resources
Content-Type: application/json
Authorization: Bearer {token}

{
  "schedule_id": "660e8400-e29b-41d4-a716-446655440001",
  "target_utilization": 0.80,
  "resource_costs": {
    "machines": {
      "cnc-01": 150.00
    },
    "operators": {
      "MACHINING_L3": 75.00,
      "MACHINING_L2": 60.00,
      "MACHINING_L1": 45.00
    }
  },
  "constraints": {
    "max_operators": 20,
    "max_machines_per_zone": {
      "Zone-A": 10,
      "Zone-B": 8
    }
  }
}
```

**Response:**
```json
{
  "optimization_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "optimal",
  "total_cost": 12500.00,
  "resource_mix": {
    "machines": {
      "cnc-01": 3,
      "weld-01": 2
    },
    "operators": {
      "MACHINING_L3": 2,
      "MACHINING_L2": 4,
      "WELDING_L2": 3
    }
  },
  "utilization": {
    "average": 0.79,
    "machines": 0.82,
    "operators": 0.76
  },
  "peak_requirements": {
    "timestamp": "2025-08-10T10:00:00Z",
    "machines_needed": 5,
    "operators_needed": 9
  }
}
```

### Resource Management

#### List Machines

```http
GET /scheduling/machines?zone=Zone-A&available=true
Authorization: Bearer {token}
```

**Response:**
```json
{
  "items": [
    {
      "id": "cnc-01",
      "name": "CNC Machine 01",
      "zone": "Zone-A",
      "is_available": true,
      "skill_requirements": [
        {
          "skill_type": "MACHINING",
          "minimum_level": 2
        }
      ],
      "current_task": null,
      "maintenance_windows": []
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 20
}
```

#### List Operators

```http
GET /scheduling/operators?skill=MACHINING&min_level=2
Authorization: Bearer {token}
```

**Response:**
```json
{
  "items": [
    {
      "id": "op-001",
      "name": "John Smith",
      "employee_id": "EMP001",
      "skills": [
        {
          "skill_type": "MACHINING",
          "level": 3,
          "certified_date": "2023-01-15",
          "expiry_date": "2026-01-15"
        }
      ],
      "is_available": true,
      "shift_pattern": "day",
      "current_tasks": []
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20
}
```

### Analytics & Reporting

#### Get Schedule Analytics

```http
GET /scheduling/schedules/{schedule_id}/analytics
Authorization: Bearer {token}
```

**Response:**
```json
{
  "schedule_id": "660e8400-e29b-41d4-a716-446655440001",
  "kpis": {
    "makespan_hours": 120.5,
    "total_cost": 15000.00,
    "machine_utilization": 0.85,
    "operator_utilization": 0.78,
    "on_time_delivery_rate": 0.92,
    "average_flow_time_hours": 48.3,
    "wip_average": 12.5
  },
  "bottlenecks": [
    {
      "resource_type": "machine",
      "resource_id": "cnc-01",
      "utilization": 0.95,
      "queue_length_average": 5.2
    }
  ],
  "critical_resources": [
    {
      "operator_id": "op-001",
      "skill_type": "MACHINING",
      "criticality_score": 0.89
    }
  ],
  "tardiness_analysis": {
    "late_jobs_count": 2,
    "average_tardiness_hours": 4.5,
    "max_tardiness_hours": 8.0
  }
}
```

## Domain Models

### Job

Represents a manufacturing work order with multiple operations.

```typescript
interface Job {
  id: UUID;
  job_number: string;
  priority: 0 | 1 | 2; // LOW | MEDIUM | HIGH
  due_date?: ISO8601;
  release_date: ISO8601;
  tasks: Task[];
}
```

### Task

Represents a single operation within a job.

```typescript
interface Task {
  id: UUID;
  job_id: UUID;
  operation_number: number;
  machine_options: MachineOption[];
  skill_requirements: SkillRequirement[];
  is_critical: boolean;
  predecessor_ids: UUID[];
  status: TaskStatus;
}

enum TaskStatus {
  PENDING = "pending",
  READY = "ready",
  SCHEDULED = "scheduled",
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  CANCELLED = "cancelled",
  ON_HOLD = "on_hold"
}
```

### Machine

Represents a production resource.

```typescript
interface Machine {
  id: UUID;
  name: string;
  zone: string;
  skill_requirements: SkillRequirement[];
  is_attended: boolean;
  is_available: boolean;
  maintenance_windows: TimeWindow[];
}
```

### Operator

Represents a human resource with skills.

```typescript
interface Operator {
  id: UUID;
  name: string;
  employee_id: string;
  skills: SkillProficiency[];
  shift_pattern: "day" | "night" | "swing";
  is_available: boolean;
}
```

### Schedule

Represents a complete production schedule.

```typescript
interface Schedule {
  id: UUID;
  version: number;
  effective_date: ISO8601;
  assignments: Assignment[];
  makespan: Duration;
  total_cost: number;
}

interface Assignment {
  task_id: UUID;
  machine_id: UUID;
  operator_ids: UUID[];
  planned_start: ISO8601;
  planned_end: ISO8601;
}
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error information.

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "due_date",
        "message": "Due date must be in the future"
      }
    ],
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-08-07T10:30:00Z"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `AUTHENTICATION_REQUIRED` | 401 | Missing or invalid authentication |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks required permissions |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource does not exist |
| `CONFLICT` | 409 | Resource conflict (e.g., duplicate job number) |
| `BUSINESS_RULE_VIOLATION` | 422 | Business rule constraint violated |
| `SOLVER_TIMEOUT` | 408 | Optimization solver exceeded time limit |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

### Validation Errors

Validation errors include field-level details:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "tasks[0].machine_options",
        "message": "At least one machine option required"
      },
      {
        "field": "operators[2].skills[0].level",
        "message": "Skill level must be between 1 and 3"
      }
    ]
  }
}
```

## Rate Limiting

The API implements rate limiting to ensure fair usage and system stability.

### Rate Limits

| Endpoint Type | Requests | Window |
|--------------|----------|---------|
| Authentication | 5 | 1 minute |
| Scheduling Solve | 10 | 1 minute |
| Resource Optimization | 5 | 1 minute |
| Read Operations | 100 | 1 minute |
| Write Operations | 50 | 1 minute |

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1691408400
```

### Rate Limit Exceeded Response

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after 30 seconds",
    "retry_after": 30
  }
}
```

## WebSocket Events

The API provides real-time updates via WebSocket connections.

### Connection

```javascript
const ws = new WebSocket('wss://api.vulcan-engine.com/ws?token={jwt_token}');
```

### Event Types

#### Schedule Progress

```json
{
  "event": "schedule.progress",
  "data": {
    "schedule_id": "660e8400-e29b-41d4-a716-446655440001",
    "progress": 0.45,
    "current_time": "2025-08-10T10:30:00Z",
    "active_tasks": 5,
    "completed_tasks": 45
  }
}
```

#### Task Status Change

```json
{
  "event": "task.status_changed",
  "data": {
    "task_id": "task-001",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "old_status": "scheduled",
    "new_status": "in_progress",
    "timestamp": "2025-08-10T07:00:00Z"
  }
}
```

#### Optimization Progress

```json
{
  "event": "optimization.progress",
  "data": {
    "optimization_id": "770e8400-e29b-41d4-a716-446655440002",
    "progress": 0.75,
    "current_objective": 12500.00,
    "best_bound": 11000.00,
    "gap": 0.12,
    "nodes_explored": 45000
  }
}
```

#### Alert

```json
{
  "event": "alert",
  "data": {
    "level": "warning",
    "type": "resource_conflict",
    "message": "Operator op-001 assigned to overlapping tasks",
    "affected_resources": ["op-001"],
    "timestamp": "2025-08-10T10:35:00Z"
  }
}
```

### Subscription Management

#### Subscribe to Events

```json
{
  "action": "subscribe",
  "channels": ["schedule.660e8400-e29b-41d4-a716-446655440001", "alerts"]
}
```

#### Unsubscribe

```json
{
  "action": "unsubscribe",
  "channels": ["schedule.660e8400-e29b-41d4-a716-446655440001"]
}
```

### Connection Management

#### Heartbeat

The server sends periodic heartbeats:

```json
{
  "event": "heartbeat",
  "timestamp": "2025-08-10T10:30:00Z"
}
```

Clients should respond with:

```json
{
  "action": "pong"
}
```

#### Reconnection

On disconnection, clients should implement exponential backoff:

```javascript
let reconnectDelay = 1000; // Start with 1 second
const maxDelay = 30000; // Max 30 seconds

function reconnect() {
  setTimeout(() => {
    connect();
    reconnectDelay = Math.min(reconnectDelay * 2, maxDelay);
  }, reconnectDelay);
}
```
