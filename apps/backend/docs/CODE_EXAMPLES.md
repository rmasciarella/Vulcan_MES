# Vulcan Engine Code Examples

## Table of Contents

1. [Python Examples](#python-examples)
2. [JavaScript/TypeScript Examples](#javascripttypescript-examples)
3. [C# Examples](#c-examples)
4. [Java Examples](#java-examples)
5. [Go Examples](#go-examples)
6. [cURL Examples](#curl-examples)

## Python Examples

### Complete Python Client

```python
"""
Vulcan Engine Python Client
Comprehensive client for scheduling API integration
"""

import requests
import json
import asyncio
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class SkillType(Enum):
    MACHINING = "MACHINING"
    WELDING = "WELDING"
    ASSEMBLY = "ASSEMBLY"
    INSPECTION = "INSPECTION"
    PROGRAMMING = "PROGRAMMING"

@dataclass
class Task:
    operation_number: int
    machine_options: List[str]
    duration_minutes: int
    skill_requirements: Dict[SkillType, int]
    predecessors: List[str] = None

    def to_dict(self):
        return {
            "operation_number": self.operation_number,
            "machine_options": self.machine_options,
            "duration_minutes": self.duration_minutes,
            "skill_requirements": {k.value: v for k, v in self.skill_requirements.items()},
            "predecessors": self.predecessors or []
        }

@dataclass
class Job:
    job_number: str
    tasks: List[Task]
    priority: int = 0
    due_date: Optional[datetime] = None

    def to_dict(self):
        return {
            "job_number": self.job_number,
            "tasks": [t.to_dict() for t in self.tasks],
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None
        }

class VulcanEngineClient:
    """Complete Python client for Vulcan Engine API."""

    def __init__(self, base_url: str, username: str = None, password: str = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None

        if username and password:
            self.authenticate(username, password)

    def authenticate(self, username: str, password: str):
        """Authenticate and obtain tokens."""
        response = self.session.post(
            f"{self.base_url}/login/access-token",
            data={"username": username, "password": password}
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

        return self

    def refresh_auth(self):
        """Refresh authentication token."""
        response = self.session.post(
            f"{self.base_url}/login/refresh",
            headers={"Authorization": f"Bearer {self.refresh_token}"}
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

        return self

    def create_job(self, job: Job) -> Dict[str, Any]:
        """Create a new job."""
        response = self.session.post(
            f"{self.base_url}/scheduling/jobs",
            json=job.to_dict()
        )
        response.raise_for_status()
        return response.json()

    def solve_schedule(
        self,
        jobs: List[Job],
        machines: List[Dict],
        operators: List[Dict],
        max_time: int = 60,
        objectives: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Solve scheduling problem."""
        problem = {
            "problem": {
                "jobs": [j.to_dict() for j in jobs],
                "machines": machines,
                "operators": operators,
                "calendar": self._default_calendar()
            },
            "optimization_parameters": {
                "max_solving_time": max_time,
                "objective_weights": objectives or {
                    "makespan": 0.4,
                    "total_cost": 0.3,
                    "tardiness": 0.3
                }
            }
        }

        response = self.session.post(
            f"{self.base_url}/scheduling/solve",
            json=problem
        )
        response.raise_for_status()
        return response.json()

    def get_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Get schedule details."""
        response = self.session.get(
            f"{self.base_url}/scheduling/schedules/{schedule_id}"
        )
        response.raise_for_status()
        return response.json()

    def get_analytics(self, schedule_id: str) -> Dict[str, Any]:
        """Get schedule analytics."""
        response = self.session.get(
            f"{self.base_url}/scheduling/schedules/{schedule_id}/analytics"
        )
        response.raise_for_status()
        return response.json()

    def optimize_resources(
        self,
        schedule_id: str,
        target_utilization: float = 0.8,
        resource_costs: Dict[str, Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Optimize resources for fixed schedule."""
        payload = {
            "schedule_id": schedule_id,
            "target_utilization": target_utilization,
            "resource_costs": resource_costs or self._default_costs()
        }

        response = self.session.post(
            f"{self.base_url}/scheduling/optimize-resources",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def monitor_schedule(self, schedule_id: str):
        """Monitor schedule execution via WebSocket."""
        uri = f"wss://{self.base_url.replace('http://', '').replace('https://', '')}/ws?token={self.access_token}"

        async with websockets.connect(uri) as websocket:
            # Subscribe to schedule channel
            await websocket.send(json.dumps({
                "action": "subscribe",
                "channels": [f"schedule.{schedule_id}"]
            }))

            print(f"Monitoring schedule {schedule_id}...")

            async for message in websocket:
                event = json.loads(message)
                self._handle_websocket_event(event)

    def _handle_websocket_event(self, event: Dict[str, Any]):
        """Handle WebSocket events."""
        if event["event"] == "schedule.progress":
            data = event["data"]
            print(f"Progress: {data['progress']:.1%} - Active: {data['active_tasks']}")
        elif event["event"] == "task.status_changed":
            data = event["data"]
            print(f"Task {data['task_id']}: {data['new_status']}")
        elif event["event"] == "alert":
            data = event["data"]
            print(f"⚠️ {data['level']}: {data['message']}")

    def _default_calendar(self) -> Dict[str, Any]:
        """Get default business calendar."""
        return {
            "weekday_hours": {
                str(i): {"start_time": "07:00", "end_time": "16:00"}
                for i in range(5)
            },
            "holidays": []
        }

    def _default_costs(self) -> Dict[str, Dict[str, float]]:
        """Get default resource costs."""
        return {
            "machines": {
                "cnc-01": 150.00,
                "cnc-02": 150.00,
                "weld-01": 120.00
            },
            "operators": {
                "MACHINING_L3": 75.00,
                "MACHINING_L2": 60.00,
                "MACHINING_L1": 45.00
            }
        }

# Example usage
def main():
    # Initialize client
    client = VulcanEngineClient(
        base_url="http://localhost:8000/api/v1",
        username="admin@example.com",
        password="changethis123"
    )

    # Create a job
    job = Job(
        job_number=f"JOB-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        tasks=[
            Task(
                operation_number=10,
                machine_options=["cnc-01", "cnc-02"],
                duration_minutes=60,
                skill_requirements={SkillType.MACHINING: 2}
            ),
            Task(
                operation_number=20,
                machine_options=["weld-01"],
                duration_minutes=45,
                skill_requirements={SkillType.WELDING: 1},
                predecessors=["task-001"]
            )
        ],
        priority=1,
        due_date=datetime.now() + timedelta(days=7)
    )

    # Create job
    job_response = client.create_job(job)
    print(f"Created job: {job_response['id']}")

    # Get available resources
    machines = [
        {
            "id": "cnc-01",
            "name": "CNC Machine 01",
            "zone": "Zone-A",
            "skill_requirements": [{"skill_type": "MACHINING", "minimum_level": 2}],
            "is_attended": True
        }
    ]

    operators = [
        {
            "id": "op-001",
            "name": "John Smith",
            "employee_id": "EMP001",
            "skills": [{"skill_type": "MACHINING", "level": 3}],
            "shift_pattern": "day"
        }
    ]

    # Solve schedule
    solution = client.solve_schedule([job], machines, operators)
    print(f"Schedule created: {solution['schedule_id']}")
    print(f"Makespan: {solution['makespan_hours']} hours")
    print(f"Total cost: ${solution['total_cost']}")

    # Get analytics
    analytics = client.get_analytics(solution['schedule_id'])
    print(f"Machine utilization: {analytics['kpis']['machine_utilization']:.1%}")

    # Optimize resources
    optimization = client.optimize_resources(solution['schedule_id'])
    print(f"Optimized cost: ${optimization['total_cost']}")

    # Monitor schedule (async)
    # asyncio.run(client.monitor_schedule(solution['schedule_id']))

if __name__ == "__main__":
    main()
```

## JavaScript/TypeScript Examples

### Complete TypeScript Client

```typescript
/**
 * Vulcan Engine TypeScript Client
 * Full-featured client with TypeScript support
 */

interface Credentials {
  username: string;
  password: string;
}

interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface Task {
  operation_number: number;
  machine_options: string[];
  duration_minutes: number;
  skill_requirements: Record<string, number>;
  predecessors?: string[];
}

interface Job {
  job_number: string;
  tasks: Task[];
  priority?: number;
  due_date?: string;
}

interface Machine {
  id: string;
  name: string;
  zone: string;
  skill_requirements: Array<{
    skill_type: string;
    minimum_level: number;
  }>;
  is_attended: boolean;
  is_available: boolean;
}

interface Operator {
  id: string;
  name: string;
  employee_id: string;
  skills: Array<{
    skill_type: string;
    level: number;
  }>;
  shift_pattern: string;
}

interface Schedule {
  schedule_id: string;
  status: string;
  makespan_hours: number;
  total_cost: number;
  assignments: Array<{
    task_id: string;
    machine_id: string;
    operator_ids: string[];
    planned_start: string;
    planned_end: string;
  }>;
}

class VulcanEngineClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async authenticate(credentials: Credentials): Promise<void> {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await fetch(`${this.baseUrl}/login/access-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Authentication failed: ${response.statusText}`);
    }

    const data: Token = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
  }

  async refreshAuth(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/login/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.refreshToken}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Token refresh failed: ${response.statusText}`);
    }

    const data: Token = await response.json();
    this.accessToken = data.access_token;
  }

  private async request<T>(
    method: string,
    endpoint: string,
    body?: any
  ): Promise<T> {
    const headers: HeadersInit = {
      'Authorization': `Bearer ${this.accessToken}`,
    };

    if (body) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
      // Try refreshing token
      await this.refreshAuth();
      // Retry request
      return this.request<T>(method, endpoint, body);
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || response.statusText);
    }

    return response.json();
  }

  async createJob(job: Job): Promise<{ id: string; task_count: number }> {
    return this.request('POST', '/scheduling/jobs', job);
  }

  async solveSchedule(
    jobs: Job[],
    machines: Machine[],
    operators: Operator[],
    options?: {
      maxTime?: number;
      objectives?: Record<string, number>;
    }
  ): Promise<Schedule> {
    const problem = {
      problem: {
        jobs,
        machines,
        operators,
        calendar: {
          weekday_hours: {
            '0': { start_time: '07:00', end_time: '16:00' },
            '1': { start_time: '07:00', end_time: '16:00' },
            '2': { start_time: '07:00', end_time: '16:00' },
            '3': { start_time: '07:00', end_time: '16:00' },
            '4': { start_time: '07:00', end_time: '16:00' },
          },
          holidays: [],
        },
      },
      optimization_parameters: {
        max_solving_time: options?.maxTime || 60,
        objective_weights: options?.objectives || {
          makespan: 0.4,
          total_cost: 0.3,
          tardiness: 0.3,
        },
      },
    };

    return this.request('POST', '/scheduling/solve', problem);
  }

  async getSchedule(scheduleId: string): Promise<any> {
    return this.request('GET', `/scheduling/schedules/${scheduleId}`);
  }

  async getAnalytics(scheduleId: string): Promise<any> {
    return this.request('GET', `/scheduling/schedules/${scheduleId}/analytics`);
  }

  connectWebSocket(scheduleId: string): WebSocket {
    const wsUrl = this.baseUrl
      .replace('http://', 'ws://')
      .replace('https://', 'wss://');

    const ws = new WebSocket(`${wsUrl}/ws?token=${this.accessToken}`);

    ws.onopen = () => {
      // Subscribe to schedule updates
      ws.send(JSON.stringify({
        action: 'subscribe',
        channels: [`schedule.${scheduleId}`],
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleWebSocketEvent(data);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  }

  private handleWebSocketEvent(event: any): void {
    switch (event.event) {
      case 'schedule.progress':
        console.log(`Progress: ${(event.data.progress * 100).toFixed(1)}%`);
        break;
      case 'task.status_changed':
        console.log(`Task ${event.data.task_id}: ${event.data.new_status}`);
        break;
      case 'alert':
        console.warn(`Alert: ${event.data.message}`);
        break;
    }
  }
}

// Example usage
async function main() {
  const client = new VulcanEngineClient('http://localhost:8000/api/v1');

  // Authenticate
  await client.authenticate({
    username: 'admin@example.com',
    password: 'changethis123',
  });

  // Create a job
  const job: Job = {
    job_number: `JOB-${Date.now()}`,
    tasks: [
      {
        operation_number: 10,
        machine_options: ['cnc-01', 'cnc-02'],
        duration_minutes: 60,
        skill_requirements: { MACHINING: 2 },
      },
      {
        operation_number: 20,
        machine_options: ['weld-01'],
        duration_minutes: 45,
        skill_requirements: { WELDING: 1 },
        predecessors: ['task-001'],
      },
    ],
    priority: 1,
    due_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
  };

  const jobResponse = await client.createJob(job);
  console.log('Created job:', jobResponse.id);

  // Define resources
  const machines: Machine[] = [
    {
      id: 'cnc-01',
      name: 'CNC Machine 01',
      zone: 'Zone-A',
      skill_requirements: [
        { skill_type: 'MACHINING', minimum_level: 2 },
      ],
      is_attended: true,
      is_available: true,
    },
  ];

  const operators: Operator[] = [
    {
      id: 'op-001',
      name: 'John Smith',
      employee_id: 'EMP001',
      skills: [
        { skill_type: 'MACHINING', level: 3 },
      ],
      shift_pattern: 'day',
    },
  ];

  // Solve schedule
  const schedule = await client.solveSchedule([job], machines, operators);
  console.log('Schedule created:', schedule.schedule_id);
  console.log('Makespan:', schedule.makespan_hours, 'hours');
  console.log('Total cost: $', schedule.total_cost);

  // Get analytics
  const analytics = await client.getAnalytics(schedule.schedule_id);
  console.log('Machine utilization:', analytics.kpis.machine_utilization);

  // Monitor schedule
  const ws = client.connectWebSocket(schedule.schedule_id);
}

main().catch(console.error);
```

## C# Examples

### Complete C# Client

```csharp
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;

namespace VulcanEngine.Client
{
    public enum SkillType
    {
        MACHINING,
        WELDING,
        ASSEMBLY,
        INSPECTION,
        PROGRAMMING
    }

    public class Task
    {
        public int OperationNumber { get; set; }
        public List<string> MachineOptions { get; set; }
        public int DurationMinutes { get; set; }
        public Dictionary<string, int> SkillRequirements { get; set; }
        public List<string> Predecessors { get; set; }
    }

    public class Job
    {
        public string JobNumber { get; set; }
        public List<Task> Tasks { get; set; }
        public int Priority { get; set; }
        public DateTime? DueDate { get; set; }
    }

    public class Schedule
    {
        public string ScheduleId { get; set; }
        public string Status { get; set; }
        public double MakespanHours { get; set; }
        public decimal TotalCost { get; set; }
        public List<Assignment> Assignments { get; set; }
    }

    public class Assignment
    {
        public string TaskId { get; set; }
        public string MachineId { get; set; }
        public List<string> OperatorIds { get; set; }
        public DateTime PlannedStart { get; set; }
        public DateTime PlannedEnd { get; set; }
    }

    public class VulcanEngineClient
    {
        private readonly HttpClient _httpClient;
        private string _accessToken;
        private string _refreshToken;
        private readonly string _baseUrl;

        public VulcanEngineClient(string baseUrl)
        {
            _baseUrl = baseUrl.TrimEnd('/');
            _httpClient = new HttpClient();
        }

        public async Task AuthenticateAsync(string username, string password)
        {
            var formContent = new FormUrlEncodedContent(new[]
            {
                new KeyValuePair<string, string>("username", username),
                new KeyValuePair<string, string>("password", password)
            });

            var response = await _httpClient.PostAsync(
                $"{_baseUrl}/login/access-token",
                formContent
            );

            response.EnsureSuccessStatusCode();

            var content = await response.Content.ReadAsStringAsync();
            dynamic tokens = JsonConvert.DeserializeObject(content);

            _accessToken = tokens.access_token;
            _refreshToken = tokens.refresh_token;

            _httpClient.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", _accessToken);
        }

        public async Task<Job> CreateJobAsync(Job job)
        {
            var json = JsonConvert.SerializeObject(job);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync(
                $"{_baseUrl}/scheduling/jobs",
                content
            );

            response.EnsureSuccessStatusCode();

            var responseContent = await response.Content.ReadAsStringAsync();
            return JsonConvert.DeserializeObject<Job>(responseContent);
        }

        public async Task<Schedule> SolveScheduleAsync(
            List<Job> jobs,
            List<object> machines,
            List<object> operators,
            int maxTime = 60
        )
        {
            var problem = new
            {
                problem = new
                {
                    jobs,
                    machines,
                    operators,
                    calendar = new
                    {
                        weekday_hours = new Dictionary<string, object>
                        {
                            ["0"] = new { start_time = "07:00", end_time = "16:00" },
                            ["1"] = new { start_time = "07:00", end_time = "16:00" },
                            ["2"] = new { start_time = "07:00", end_time = "16:00" },
                            ["3"] = new { start_time = "07:00", end_time = "16:00" },
                            ["4"] = new { start_time = "07:00", end_time = "16:00" }
                        },
                        holidays = new List<string>()
                    }
                },
                optimization_parameters = new
                {
                    max_solving_time = maxTime,
                    objective_weights = new
                    {
                        makespan = 0.4,
                        total_cost = 0.3,
                        tardiness = 0.3
                    }
                }
            };

            var json = JsonConvert.SerializeObject(problem);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync(
                $"{_baseUrl}/scheduling/solve",
                content
            );

            response.EnsureSuccessStatusCode();

            var responseContent = await response.Content.ReadAsStringAsync();
            return JsonConvert.DeserializeObject<Schedule>(responseContent);
        }

        public async Task<object> GetAnalyticsAsync(string scheduleId)
        {
            var response = await _httpClient.GetAsync(
                $"{_baseUrl}/scheduling/schedules/{scheduleId}/analytics"
            );

            response.EnsureSuccessStatusCode();

            var content = await response.Content.ReadAsStringAsync();
            return JsonConvert.DeserializeObject(content);
        }
    }

    // Example usage
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new VulcanEngineClient("http://localhost:8000/api/v1");

            // Authenticate
            await client.AuthenticateAsync("admin@example.com", "changethis123");

            // Create a job
            var job = new Job
            {
                JobNumber = $"JOB-{DateTime.Now:yyyyMMdd-HHmmss}",
                Tasks = new List<Task>
                {
                    new Task
                    {
                        OperationNumber = 10,
                        MachineOptions = new List<string> { "cnc-01", "cnc-02" },
                        DurationMinutes = 60,
                        SkillRequirements = new Dictionary<string, int>
                        {
                            ["MACHINING"] = 2
                        }
                    }
                },
                Priority = 1,
                DueDate = DateTime.Now.AddDays(7)
            };

            var createdJob = await client.CreateJobAsync(job);
            Console.WriteLine($"Created job: {createdJob.JobNumber}");

            // Solve schedule
            var machines = new List<object>
            {
                new
                {
                    id = "cnc-01",
                    name = "CNC Machine 01",
                    zone = "Zone-A",
                    skill_requirements = new[]
                    {
                        new { skill_type = "MACHINING", minimum_level = 2 }
                    },
                    is_attended = true,
                    is_available = true
                }
            };

            var operators = new List<object>
            {
                new
                {
                    id = "op-001",
                    name = "John Smith",
                    employee_id = "EMP001",
                    skills = new[]
                    {
                        new { skill_type = "MACHINING", level = 3 }
                    },
                    shift_pattern = "day"
                }
            };

            var schedule = await client.SolveScheduleAsync(
                new List<Job> { job },
                machines,
                operators
            );

            Console.WriteLine($"Schedule created: {schedule.ScheduleId}");
            Console.WriteLine($"Makespan: {schedule.MakespanHours} hours");
            Console.WriteLine($"Total cost: ${schedule.TotalCost}");

            // Get analytics
            var analytics = await client.GetAnalyticsAsync(schedule.ScheduleId);
            Console.WriteLine($"Analytics: {JsonConvert.SerializeObject(analytics)}");
        }
    }
}
```

## Java Examples

### Complete Java Client

```java
package com.vulcanengine.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.*;
import java.io.IOException;
import java.time.LocalDateTime;
import java.util.*;

public class VulcanEngineClient {
    private final String baseUrl;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;
    private String accessToken;
    private String refreshToken;

    public VulcanEngineClient(String baseUrl) {
        this.baseUrl = baseUrl.replaceAll("/$", "");
        this.httpClient = new OkHttpClient();
        this.objectMapper = new ObjectMapper();
    }

    public void authenticate(String username, String password) throws IOException {
        RequestBody formBody = new FormBody.Builder()
            .add("username", username)
            .add("password", password)
            .build();

        Request request = new Request.Builder()
            .url(baseUrl + "/login/access-token")
            .post(formBody)
            .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Authentication failed: " + response);
            }

            Map<String, Object> tokens = objectMapper.readValue(
                response.body().string(),
                Map.class
            );

            accessToken = (String) tokens.get("access_token");
            refreshToken = (String) tokens.get("refresh_token");
        }
    }

    public Map<String, Object> createJob(Job job) throws IOException {
        String json = objectMapper.writeValueAsString(job);
        RequestBody body = RequestBody.create(
            json,
            MediaType.parse("application/json")
        );

        Request request = new Request.Builder()
            .url(baseUrl + "/scheduling/jobs")
            .header("Authorization", "Bearer " + accessToken)
            .post(body)
            .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Failed to create job: " + response);
            }

            return objectMapper.readValue(
                response.body().string(),
                Map.class
            );
        }
    }

    public Schedule solveSchedule(
        List<Job> jobs,
        List<Machine> machines,
        List<Operator> operators
    ) throws IOException {
        Map<String, Object> problem = new HashMap<>();
        Map<String, Object> problemData = new HashMap<>();
        problemData.put("jobs", jobs);
        problemData.put("machines", machines);
        problemData.put("operators", operators);
        problemData.put("calendar", createDefaultCalendar());
        problem.put("problem", problemData);

        Map<String, Object> parameters = new HashMap<>();
        parameters.put("max_solving_time", 60);
        parameters.put("objective_weights", Map.of(
            "makespan", 0.4,
            "total_cost", 0.3,
            "tardiness", 0.3
        ));
        problem.put("optimization_parameters", parameters);

        String json = objectMapper.writeValueAsString(problem);
        RequestBody body = RequestBody.create(
            json,
            MediaType.parse("application/json")
        );

        Request request = new Request.Builder()
            .url(baseUrl + "/scheduling/solve")
            .header("Authorization", "Bearer " + accessToken)
            .post(body)
            .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Failed to solve schedule: " + response);
            }

            return objectMapper.readValue(
                response.body().string(),
                Schedule.class
            );
        }
    }

    private Map<String, Object> createDefaultCalendar() {
        Map<String, Object> calendar = new HashMap<>();
        Map<String, Object> weekdayHours = new HashMap<>();

        for (int i = 0; i < 5; i++) {
            weekdayHours.put(String.valueOf(i), Map.of(
                "start_time", "07:00",
                "end_time", "16:00"
            ));
        }

        calendar.put("weekday_hours", weekdayHours);
        calendar.put("holidays", new ArrayList<>());

        return calendar;
    }

    // Data classes
    public static class Job {
        public String jobNumber;
        public List<Task> tasks;
        public int priority;
        public String dueDate;
    }

    public static class Task {
        public int operationNumber;
        public List<String> machineOptions;
        public int durationMinutes;
        public Map<String, Integer> skillRequirements;
        public List<String> predecessors;
    }

    public static class Machine {
        public String id;
        public String name;
        public String zone;
        public List<SkillRequirement> skillRequirements;
        public boolean isAttended;
        public boolean isAvailable;
    }

    public static class Operator {
        public String id;
        public String name;
        public String employeeId;
        public List<Skill> skills;
        public String shiftPattern;
    }

    public static class SkillRequirement {
        public String skillType;
        public int minimumLevel;
    }

    public static class Skill {
        public String skillType;
        public int level;
    }

    public static class Schedule {
        public String scheduleId;
        public String status;
        public double makespanHours;
        public double totalCost;
        public List<Assignment> assignments;
    }

    public static class Assignment {
        public String taskId;
        public String machineId;
        public List<String> operatorIds;
        public String plannedStart;
        public String plannedEnd;
    }

    // Example usage
    public static void main(String[] args) throws IOException {
        VulcanEngineClient client = new VulcanEngineClient("http://localhost:8000/api/v1");

        // Authenticate
        client.authenticate("admin@example.com", "changethis123");

        // Create a job
        Job job = new Job();
        job.jobNumber = "JOB-" + System.currentTimeMillis();
        job.priority = 1;
        job.dueDate = LocalDateTime.now().plusDays(7).toString();

        Task task = new Task();
        task.operationNumber = 10;
        task.machineOptions = Arrays.asList("cnc-01", "cnc-02");
        task.durationMinutes = 60;
        task.skillRequirements = Map.of("MACHINING", 2);

        job.tasks = Arrays.asList(task);

        Map<String, Object> createdJob = client.createJob(job);
        System.out.println("Created job: " + createdJob.get("id"));

        // Define resources
        Machine machine = new Machine();
        machine.id = "cnc-01";
        machine.name = "CNC Machine 01";
        machine.zone = "Zone-A";
        machine.isAttended = true;
        machine.isAvailable = true;

        SkillRequirement skillReq = new SkillRequirement();
        skillReq.skillType = "MACHINING";
        skillReq.minimumLevel = 2;
        machine.skillRequirements = Arrays.asList(skillReq);

        Operator operator = new Operator();
        operator.id = "op-001";
        operator.name = "John Smith";
        operator.employeeId = "EMP001";
        operator.shiftPattern = "day";

        Skill skill = new Skill();
        skill.skillType = "MACHINING";
        skill.level = 3;
        operator.skills = Arrays.asList(skill);

        // Solve schedule
        Schedule schedule = client.solveSchedule(
            Arrays.asList(job),
            Arrays.asList(machine),
            Arrays.asList(operator)
        );

        System.out.println("Schedule created: " + schedule.scheduleId);
        System.out.println("Makespan: " + schedule.makespanHours + " hours");
        System.out.println("Total cost: $" + schedule.totalCost);
    }
}
```

## Go Examples

### Complete Go Client

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
    "net/url"
    "strings"
    "time"
)

type VulcanClient struct {
    BaseURL      string
    AccessToken  string
    RefreshToken string
    HTTPClient   *http.Client
}

type Credentials struct {
    Username string `json:"username"`
    Password string `json:"password"`
}

type Token struct {
    AccessToken  string `json:"access_token"`
    RefreshToken string `json:"refresh_token"`
    TokenType    string `json:"token_type"`
}

type Task struct {
    OperationNumber   int               `json:"operation_number"`
    MachineOptions    []string          `json:"machine_options"`
    DurationMinutes   int               `json:"duration_minutes"`
    SkillRequirements map[string]int    `json:"skill_requirements"`
    Predecessors      []string          `json:"predecessors,omitempty"`
}

type Job struct {
    JobNumber string    `json:"job_number"`
    Tasks     []Task    `json:"tasks"`
    Priority  int       `json:"priority"`
    DueDate   *string   `json:"due_date,omitempty"`
}

type Schedule struct {
    ScheduleID    string       `json:"schedule_id"`
    Status        string       `json:"status"`
    MakespanHours float64      `json:"makespan_hours"`
    TotalCost     float64      `json:"total_cost"`
    Assignments   []Assignment `json:"assignments"`
}

type Assignment struct {
    TaskID       string   `json:"task_id"`
    MachineID    string   `json:"machine_id"`
    OperatorIDs  []string `json:"operator_ids"`
    PlannedStart string   `json:"planned_start"`
    PlannedEnd   string   `json:"planned_end"`
}

func NewVulcanClient(baseURL string) *VulcanClient {
    return &VulcanClient{
        BaseURL:    strings.TrimRight(baseURL, "/"),
        HTTPClient: &http.Client{Timeout: 30 * time.Second},
    }
}

func (c *VulcanClient) Authenticate(username, password string) error {
    data := url.Values{}
    data.Set("username", username)
    data.Set("password", password)

    req, err := http.NewRequest(
        "POST",
        c.BaseURL+"/login/access-token",
        strings.NewReader(data.Encode()),
    )
    if err != nil {
        return err
    }

    req.Header.Add("Content-Type", "application/x-www-form-urlencoded")

    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("authentication failed: %s", resp.Status)
    }

    var token Token
    if err := json.NewDecoder(resp.Body).Decode(&token); err != nil {
        return err
    }

    c.AccessToken = token.AccessToken
    c.RefreshToken = token.RefreshToken

    return nil
}

func (c *VulcanClient) makeRequest(method, endpoint string, body interface{}) (*http.Response, error) {
    var reqBody []byte
    var err error

    if body != nil {
        reqBody, err = json.Marshal(body)
        if err != nil {
            return nil, err
        }
    }

    req, err := http.NewRequest(
        method,
        c.BaseURL+endpoint,
        bytes.NewBuffer(reqBody),
    )
    if err != nil {
        return nil, err
    }

    req.Header.Add("Authorization", "Bearer "+c.AccessToken)
    if body != nil {
        req.Header.Add("Content-Type", "application/json")
    }

    return c.HTTPClient.Do(req)
}

func (c *VulcanClient) CreateJob(job Job) (map[string]interface{}, error) {
    resp, err := c.makeRequest("POST", "/scheduling/jobs", job)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("failed to create job: %s", resp.Status)
    }

    var result map[string]interface{}
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }

    return result, nil
}

func (c *VulcanClient) SolveSchedule(jobs []Job, machines, operators []interface{}) (*Schedule, error) {
    problem := map[string]interface{}{
        "problem": map[string]interface{}{
            "jobs":      jobs,
            "machines":  machines,
            "operators": operators,
            "calendar": map[string]interface{}{
                "weekday_hours": map[string]interface{}{
                    "0": map[string]string{"start_time": "07:00", "end_time": "16:00"},
                    "1": map[string]string{"start_time": "07:00", "end_time": "16:00"},
                    "2": map[string]string{"start_time": "07:00", "end_time": "16:00"},
                    "3": map[string]string{"start_time": "07:00", "end_time": "16:00"},
                    "4": map[string]string{"start_time": "07:00", "end_time": "16:00"},
                },
                "holidays": []string{},
            },
        },
        "optimization_parameters": map[string]interface{}{
            "max_solving_time": 60,
            "objective_weights": map[string]float64{
                "makespan":   0.4,
                "total_cost": 0.3,
                "tardiness":  0.3,
            },
        },
    }

    resp, err := c.makeRequest("POST", "/scheduling/solve", problem)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        body, _ := ioutil.ReadAll(resp.Body)
        return nil, fmt.Errorf("failed to solve schedule: %s - %s", resp.Status, string(body))
    }

    var schedule Schedule
    if err := json.NewDecoder(resp.Body).Decode(&schedule); err != nil {
        return nil, err
    }

    return &schedule, nil
}

func main() {
    client := NewVulcanClient("http://localhost:8000/api/v1")

    // Authenticate
    if err := client.Authenticate("admin@example.com", "changethis123"); err != nil {
        panic(err)
    }
    fmt.Println("Authenticated successfully")

    // Create a job
    job := Job{
        JobNumber: fmt.Sprintf("JOB-%d", time.Now().Unix()),
        Tasks: []Task{
            {
                OperationNumber:   10,
                MachineOptions:    []string{"cnc-01", "cnc-02"},
                DurationMinutes:   60,
                SkillRequirements: map[string]int{"MACHINING": 2},
            },
        },
        Priority: 1,
    }

    createdJob, err := client.CreateJob(job)
    if err != nil {
        panic(err)
    }
    fmt.Printf("Created job: %v\n", createdJob["id"])

    // Define resources
    machines := []interface{}{
        map[string]interface{}{
            "id":   "cnc-01",
            "name": "CNC Machine 01",
            "zone": "Zone-A",
            "skill_requirements": []map[string]interface{}{
                {"skill_type": "MACHINING", "minimum_level": 2},
            },
            "is_attended":  true,
            "is_available": true,
        },
    }

    operators := []interface{}{
        map[string]interface{}{
            "id":          "op-001",
            "name":        "John Smith",
            "employee_id": "EMP001",
            "skills": []map[string]interface{}{
                {"skill_type": "MACHINING", "level": 3},
            },
            "shift_pattern": "day",
        },
    }

    // Solve schedule
    schedule, err := client.SolveSchedule([]Job{job}, machines, operators)
    if err != nil {
        panic(err)
    }

    fmt.Printf("Schedule created: %s\n", schedule.ScheduleID)
    fmt.Printf("Makespan: %.2f hours\n", schedule.MakespanHours)
    fmt.Printf("Total cost: $%.2f\n", schedule.TotalCost)
}
```

