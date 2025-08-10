# Vulcan Engine Integration Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication Setup](#authentication-setup)
3. [Common Workflows](#common-workflows)
4. [SDK Examples](#sdk-examples)
5. [WebSocket Integration](#websocket-integration)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- API credentials (contact admin@example.com)
- HTTPS-capable client
- JSON parsing capability
- WebSocket support (for real-time features)

### Quick Start

1. **Obtain API Credentials**
   ```bash
   # Request access from your administrator
   # You'll receive:
   # - API endpoint URL
   # - Client ID
   # - Client Secret (keep secure!)
   ```

2. **Test Connection**
   ```bash
   curl -X GET https://api.vulcan-engine.com/api/v1/health
   ```

3. **Authenticate**
   ```bash
   curl -X POST https://api.vulcan-engine.com/api/v1/login/access-token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=your_password"
   ```

4. **Make Your First API Call**
   ```bash
   curl -X GET https://api.vulcan-engine.com/api/v1/scheduling/machines \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

## Authentication Setup

### OAuth 2.0 Flow

The API uses OAuth 2.0 with JWT tokens.

#### Python Example

```python
import requests
from datetime import datetime, timedelta

class VulcanAPIClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

    def authenticate(self):
        """Obtain access and refresh tokens."""
        response = requests.post(
            f"{self.base_url}/login/access-token",
            data={
                "username": self.username,
                "password": self.password
            }
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.token_expiry = datetime.now() + timedelta(minutes=30)

        return self.access_token

    def refresh_access_token(self):
        """Refresh the access token using refresh token."""
        response = requests.post(
            f"{self.base_url}/login/refresh",
            headers={"Authorization": f"Bearer {self.refresh_token}"}
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        self.token_expiry = datetime.now() + timedelta(minutes=30)

        return self.access_token

    def make_request(self, method, endpoint, **kwargs):
        """Make an authenticated API request."""
        # Check if token needs refresh
        if datetime.now() >= self.token_expiry - timedelta(minutes=5):
            self.refresh_access_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        response = requests.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            **kwargs
        )
        response.raise_for_status()

        return response.json()

# Usage
client = VulcanAPIClient(
    "https://api.vulcan-engine.com/api/v1",
    "user@example.com",
    "password"
)
client.authenticate()
```

#### JavaScript/TypeScript Example

```typescript
class VulcanAPIClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private tokenExpiry: Date | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async authenticate(username: string, password: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/login/access-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username,
        password,
      }),
    });

    if (!response.ok) {
      throw new Error(`Authentication failed: ${response.statusText}`);
    }

    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.tokenExpiry = new Date(Date.now() + 30 * 60 * 1000); // 30 minutes
  }

  async refreshAccessToken(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/login/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.refreshToken}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Token refresh failed: ${response.statusText}`);
    }

    const data = await response.json();
    this.accessToken = data.access_token;
    this.tokenExpiry = new Date(Date.now() + 30 * 60 * 1000);
  }

  async request<T>(
    method: string,
    endpoint: string,
    body?: any
  ): Promise<T> {
    // Check if token needs refresh
    if (this.tokenExpiry && Date.now() >= this.tokenExpiry.getTime() - 5 * 60 * 1000) {
      await this.refreshAccessToken();
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || response.statusText);
    }

    return response.json();
  }
}
```

## Common Workflows

### Workflow 1: Create and Schedule a Job

This workflow demonstrates creating a manufacturing job and obtaining an optimized schedule.

