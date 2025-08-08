# Vulcan Engine Observability Guide

This guide covers the comprehensive observability infrastructure implemented for the Vulcan Engine scheduling system, including logging, metrics, tracing, health checks, and monitoring.

## 🎯 Overview

The Vulcan Engine includes enterprise-grade observability features:

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics Collection**: Prometheus metrics for all system components
- **Distributed Tracing**: OpenTelemetry tracing for request flows
- **Health Checks**: Comprehensive system health monitoring
- **Circuit Breakers**: Resilience patterns for external service calls
- **Performance Monitoring**: Detailed OR-Tools solver observability
- **Development Tools**: Debugging utilities and test data generation

## 🚀 Quick Start

### 1. Install Dependencies

```bash
./scripts/install-dependencies.sh
```

### 2. Configure Environment

Add to your `.env` file:

```env
# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_SQL=false

# Observability Configuration
ENABLE_METRICS=true
METRICS_PORT=8001
ENABLE_TRACING=true

# Circuit Breaker Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Performance Monitoring
ENABLE_PERFORMANCE_MONITORING=true
SLOW_QUERY_THRESHOLD_SECONDS=1.0
SCHEDULER_TIMEOUT_SECONDS=300
```

### 3. Start the Application

```bash
fastapi dev app/main.py
```

### 4. Access Observability Endpoints

- **API Documentation**: http://localhost:8000/docs
- **Health Checks**: http://localhost:8000/health
- **Metrics**: http://localhost:8001/metrics
- **Debug Dashboard**: http://localhost:8000/api/v1/debug/dashboard (local only)

## 📊 Key Features

### Structured Logging

All log entries include:
- **Correlation ID**: Tracks requests across services
- **User ID**: User context for authenticated requests
- **Timestamp**: ISO format timestamps
- **Context**: Rich contextual information
- **Performance**: Duration and metrics

Example log entry:
```json
{
  "timestamp": "2025-01-08T10:30:45.123Z",
  "level": "info",
  "message": "Schedule optimization completed successfully",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user123",
  "operation": "schedule_optimization",
  "duration_seconds": 2.45,
  "status": "OPTIMAL",
  "makespan_minutes": 1440,
  "jobs_count": 5
}
```

### Prometheus Metrics

Comprehensive metrics collection:

#### HTTP Metrics
- `vulcan_http_requests_total`: Total HTTP requests by method, endpoint, status
- `vulcan_http_request_duration_seconds`: HTTP request duration histograms

#### Scheduler Metrics
- `vulcan_scheduler_operations_total`: Total scheduling operations by type and status
- `vulcan_scheduler_operation_duration_seconds`: Scheduling operation durations
- `vulcan_solver_solve_time_seconds`: OR-Tools solver execution time
- `vulcan_solver_status_total`: Solver status counters

#### Database Metrics
- `vulcan_database_operations_total`: Database operations by type and table
- `vulcan_database_operation_duration_seconds`: Database operation durations

#### Circuit Breaker Metrics
- `vulcan_circuit_breaker_state`: Circuit breaker state (0=closed, 0.5=half-open, 1=open)

#### Business Metrics
- `vulcan_active_jobs`: Current number of active jobs
- `vulcan_completed_tasks_total`: Total completed tasks

### Health Checks

#### Available Endpoints

1. **Overall Health**: `GET /health`
   - Comprehensive system status
   - All component health checks
   - Summary statistics

2. **Specific Health Check**: `GET /health/{check_name}`
   - Individual component status
   - Detailed diagnostics

3. **Liveness Probe**: `GET /health/live`
   - Simple alive check for orchestration
   - Minimal overhead

4. **Readiness Probe**: `GET /health/ready`
   - Service readiness for traffic
   - Critical component checks

5. **Circuit Breaker Status**: `GET /health/circuit-breakers`
   - All circuit breaker states
   - Failure statistics

#### Health Check Components

- **Database**: Connectivity, performance, connection count
- **Solver**: OR-Tools availability and functionality
- **System Resources**: CPU, memory, disk usage
- **Application**: Configuration validation, security checks

### Circuit Breakers

Automatic protection against cascading failures:

```python
from app.core.circuit_breaker import with_resilience

@with_resilience("database", max_retry_attempts=3)
async def database_operation():
    # Your database operation here
    pass
```

Available decorators:
- `@with_circuit_breaker`: Circuit breaker only
- `@with_retry`: Retry logic only
- `@with_resilience`: Combined circuit breaker + retry
- `@with_timeout`: Timeout protection

### Performance Monitoring

Detailed performance tracking:

