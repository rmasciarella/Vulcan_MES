# Performance Optimization Guide

## Overview

This document outlines the comprehensive performance optimization strategies implemented in the Vulcan Engine production scheduling system. The optimizations ensure the system can handle enterprise workloads efficiently with sub-second response times and horizontal scalability.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Caching Strategy](#caching-strategy)
3. [Database Optimization](#database-optimization)
4. [Background Processing](#background-processing)
5. [Performance Monitoring](#performance-monitoring)
6. [Load Testing](#load-testing)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Performance Stack

```
┌─────────────────────────────────────────────┐
│            Load Balancer (Traefik)          │
└─────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌───────▼────────┐
│   FastAPI      │         │   FastAPI      │
│   Instance 1   │         │   Instance 2   │
└───────┬────────┘         └───────┬────────┘
        │                           │
        ├───────────┬───────────────┤
        │           │               │
┌───────▼──┐  ┌────▼────┐  ┌──────▼──────┐
│  Redis   │  │   DB    │  │  DB Replica │
│  Cache   │  │ Primary │  │  (Read)     │
└──────────┘  └─────────┘  └─────────────┘
        │
┌───────▼────────────────────────────────────┐
│           Celery Workers                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Worker 1 │ │ Worker 2 │ │ Worker N │  │
│  └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────┘
```

### Key Components

- **Redis Cache**: In-memory data store for fast access to frequently used data
- **Celery Workers**: Asynchronous task processing for long-running operations
- **Database Read Replicas**: Separate read and write operations for scalability
- **Connection Pooling**: Efficient database connection management
- **Performance Monitoring**: Real-time metrics and bottleneck detection

## Caching Strategy

### Cache Layers

1. **Application-Level Cache** (`app/core/cache.py`)
   - Redis-based caching with configurable TTLs
   - Decorator-based caching for functions
   - Entity-specific caching with invalidation

2. **Repository-Level Cache** (`app/infrastructure/cache/cached_repositories.py`)
   - Transparent caching for domain entities
   - Automatic cache invalidation on updates
   - Query result caching

### Cache Configuration

```python
# Cache TTL Configuration (seconds)
CACHE_ENTITY_TTL = {
    "job": 3600,        # 1 hour
    "task": 3600,       # 1 hour
    "operator": 7200,   # 2 hours
    "machine": 7200,    # 2 hours
    "schedule": 1800,   # 30 minutes
    "production_zone": 7200,  # 2 hours
}
```

### Cache Usage Examples

#### Function Caching

```python
from app.core.cache import cache

@cache(ttl=3600, key_prefix="expensive_operation")
def expensive_calculation(param1: int, param2: str) -> dict:
    # Expensive operation
    return result
```

#### Entity Caching

```python
from app.infrastructure.cache import CachedJobRepository

# Wrap repository with caching
cached_repo = CachedJobRepository(original_repo)

# Transparent caching
job = await cached_repo.get_by_id(job_id)  # Checks cache first
```

#### Cache Invalidation

```python
from app.core.cache import cache_invalidate

@cache_invalidate(patterns=["job:*", "schedule:*"])
def update_job(job_id: str, updates: dict) -> Job:
    # Update operation that invalidates related caches
    return updated_job
```

### Cache Warming

The system supports cache warming on startup for frequently accessed data:

```python
from app.core.cache import warm_cache_on_startup

# In app startup
await warm_cache_on_startup()
```

## Database Optimization

### Connection Pooling

```python
# Connection pool configuration
POOL_CONFIG = {
    "pool_size": 20,
    "max_overflow": 40,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}
```

### Read Replica Configuration

```python
# Use read replica for read-only operations
from app.core.database import get_read_db

def get_jobs_read_only():
    with get_read_db() as db:
        return db.query(Job).all()
```

### Query Optimization

1. **Indexing Strategy**
   - Index foreign keys
   - Index frequently queried columns
   - Composite indexes for common query patterns

2. **Query Monitoring**
   - Automatic slow query logging
   - Query execution plan analysis
   - Performance metrics collection

```python
# Slow query detection
if total_time > PERFORMANCE_SLOW_QUERY_THRESHOLD:
    logger.warning(f"Slow query detected ({total_time:.2f}s)")
```

### Database Maintenance

```python
from app.core.database import QueryOptimizer

# Analyze table statistics
QueryOptimizer.analyze_table("jobs", session)

# Vacuum table
QueryOptimizer.vacuum_table("schedules", session, full=False)

# Get table statistics
stats = QueryOptimizer.get_table_stats("tasks", session)
```

## Background Processing

### Celery Configuration

```python
# Celery task queues
TASK_ROUTES = {
    "scheduling.*": {"queue": "scheduling"},
    "optimization.*": {"queue": "optimization"},
    "maintenance.*": {"queue": "maintenance"},
    "reporting.*": {"queue": "reporting"},
}
```

### Task Examples

#### Scheduling Task

```python
from app.core.tasks.scheduling import schedule_job

# Async job scheduling
result = schedule_job.delay(
    job_id="job_123",
    priority=5,
    constraints={"max_makespan": 7200}
)
```

#### Optimization Task

```python
from app.core.tasks.optimization import optimize_schedule

# Background optimization
result = optimize_schedule.delay(
    schedule_id="schedule_456",
    optimization_params={"focus": "cost"}
)
```

### Periodic Tasks

```python
# Configured in celery_app.py
BEAT_SCHEDULE = {
    "cache-cleanup": {
        "task": "maintenance.cleanup_expired_cache",
        "schedule": 3600.0,  # Every hour
    },
    "optimize-schedules": {
        "task": "optimization.optimize_pending_schedules",
        "schedule": 300.0,  # Every 5 minutes
    },
}
```

## Performance Monitoring

### Metrics Collection

```python
from app.core.monitoring import performance_monitor

# Measure operation time
with performance_monitor.measure_time("critical_operation"):
    perform_critical_operation()

# Decorator for functions
@performance_monitor.measure_function(name="api.endpoint")
def api_endpoint():
    return response
```

### System Monitoring

```python
from app.core.monitoring import system_monitor

# Collect system metrics
metrics = system_monitor.collect_system_metrics()
# Returns: CPU, memory, disk, network metrics
```

### Performance Analysis

```python
from app.core.monitoring import performance_analyzer

# Identify bottlenecks
bottlenecks = performance_analyzer.identify_bottlenecks()

# Analyze response times
analysis = performance_analyzer.analyze_response_times()

# Generate performance report
report = performance_analyzer.generate_performance_report()
```

### API Endpoints

- `GET /api/v1/monitoring/performance` - Performance metrics
- `GET /api/v1/monitoring/system` - System resource metrics
- `GET /api/v1/monitoring/database` - Database metrics
- `GET /api/v1/monitoring/cache` - Cache metrics
- `GET /api/v1/monitoring/bottlenecks` - Identified bottlenecks
- `GET /api/v1/monitoring/dashboard/kpi` - KPI dashboard

## Load Testing

### Locust Testing

```bash
# Run Locust web UI
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Run headless with specific parameters
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless
```

### k6 Testing

```bash
# Run k6 test
k6 run tests/load/k6_test.js

# Run with specific VUs and duration
k6 run --vus=100 --duration=30s tests/load/k6_test.js

# Run with HTML report
k6 run --out html=report.html tests/load/k6_test.js
```

### Test Scenarios

1. **Normal Load**: 100 users, steady traffic
2. **Stress Test**: 500 users, increasing load
3. **Spike Test**: Sudden traffic increase to 1000 users
4. **Endurance Test**: 50 users for 1 hour
5. **Mixed Load**: Combination of different user patterns

## Best Practices

### 1. Caching Best Practices

- **Cache Frequently Accessed Data**: Focus on read-heavy operations
- **Set Appropriate TTLs**: Balance freshness vs performance
- **Implement Cache Warming**: Pre-load critical data
- **Monitor Hit Rates**: Aim for >80% cache hit rate
- **Use Cache Invalidation Wisely**: Invalidate only affected keys

### 2. Database Best Practices

- **Use Read Replicas**: Separate read and write operations
- **Optimize Queries**: Use EXPLAIN ANALYZE regularly
- **Batch Operations**: Reduce round trips
- **Connection Pooling**: Reuse connections efficiently
- **Regular Maintenance**: VACUUM and ANALYZE tables

### 3. Background Processing Best Practices

- **Queue Priority**: Use different queues for different priorities
- **Retry Logic**: Implement exponential backoff
- **Task Monitoring**: Track task completion and failures
- **Resource Limits**: Set appropriate timeouts and concurrency
- **Idempotent Tasks**: Ensure tasks can be safely retried

### 4. Monitoring Best Practices

- **Set Alerts**: Configure alerts for critical metrics
- **Regular Reviews**: Weekly performance reviews
- **Baseline Metrics**: Establish normal performance baselines
- **Capacity Planning**: Monitor trends for scaling decisions
- **Documentation**: Document performance issues and solutions

## Troubleshooting

### Common Performance Issues

#### High Response Times

1. **Check Cache Hit Rate**
   ```python
   cache_stats = cache_manager.get_stats()
   print(f"Hit rate: {cache_stats['hit_rate']}%")
   ```

2. **Identify Slow Queries**
   - Check logs for slow query warnings
   - Use database query analyzer

3. **Monitor Resource Usage**
   ```python
   system_metrics = system_monitor.collect_system_metrics()
   ```

#### Memory Issues

1. **Profile Memory Usage**
   ```python
   from app.core.monitoring import memory_profiler
   memory_profiler.start_profiling()
   snapshot = memory_profiler.take_snapshot("checkpoint")
   ```

2. **Check for Memory Leaks**
   - Compare memory snapshots
   - Monitor process memory growth

#### Database Connection Issues

1. **Check Pool Status**
   ```python
   pool_status = get_pool_status()
   print(f"Active connections: {pool_status['primary']['checked_out']}")
   ```

2. **Verify Connection Health**
   ```python
   health = check_database_health()
   ```

### Performance Debugging Commands

```bash
# Monitor Redis
redis-cli monitor

# Check Celery workers
celery -A app.core.celery_app inspect active

# Database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# System resources
htop
iostat -x 1
netstat -an | grep ESTABLISHED | wc -l
```

## Deployment Considerations

### Docker Compose

```bash
# Start performance stack
docker-compose -f docker-compose.yml -f docker-compose.performance.yml up -d

# Scale workers
docker-compose scale celery_worker=4

# Monitor logs
docker-compose logs -f celery_worker
```

### Environment Variables

```env
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secure_password
REDIS_CACHE_TTL=3600

# Database Read Replica
DATABASE_READ_REPLICA_URL=postgresql://user:pass@replica:5432/db

# Performance Settings
ENABLE_PERFORMANCE_MONITORING=true
PERFORMANCE_SLOW_QUERY_THRESHOLD=1.0
ENABLE_REQUEST_PROFILING=false

# Celery Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=1800
```

### Production Checklist

- [ ] Redis configured with persistence
- [ ] Database read replicas configured
- [ ] Connection pooling optimized
- [ ] Monitoring dashboards set up
- [ ] Alerts configured
- [ ] Load testing completed
- [ ] Cache warming enabled
- [ ] Background workers scaled appropriately
- [ ] Slow query logging enabled
- [ ] Performance baselines established

## Metrics and KPIs

### Target Performance Metrics

| Metric | Target | Critical |
|--------|--------|----------|
| API Response Time (p95) | < 500ms | > 1000ms |
| Cache Hit Rate | > 80% | < 60% |
| Database Query Time (p95) | < 100ms | > 500ms |
| Background Task Success Rate | > 99% | < 95% |
| System CPU Usage | < 70% | > 90% |
| Memory Usage | < 80% | > 95% |
| Error Rate | < 1% | > 5% |

### Monitoring Dashboard

Access monitoring dashboards:

- **Grafana**: http://localhost:3000 (admin/admin)
- **Flower (Celery)**: http://localhost:5555
- **Redis Commander**: http://localhost:8081
- **pgAdmin**: http://localhost:5050

## Conclusion

This performance optimization implementation provides:

1. **Scalability**: Horizontal scaling support with load balancing
2. **Efficiency**: Sub-second response times with caching
3. **Reliability**: Background processing for long operations
4. **Observability**: Comprehensive monitoring and alerting
5. **Maintainability**: Clear separation of concerns and documentation

The system is designed to handle thousands of concurrent jobs and tasks while maintaining optimal performance and resource utilization.