```python
import json
from datetime import datetime, timedelta

def schedule_manufacturing_job(client):
    """Complete workflow for scheduling a manufacturing job."""

    # Step 1: Create a standard job
    print("Step 1: Creating job...")
    job = client.make_request(
        "POST",
        "/scheduling/domain/jobs/standard",
        json={
            "job_number": f"JOB-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "operation_count": 50,
            "priority": 1,
            "due_date": (datetime.now() + timedelta(days=7)).isoformat()
        }
    )
    print(f"Created job: {job['id']}")

    # Step 2: Get available resources
    print("\nStep 2: Fetching available resources...")
    machines = client.make_request("GET", "/scheduling/machines?available=true")
    operators = client.make_request("GET", "/scheduling/operators?available=true")
    print(f"Found {machines['total']} machines and {operators['total']} operators")

    # Step 3: Prepare scheduling problem
    print("\nStep 3: Preparing scheduling problem...")
    problem = {
        "problem": {
            "jobs": [job],
            "machines": machines["items"],
            "operators": operators["items"],
            "calendar": {
                "weekday_hours": {
                    "0": {"start_time": "07:00", "end_time": "16:00"},
                    "1": {"start_time": "07:00", "end_time": "16:00"},
                    "2": {"start_time": "07:00", "end_time": "16:00"},
                    "3": {"start_time": "07:00", "end_time": "16:00"},
                    "4": {"start_time": "07:00", "end_time": "16:00"}
                },
                "holidays": []
            }
        },
        "optimization_parameters": {
            "max_solving_time": 60,
            "objective_weights": {
                "makespan": 0.4,
                "total_cost": 0.3,
                "tardiness": 0.3
            }
        }
    }

    # Step 4: Solve the scheduling problem
    print("\nStep 4: Solving scheduling problem...")
    schedule = client.make_request(
        "POST",
        "/scheduling/solve",
        json=problem
    )
    print(f"Schedule created: {schedule['schedule_id']}")
    print(f"Status: {schedule['status']}")
    print(f"Makespan: {schedule['makespan_hours']} hours")
    print(f"Total cost: ${schedule['total_cost']}")

    # Step 5: Get schedule analytics
    print("\nStep 5: Fetching analytics...")
    analytics = client.make_request(
        "GET",
        f"/scheduling/schedules/{schedule['schedule_id']}/analytics"
    )
    print(f"Machine utilization: {analytics['kpis']['machine_utilization']:.1%}")
    print(f"On-time delivery rate: {analytics['kpis']['on_time_delivery_rate']:.1%}")

    return schedule

# Execute workflow
schedule = schedule_manufacturing_job(client)
```

### Workflow 2: Resource Optimization for Fixed Schedule

```python
def optimize_resources_for_schedule(client, schedule_id):
    """Optimize resource allocation for an existing schedule."""

    # Step 1: Get current schedule details
    print("Step 1: Fetching schedule details...")
    schedule = client.make_request(
        "GET",
        f"/scheduling/schedules/{schedule_id}"
    )
    print(f"Schedule version: {schedule['version']}")
    print(f"Current makespan: {schedule['makespan_hours']} hours")

    # Step 2: Define resource costs
    print("\nStep 2: Defining resource costs...")
    resource_costs = {
        "machines": {
            "cnc-01": 150.00,
            "cnc-02": 150.00,
            "weld-01": 120.00,
            "weld-02": 120.00,
            "assembly-01": 100.00
        },
        "operators": {
            "MACHINING_L3": 75.00,
            "MACHINING_L2": 60.00,
            "MACHINING_L1": 45.00,
            "WELDING_L2": 65.00,
            "WELDING_L1": 50.00,
            "ASSEMBLY_L2": 55.00,
            "ASSEMBLY_L1": 40.00
        }
    }

    # Step 3: Optimize resources
    print("\nStep 3: Optimizing resource allocation...")
    optimization = client.make_request(
        "POST",
        "/scheduling/optimize-resources",
        json={
            "schedule_id": schedule_id,
            "target_utilization": 0.80,
            "resource_costs": resource_costs,
            "constraints": {
                "max_operators": 25,
                "max_machines_per_zone": {
                    "Zone-A": 10,
                    "Zone-B": 8,
                    "Zone-C": 6
                }
            }
        }
    )

    print(f"Optimization status: {optimization['status']}")
    print(f"Total cost: ${optimization['total_cost']}")
    print(f"Average utilization: {optimization['utilization']['average']:.1%}")

    # Step 4: Display resource mix
    print("\nStep 4: Recommended resource mix:")
    print("Machines:")
    for machine, count in optimization['resource_mix']['machines'].items():
        print(f"  {machine}: {count} units")

    print("Operators:")
    for skill, count in optimization['resource_mix']['operators'].items():
        print(f"  {skill}: {count} people")

    return optimization

# Execute workflow
optimization = optimize_resources_for_schedule(client, "schedule-id-here")
```

