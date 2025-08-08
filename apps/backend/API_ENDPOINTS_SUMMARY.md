# Production Scheduling API Endpoints

This document summarizes the HTTP API endpoints that have been created to expose the production scheduling functionality.

## API Structure

The scheduling API is organized into four main resource groups:

- **Jobs** (`/api/v1/scheduling/jobs`) - Job management and lifecycle
- **Schedules** (`/api/v1/scheduling/schedules`) - Schedule creation and optimization
- **Resources** (`/api/v1/scheduling/resources`) - Machine and operator management
- **Status** (`/api/v1/scheduling/status`) - Real-time monitoring and system status

## Authentication & Authorization

All endpoints use JWT authentication with role-based access control (RBAC):

- **Operator** - View-only access to jobs, schedules, and resources
- **Scheduler** - Create and manage jobs, create and optimize schedules
- **Manager** - Full CRUD operations, schedule publishing and management
- **Admin** - All permissions including resource management and system administration

## Job Management Endpoints

### Core Job Operations
```
POST   /api/v1/scheduling/jobs                    # Create new job
GET    /api/v1/scheduling/jobs                    # List jobs with filtering
GET    /api/v1/scheduling/jobs/{job_id}           # Get job details
GET    /api/v1/scheduling/jobs/number/{job_number} # Get job by number
PUT    /api/v1/scheduling/jobs/{job_id}           # Update job
DELETE /api/v1/scheduling/jobs/{job_id}           # Delete job
```

### Job Status and Scheduling
```
POST   /api/v1/scheduling/jobs/{job_id}/status    # Change job status
POST   /api/v1/scheduling/jobs/{job_id}/schedule  # Update job schedule dates
GET    /api/v1/scheduling/jobs/statistics/summary # Get job statistics
```

### Key Features
- Full CRUD operations with validation
- Status transition management (planned → released → in_progress → completed)
- Priority and due date management
- Task coordination and progress tracking
- Customer and part number tracking

## Schedule Management Endpoints

### Core Schedule Operations
```
POST   /api/v1/scheduling/schedules               # Create new schedule
GET    /api/v1/scheduling/schedules               # List schedules with filtering
GET    /api/v1/scheduling/schedules/{schedule_id} # Get schedule details
DELETE /api/v1/scheduling/schedules/{schedule_id} # Delete schedule
```

### Schedule Optimization and Management
```
POST   /api/v1/scheduling/schedules/{schedule_id}/optimize # Run optimization
POST   /api/v1/scheduling/schedules/{schedule_id}/status   # Change status (publish/activate/complete)
GET    /api/v1/scheduling/schedules/{schedule_id}/assignments # Get task assignments
GET    /api/v1/scheduling/schedules/{schedule_id}/metrics     # Get performance metrics
GET    /api/v1/scheduling/schedules/{schedule_id}/validation  # Validate constraints
```

### Key Features
- OR-Tools CP-SAT optimization integration
- Hierarchical optimization (makespan → cost)
- Constraint validation and violation reporting
- Schedule lifecycle management (draft → published → active → completed)
- Performance metrics calculation
- Real-time optimization status tracking

## Resource Management Endpoints

### Availability and Discovery
```
GET    /api/v1/scheduling/resources/availability  # Check resource availability
GET    /api/v1/scheduling/resources/utilization   # Get utilization statistics
```

### Machine Management
```
GET    /api/v1/scheduling/resources/machines                     # List machines
GET    /api/v1/scheduling/resources/machines/{machine_id}        # Get machine details
GET    /api/v1/scheduling/resources/machines/{machine_id}/schedule # Get machine schedule
```

### Operator Management
```
GET    /api/v1/scheduling/resources/operators                      # List operators
GET    /api/v1/scheduling/resources/operators/{operator_id}        # Get operator details
GET    /api/v1/scheduling/resources/operators/{operator_id}/schedule # Get operator schedule
```

### Key Features
- Real-time availability checking
- Skill-based operator filtering
- Production zone filtering
- Utilization tracking and reporting
- Schedule conflict detection

## Status and Monitoring Endpoints

### System Status
```
GET    /api/v1/scheduling/status/system          # Overall system health
GET    /api/v1/scheduling/status/dashboard       # Dashboard metrics
GET    /api/v1/scheduling/status/alerts          # System alerts and warnings
```