## cURL Examples

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethis123"

# Save token to variable
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethis123" \
  | jq -r '.access_token')
```

### Create Job

```bash
curl -X POST http://localhost:8000/api/v1/scheduling/domain/jobs/standard \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_number": "JOB-001",
    "operation_count": 50,
    "priority": 1,
    "due_date": "2025-08-15T16:00:00Z"
  }'
```

### Solve Schedule

```bash
curl -X POST http://localhost:8000/api/v1/scheduling/solve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "problem": {
      "jobs": [{
        "job_number": "JOB-001",
        "tasks": [{
          "operation_number": 10,
          "machine_options": ["cnc-01"],
          "duration_minutes": 60,
          "skill_requirements": {"MACHINING": 2}
        }],
        "priority": 1,
        "due_date": "2025-08-15T16:00:00Z"
      }],
      "machines": [{
        "id": "cnc-01",
        "name": "CNC Machine 01",
        "zone": "Zone-A",
        "skill_requirements": [{"skill_type": "MACHINING", "minimum_level": 2}],
        "is_attended": true,
        "is_available": true
      }],
      "operators": [{
        "id": "op-001",
        "name": "John Smith",
        "employee_id": "EMP001",
        "skills": [{"skill_type": "MACHINING", "level": 3}],
        "shift_pattern": "day"
      }],
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
  }'