### Workflow 3: Real-time Schedule Monitoring

```python
import asyncio
import websockets
import json

async def monitor_schedule_execution(schedule_id, token):
    """Monitor schedule execution in real-time."""

    uri = f"wss://api.vulcan-engine.com/ws?token={token}"

    async with websockets.connect(uri) as websocket:
        # Subscribe to schedule events
        await websocket.send(json.dumps({
            "action": "subscribe",
            "channels": [
                f"schedule.{schedule_id}",
                "alerts"
            ]
        }))

        print(f"Monitoring schedule {schedule_id}...")

        # Listen for events
        while True:
            message = await websocket.recv()
            event = json.loads(message)

            if event["event"] == "schedule.progress":
                data = event["data"]
                print(f"Progress: {data['progress']:.1%} - "
                      f"Active: {data['active_tasks']} - "
                      f"Completed: {data['completed_tasks']}")

            elif event["event"] == "task.status_changed":
                data = event["data"]
                print(f"Task {data['task_id']}: "
                      f"{data['old_status']} -> {data['new_status']}")

            elif event["event"] == "alert":
                data = event["data"]
                print(f"⚠️ {data['level'].upper()}: {data['message']}")

            elif event["event"] == "heartbeat":
                # Respond to heartbeat
                await websocket.send(json.dumps({"action": "pong"}))

# Run monitoring
asyncio.run(monitor_schedule_execution("schedule-id", "your-token"))
```

## SDK Examples

### Python SDK

```python
# Install: pip install vulcan-engine-sdk

from vulcan_engine import VulcanClient, SchedulingProblem, OptimizationObjective

# Initialize client
client = VulcanClient(
    api_key="your-api-key",
    base_url="https://api.vulcan-engine.com"
)

# Create a scheduling problem
problem = SchedulingProblem()

# Add jobs
job = problem.add_job(
    job_number="JOB-001",
    priority=1,
    due_date="2025-08-15T16:00:00Z"
)

# Add tasks to job
task1 = job.add_task(
    operation_number=10,
    machine_options=["cnc-01", "cnc-02"],
    duration_minutes=60,
    skill_requirements={"MACHINING": 2}
)

task2 = job.add_task(
    operation_number=20,
    machine_options=["weld-01"],
    duration_minutes=45,
    skill_requirements={"WELDING": 1},
    predecessors=[task1]
)

# Define optimization objective
objective = OptimizationObjective(
    minimize_makespan=0.4,
    minimize_cost=0.3,
    minimize_tardiness=0.3
)

# Solve
solution = client.solve(problem, objective, timeout_seconds=60)

# Access results
print(f"Schedule ID: {solution.schedule_id}")
print(f"Makespan: {solution.makespan_hours} hours")
print(f"Total cost: ${solution.total_cost}")

# Get Gantt chart data
gantt_data = solution.get_gantt_chart()

# Export to Excel
solution.export_to_excel("schedule.xlsx")
```

### JavaScript/TypeScript SDK

```typescript
// Install: npm install @vulcan-engine/sdk

import { VulcanClient, SchedulingProblem, Job, Task } from '@vulcan-engine/sdk';

// Initialize client
const client = new VulcanClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.vulcan-engine.com'
});

// Create scheduling problem
const problem = new SchedulingProblem();

// Add job with tasks
const job = problem.addJob({
  jobNumber: 'JOB-001',
  priority: 'HIGH',
  dueDate: new Date('2025-08-15T16:00:00Z')
});

const task1 = job.addTask({
  operationNumber: 10,
  machineOptions: ['cnc-01', 'cnc-02'],
  durationMinutes: 60,
  skillRequirements: { MACHINING: 2 }
});

const task2 = job.addTask({
  operationNumber: 20,
  machineOptions: ['weld-01'],
  durationMinutes: 45,
  skillRequirements: { WELDING: 1 },
  predecessors: [task1.id]
});

// Solve
const solution = await client.solve(problem, {
  maxSolvingTime: 60,
  objectives: {
    makespan: 0.4,
    cost: 0.3,
    tardiness: 0.3
  }
});

// Access results
console.log(`Schedule ID: ${solution.scheduleId}`);
console.log(`Makespan: ${solution.makespanHours} hours`);
console.log(`Total cost: $${solution.totalCost}`);

// Subscribe to real-time updates
solution.onProgress((progress) => {
  console.log(`Progress: ${progress.percentage}%`);
});

solution.onTaskStatusChange((event) => {
  console.log(`Task ${event.taskId}: ${event.oldStatus} -> ${event.newStatus}`);
});
```