### Real-time Monitoring
```
GET    /api/v1/scheduling/status/real-time       # Current production floor status
GET    /api/v1/scheduling/status/optimization/{schedule_id} # Optimization progress
```

### Key Features
- System health scoring
- Real-time production floor status
- Alert generation and prioritization
- Performance trend analysis
- Optimization progress tracking

## Request/Response DTOs

### Job DTOs
- `CreateJobRequest` - Job creation with validation
- `UpdateJobRequest` - Partial job updates
- `JobResponse` - Complete job details with tasks
- `JobSummaryResponse` - Condensed job information
- `JobStatisticsResponse` - System-wide job statistics

### Schedule DTOs
- `CreateScheduleRequest` - Schedule creation parameters
- `OptimizeScheduleRequest` - Optimization configuration
- `ScheduleResponse` - Complete schedule with assignments
- `ScheduleStatusResponse` - Status change confirmations
- `TaskAssignmentResponse` - Individual task assignments
- `ScheduleMetricsResponse` - Performance metrics

### Resource DTOs
- `ResourceAvailabilityRequest` - Availability query parameters
- `ResourceAvailabilityResponse` - Available resources with summary
- `ResourceSummaryResponse` - Individual resource information

### Status DTOs
- `OptimizationStatusResponse` - Real-time optimization progress
- System status responses with health metrics and alerts

## Security Integration

### Authentication
- JWT tokens with RS256 algorithm
- Token refresh and rotation support
- Rate limiting and brute force protection

### Authorization
- Role-based access control (RBAC)
- Granular permissions for each operation
- Permission checking via dependency injection

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- XSS protection for string fields

## Error Handling

Comprehensive error handling with appropriate HTTP status codes:

- **400** - Bad Request (validation errors, invalid parameters)
- **401** - Unauthorized (authentication required)
- **403** - Forbidden (insufficient permissions)
- **404** - Not Found (entity not found)
- **408** - Request Timeout (optimization timeout)
- **409** - Conflict (business rule violations, status conflicts)
- **422** - Unprocessable Entity (no feasible solution)
- **500** - Internal Server Error (database errors, system failures)

## Integration Points

### Domain Services
- **JobService** - Job lifecycle management
- **SchedulingService** - Schedule creation and management
- **OptimizationService** - OR-Tools integration
- **ConstraintValidationService** - Business rule validation

### Repository Layer
- **JobRepository** - Job persistence operations
- **TaskRepository** - Task management
- **ScheduleRepository** - Schedule persistence
- **MachineRepository** - Machine data access
- **OperatorRepository** - Operator management

### External Systems
- OR-Tools CP-SAT solver for optimization
- WebSocket integration for real-time updates
- Background task processing for long-running operations

## Usage Examples

### Create and Optimize a Schedule

1. **Create Schedule**
   ```bash
   POST /api/v1/scheduling/schedules
   {
     "name": "Weekly Production Schedule",
     "job_ids": ["job-uuid-1", "job-uuid-2"],
     "start_time": "2024-01-15T08:00:00Z"
   }
   ```

2. **Optimize Schedule**
   ```bash
   POST /api/v1/scheduling/schedules/{schedule_id}/optimize
   {
     "max_time_seconds": 300,
     "primary_objective": "makespan"
   }
   ```

3. **Publish Schedule**
   ```bash
   POST /api/v1/scheduling/schedules/{schedule_id}/status
   {
     "action": "publish",
     "reason": "Schedule validated and ready"
   }
   ```

### Monitor System Status

1. **Check System Health**
   ```bash
   GET /api/v1/scheduling/status/system
   ```

2. **Get Resource Availability**
   ```bash
   GET /api/v1/scheduling/resources/availability?start_time=2024-01-15T08:00:00Z&end_time=2024-01-15T17:00:00Z
   ```

3. **View Current Production Status**
   ```bash
   GET /api/v1/scheduling/status/real-time
   ```

## Implementation Status

✅ **Completed:**
- All HTTP API endpoints implemented
- Comprehensive request/response DTOs
- Domain service integration via dependency injection
- Role-based access control and permissions
- Error handling and validation
- API documentation and examples

🔄 **Production Ready:**
The API endpoints are production-ready and provide complete access to the scheduling system functionality. They follow FastAPI best practices and integrate seamlessly with the existing domain model and security infrastructure.