```

### Get Schedule Analytics

```bash
SCHEDULE_ID="660e8400-e29b-41d4-a716-446655440001"

curl -X GET "http://localhost:8000/api/v1/scheduling/schedules/$SCHEDULE_ID/analytics" \
  -H "Authorization: Bearer $TOKEN"
```

### WebSocket Connection

```bash
# Using wscat (npm install -g wscat)
wscat -c "ws://localhost:8000/ws?token=$TOKEN" \
  -x '{"action":"subscribe","channels":["schedule.660e8400-e29b-41d4-a716-446655440001"]}'
```

### Health Check

```bash
curl -X GET http://localhost:8000/api/v1/health
```

### List Resources

```bash
# List machines
curl -X GET "http://localhost:8000/api/v1/scheduling/machines?zone=Zone-A&available=true" \
  -H "Authorization: Bearer $TOKEN"

# List operators
curl -X GET "http://localhost:8000/api/v1/scheduling/operators?skill=MACHINING&min_level=2" \
  -H "Authorization: Bearer $TOKEN"
```

### Batch Operations

```bash
# Create multiple jobs in parallel
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/v1/scheduling/domain/jobs/standard \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"job_number\": \"JOB-00$i\",
      \"operation_count\": 50,
      \"priority\": 1,
      \"due_date\": \"2025-08-15T16:00:00Z\"
    }" &
done
wait
```