### C# SDK

```csharp
// Install: dotnet add package VulcanEngine.SDK

using VulcanEngine.SDK;

// Initialize client
var client = new VulcanClient(
    apiKey: "your-api-key",
    baseUrl: "https://api.vulcan-engine.com"
);

// Create scheduling problem
var problem = new SchedulingProblem();

// Add job
var job = problem.AddJob(new Job
{
    JobNumber = "JOB-001",
    Priority = Priority.High,
    DueDate = DateTime.Now.AddDays(7)
});

// Add tasks
var task1 = job.AddTask(new Task
{
    OperationNumber = 10,
    MachineOptions = new[] { "cnc-01", "cnc-02" },
    DurationMinutes = 60,
    SkillRequirements = new Dictionary<string, int> { { "MACHINING", 2 } }
});

var task2 = job.AddTask(new Task
{
    OperationNumber = 20,
    MachineOptions = new[] { "weld-01" },
    DurationMinutes = 45,
    SkillRequirements = new Dictionary<string, int> { { "WELDING", 1 } },
    Predecessors = new[] { task1.Id }
});

// Solve
var solution = await client.SolveAsync(problem, new OptimizationOptions
{
    MaxSolvingTime = TimeSpan.FromSeconds(60),
    Objectives = new ObjectiveWeights
    {
        Makespan = 0.4,
        Cost = 0.3,
        Tardiness = 0.3
    }
});

// Access results
Console.WriteLine($"Schedule ID: {solution.ScheduleId}");
Console.WriteLine($"Makespan: {solution.MakespanHours} hours");
Console.WriteLine($"Total cost: ${solution.TotalCost}");
```

## WebSocket Integration

### Connection Management

```javascript
class VulcanWebSocketClient {
  constructor(token) {
    this.token = token;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
    this.heartbeatInterval = null;
    this.eventHandlers = new Map();
  }

  connect() {
    const wsUrl = `wss://api.vulcan-engine.com/ws?token=${this.token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.stopHeartbeat();
      this.attemptReconnect();
    };
  }

  handleMessage(message) {
    if (message.event === 'heartbeat') {
      this.send({ action: 'pong' });
      return;
    }

    // Dispatch to registered handlers
    const handlers = this.eventHandlers.get(message.event) || [];
    handlers.forEach(handler => handler(message.data));
  }

  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event).push(handler);
  }

  subscribe(channels) {
    this.send({
      action: 'subscribe',
      channels: channels
    });
  }

  unsubscribe(channels) {
    this.send({
      action: 'unsubscribe',
      channels: channels
    });
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      this.send({ action: 'ping' });
    }, 30000); // Every 30 seconds
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );

    console.log(`Reconnecting in ${delay}ms...`);
    setTimeout(() => this.connect(), delay);
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Usage
const wsClient = new VulcanWebSocketClient('your-token');
wsClient.connect();

// Subscribe to schedule updates
wsClient.on('schedule.progress', (data) => {
  console.log(`Schedule progress: ${data.progress * 100}%`);
});

wsClient.on('task.status_changed', (data) => {
  console.log(`Task ${data.task_id} status: ${data.new_status}`);
});

wsClient.on('alert', (data) => {
  console.warn(`Alert: ${data.message}`);
});