```python
from app.core.observability import monitor_performance

@monitor_performance("optimization", include_args=True)
async def optimize_schedule():
    # Your optimization logic
    pass
```

## 🔧 Development Tools

### Debug Dashboard

Access at http://localhost:8000/api/v1/debug/dashboard (local environment only)

Features:
- System metrics visualization
- Health status overview
- Test data generation
- Performance profiling
- Request logs inspection

### API Endpoints

#### Debug Information
- `GET /debug/system-info`: System resource information
- `GET /debug/environment`: Environment configuration
- `GET /debug/request-logs`: Recent request logs

#### Profiling
- `POST /debug/profiler/start`: Start performance profiling
- `POST /debug/profiler/{session_id}/stop`: Stop and get results

#### Test Data
- `GET /debug/test-data/scenario`: Generate test scenarios
- Parameters: `jobs`, `machines`, `operators`

### Test Data Generator

Generate realistic test data:

```python
from app.core.development import test_data_generator

# Generate complete scenario
scenario = test_data_generator.generate_complete_scenario(
    job_count=5,
    machine_count=10,
    operator_count=15
)

# Generate specific entities
jobs = test_data_generator.generate_jobs(count=5)
machines = test_data_generator.generate_machines(count=10)
operators = test_data_generator.generate_operators(count=15)
```

## 📈 Monitoring Stack

### Setup Monitoring Infrastructure

Generate monitoring configuration:

```python
from app.core.monitoring import MonitoringSetup

monitoring = MonitoringSetup()
config_files = monitoring.generate_all_configs()
```

This creates:
- `prometheus.yml`: Prometheus configuration
- `vulcan_alerts.yml`: Alerting rules
- `vulcan_dashboard.json`: Grafana dashboard
- `alertmanager.yml`: AlertManager configuration
- `docker-compose.monitoring.yml`: Complete monitoring stack

### Start Monitoring Stack

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

Access points:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **AlertManager**: http://localhost:9093

### Key Dashboards

The Grafana dashboard includes:
- System overview with key metrics
- HTTP request rates and response times
- Solver performance and status
- Database operation metrics
- Circuit breaker status
- System resource utilization

### Alerting Rules

Configured alerts:
- Service downtime
- High error rates (>10%)
- High response times (>2s)
- Solver failures (>5%)
- Database connection failures
- Circuit breaker opens
- Resource exhaustion (CPU >80%, Memory >90%, Disk >90%)

## 🔍 Troubleshooting

### Common Issues

#### 1. Metrics Not Appearing
- Check `ENABLE_METRICS=true` in environment
- Verify metrics port is accessible
- Check Prometheus scrape configuration

#### 2. Logs Not Structured
- Ensure `LOG_FORMAT=json` in environment
- Check log level configuration
- Verify structured logging initialization

#### 3. Health Checks Failing
- Check database connectivity
- Verify OR-Tools installation
- Review system resource usage

#### 4. High Memory Usage
- Monitor active jobs and tasks
- Check for memory leaks in solver operations
- Review database connection pooling

### Performance Optimization

#### Solver Performance
- Monitor solver execution time metrics
- Adjust solver parameters based on problem size
- Use hierarchical optimization for large problems

#### Database Performance
- Monitor slow query metrics
- Review connection pooling configuration
- Optimize frequently used queries

#### System Resources
- Monitor CPU and memory usage trends
- Scale resources based on workload patterns
- Use circuit breakers to prevent resource exhaustion

## 📚 API Reference

### Correlation ID Header

Include in requests for tracing:
```
X-Correlation-ID: your-correlation-id
```

### User Context Header

For user-specific logging:
```
X-User-ID: user-identifier
```

### Response Headers

All responses include:
```
X-Correlation-ID: correlation-id-value
```

## 🚀 Production Deployment

### Environment Configuration

Production settings:
```env
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json
ENABLE_METRICS=true
ENABLE_TRACING=true
ENABLE_PERFORMANCE_MONITORING=true
```

### Security Considerations

- Disable debug endpoints in production (`ENVIRONMENT != "local"`)
- Configure appropriate log retention policies
- Secure metrics endpoints with authentication
- Use encrypted connections for external monitoring

### Scaling

- Metrics collection scales automatically with application instances
- Use load balancers with health check endpoints
- Configure appropriate circuit breaker thresholds for your environment
- Monitor resource usage and scale accordingly

## 📞 Support

For issues related to observability:

1. Check application logs for errors
2. Verify configuration settings
3. Review health check endpoints
4. Monitor system resources
5. Check circuit breaker states

The observability system is designed to be self-diagnosing - use the debug dashboard and health checks to identify issues quickly.