// Subscribe to specific schedule
wsClient.subscribe(['schedule.660e8400-e29b-41d4-a716-446655440001']);
```

## Best Practices

### 1. Error Handling

Always implement comprehensive error handling:

```python
import time
from typing import Optional, Dict, Any

def api_call_with_retry(
    client,
    method: str,
    endpoint: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    **kwargs
) -> Optional[Dict[Any, Any]]:
    """Make API call with exponential backoff retry."""

    for attempt in range(max_retries):
        try:
            return client.make_request(method, endpoint, **kwargs)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                retry_after = int(e.response.headers.get('Retry-After', 30))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            elif e.response.status_code >= 500:  # Server error
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    print(f"Server error. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            # Other HTTP errors
            raise

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Network error. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            raise

    return None
```

### 2. Batch Operations

Optimize API usage with batch operations:

```python
def batch_create_jobs(client, job_specs, batch_size=10):
    """Create multiple jobs in batches."""
    results = []

    for i in range(0, len(job_specs), batch_size):
        batch = job_specs[i:i + batch_size]

        # Create jobs in parallel
        batch_results = []
        for spec in batch:
            result = client.make_request(
                "POST",
                "/scheduling/domain/jobs/standard",
                json=spec
            )
            batch_results.append(result)

        results.extend(batch_results)

        # Respect rate limits
        if i + batch_size < len(job_specs):
            time.sleep(1)  # Brief pause between batches

    return results
```

### 3. Caching

Implement caching for frequently accessed data:

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedVulcanClient(VulcanAPIClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._cache_expiry = {}

    def get_with_cache(self, endpoint, cache_duration=300):
        """Get data with caching."""
        now = datetime.now()

        # Check cache
        if endpoint in self._cache:
            if now < self._cache_expiry[endpoint]:
                return self._cache[endpoint]

        # Fetch fresh data
        data = self.make_request("GET", endpoint)

        # Update cache
        self._cache[endpoint] = data
        self._cache_expiry[endpoint] = now + timedelta(seconds=cache_duration)

        return data

    @lru_cache(maxsize=100)
    def get_machine_details(self, machine_id):
        """Get machine details with LRU cache."""
        return self.make_request("GET", f"/scheduling/machines/{machine_id}")
```

### 4. Monitoring and Logging

Implement comprehensive monitoring:

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vulcan_api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('vulcan_api')

class MonitoredVulcanClient(VulcanAPIClient):
    def make_request(self, method, endpoint, **kwargs):
        """Make request with monitoring."""
        start_time = datetime.now()
        correlation_id = kwargs.get('headers', {}).get('X-Correlation-ID', 'N/A')

        try:
            logger.info(f"Request started: {method} {endpoint} (ID: {correlation_id})")

            response = super().make_request(method, endpoint, **kwargs)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Request completed: {method} {endpoint} "
                       f"(Duration: {duration:.2f}s, ID: {correlation_id})")

            # Log slow requests
            if duration > 5:
                logger.warning(f"Slow request detected: {method} {endpoint} "
                             f"took {duration:.2f}s")

            return response

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Request failed: {method} {endpoint} "
                        f"(Duration: {duration:.2f}s, Error: {str(e)}, ID: {correlation_id})")
            raise
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Failures

**Problem:** 401 Unauthorized errors

**Solutions:**
- Verify credentials are correct
- Check token expiration
- Ensure refresh token logic is working
- Verify API endpoint URL

```python
def diagnose_auth_issue(client):
    """Diagnose authentication issues."""
    try:
        # Test basic connectivity
        response = requests.get(f"{client.base_url}/health")
        print(f"✓ API is reachable: {response.status_code}")

        # Test authentication
        client.authenticate()
        print("✓ Authentication successful")

        # Test authenticated request
        client.make_request("GET", "/scheduling/machines")
        print("✓ Authenticated requests working")

    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API endpoint")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("✗ Invalid credentials")
        else:
            print(f"✗ HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"✗ Unexpected error: {str(e)}")
```

#### 2. Rate Limiting

**Problem:** 429 Too Many Requests errors

**Solutions:**
- Implement exponential backoff
- Use batch operations
- Cache frequently accessed data
- Consider upgrading API plan

```python
class RateLimitHandler:
    def __init__(self, max_requests_per_minute=60):
        self.max_requests = max_requests_per_minute
        self.request_times = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()

        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.max_requests:
            # Calculate wait time
            oldest_request = min(self.request_times)
            wait_time = 60 - (now - oldest_request) + 1
            print(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)

        self.request_times.append(now)
```

#### 3. Timeout Errors

**Problem:** Solver timeout on complex problems

**Solutions:**
- Increase max_solving_time parameter
- Simplify problem constraints
- Use problem decomposition
- Enable incremental solving

```python
def solve_with_incremental_approach(client, problem):
    """Solve complex problem incrementally."""

    # Start with short timeout
    timeout = 30
    best_solution = None

    while timeout <= 300:  # Max 5 minutes
        try:
            solution = client.make_request(
                "POST",
                "/scheduling/solve",
                json={
                    **problem,
                    "optimization_parameters": {
                        **problem.get("optimization_parameters", {}),
                        "max_solving_time": timeout,
                        "initial_solution": best_solution
                    }
                }
            )

            if solution["status"] == "optimal":
                print(f"Optimal solution found in {timeout}s")
                return solution

            best_solution = solution
            timeout *= 2  # Double timeout for next attempt

        except requests.exceptions.Timeout:
            print(f"Timeout at {timeout}s, increasing...")
            timeout *= 2

    return best_solution
```

#### 4. Data Validation Errors

**Problem:** 400 Bad Request with validation errors

**Solutions:**
- Validate data before sending
- Check required fields
- Verify data types and formats
- Use SDK validation methods

```python
def validate_job_data(job_data):
    """Validate job data before submission."""
    errors = []

    # Required fields
    required = ["job_number", "tasks"]
    for field in required:
        if field not in job_data:
            errors.append(f"Missing required field: {field}")

    # Validate tasks
    if "tasks" in job_data:
        for i, task in enumerate(job_data["tasks"]):
            if not task.get("machine_options"):
                errors.append(f"Task {i}: missing machine_options")

            if "operation_number" in task:
                if not isinstance(task["operation_number"], int) or task["operation_number"] < 0:
                    errors.append(f"Task {i}: invalid operation_number")

    # Validate dates
    if "due_date" in job_data:
        try:
            due_date = datetime.fromisoformat(job_data["due_date"].replace('Z', '+00:00'))
            if due_date < datetime.now():
                errors.append("Due date must be in the future")
        except ValueError:
            errors.append("Invalid due_date format (use ISO 8601)")

    return errors

# Usage
errors = validate_job_data(job_data)
if errors:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")
else:
    # Submit job
    result = client.make_request("POST", "/scheduling/jobs", json=job_data)
```

### Debug Mode

Enable debug mode for detailed logging:

```python
import json

class DebugVulcanClient(VulcanAPIClient):
    def __init__(self, *args, debug=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug = debug

    def make_request(self, method, endpoint, **kwargs):
        """Make request with debug output."""
        if self.debug:
            print(f"\n{'='*60}")
            print(f"DEBUG: {method} {endpoint}")
            print(f"Headers: {kwargs.get('headers', {})}")
            if 'json' in kwargs:
                print(f"Body: {json.dumps(kwargs['json'], indent=2)}")
            print(f"{'='*60}\n")

        try:
            response = super().make_request(method, endpoint, **kwargs)

            if self.debug:
                print(f"\nResponse: {json.dumps(response, indent=2)}\n")

            return response

        except Exception as e:
            if self.debug:
                print(f"\nError: {str(e)}\n")
            raise

# Enable debug mode
debug_client = DebugVulcanClient(
    base_url="https://api.vulcan-engine.com/api/v1",
    username="user@example.com",
    password="password",
    debug=True
)
```

### Support Resources

- **Documentation**: https://docs.vulcan-engine.com
- **API Status**: https://status.vulcan-engine.com
- **Support Email**: support@vulcan-engine.com
- **Community Forum**: https://forum.vulcan-engine.com
- **GitHub Issues**: https://github.com/vulcan-engine/api/issues
