# Vulcan Engine Operations Guide

## Table of Contents

1. [Deployment](#deployment)
2. [Configuration Management](#configuration-management)
3. [Database Operations](#database-operations)
4. [Monitoring & Alerting](#monitoring--alerting)
5. [Performance Tuning](#performance-tuning)
6. [Security Configuration](#security-configuration)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

## Deployment

### Docker Deployment

#### Production Stack

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  backend:
    image: vulcan-engine:latest
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - SENTRY_DSN=${SENTRY_DSN}
      - ENABLE_METRICS=true
      - ENABLE_TRACING=true
    ports:
      - "8000:8000"
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=vulcan
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3000:3000"

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

#### Deployment Commands

```bash
# Build and push image
docker build -t vulcan-engine:latest .
docker tag vulcan-engine:latest registry.example.com/vulcan-engine:latest
docker push registry.example.com/vulcan-engine:latest

# Deploy stack
docker stack deploy -c docker-compose.production.yml vulcan

# Scale services
docker service scale vulcan_backend=5

# Rolling update
docker service update --image vulcan-engine:v2.0.0 vulcan_backend

# Check deployment status
docker service ls
docker service ps vulcan_backend
```

### Kubernetes Deployment

#### Deployment Manifest

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vulcan-engine
  labels:
    app: vulcan-engine
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vulcan-engine
  template:
    metadata:
      labels:
        app: vulcan-engine
    spec:
      containers:
      - name: backend
        image: vulcan-engine:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: vulcan-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: vulcan-secrets
              key: secret-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: vulcan-engine-service
spec:
  selector:
    app: vulcan-engine
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vulcan-engine-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vulcan-engine
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Helm Chart

```yaml
# helm/values.yaml
replicaCount: 3

image:
  repository: vulcan-engine
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: api.vulcan-engine.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: vulcan-engine-tls
      hosts:
        - api.vulcan-engine.com

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

postgresql:
  enabled: true
  auth:
    postgresPassword: "changeme"
    database: "vulcan"
  persistence:
    size: 20Gi

redis:
  enabled: true
  auth:
    enabled: true
    password: "changeme"
```

```bash
# Deploy with Helm
helm install vulcan-engine ./helm -f values.production.yaml

# Upgrade deployment
helm upgrade vulcan-engine ./helm -f values.production.yaml

# Rollback
helm rollback vulcan-engine 1
```

## Configuration Management

### Environment Variables

```bash
# .env.production
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/vulcan
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME="Vulcan Engine"
ENVIRONMENT=production
DEBUG=false

# CORS
BACKEND_CORS_ORIGINS=["https://app.vulcan-engine.com"]

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
ENABLE_METRICS=true
ENABLE_TRACING=true
METRICS_PORT=9090
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831

# Solver Configuration
SOLVER_MAX_TIME_SECONDS=300
SOLVER_NUM_WORKERS=4
SOLVER_MEMORY_LIMIT_MB=8192

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@vulcan-engine.com
SMTP_PASSWORD=your-password
EMAILS_FROM_EMAIL=notifications@vulcan-engine.com
EMAILS_FROM_NAME="Vulcan Engine"
```

### Configuration Validation

```python
# scripts/validate_config.py
import os
import sys
from typing import Dict, Any

def validate_config() -> bool:
    """Validate production configuration."""
    errors = []

    # Required environment variables
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "ENVIRONMENT"
    ]

    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")

    # Validate database URL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url and not db_url.startswith("postgresql://"):
        errors.append("DATABASE_URL must be a PostgreSQL connection string")

    # Validate environment
    env = os.getenv("ENVIRONMENT", "")
    if env not in ["production", "staging", "development"]:
        errors.append(f"Invalid ENVIRONMENT: {env}")

    # Validate numeric configurations
    try:
        pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        if pool_size < 5 or pool_size > 100:
            errors.append(f"DATABASE_POOL_SIZE should be between 5 and 100")
    except ValueError:
        errors.append("DATABASE_POOL_SIZE must be a number")

    if errors:
        print("Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("Configuration validation passed ✓")
    return True

if __name__ == "__main__":
    sys.exit(0 if validate_config() else 1)
```

## Database Operations

### Migration Management

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new feature tables"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current

# Generate SQL for migration (dry run)
alembic upgrade head --sql
```

### Database Backup

```bash
#!/bin/bash
# scripts/backup_database.sh

# Configuration
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="vulcan"
DB_USER="vulcan_user"
BACKUP_DIR="/var/backups/vulcan"
RETENTION_DAYS=30

# Create backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/vulcan_${TIMESTAMP}.sql.gz"

echo "Starting database backup..."
pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} | gzip > ${BACKUP_FILE}

if [ $? -eq 0 ]; then
    echo "Backup completed: ${BACKUP_FILE}"

    # Upload to S3 (optional)
    aws s3 cp ${BACKUP_FILE} s3://vulcan-backups/database/

    # Clean old backups
    find ${BACKUP_DIR} -name "vulcan_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    echo "Old backups cleaned"
else
    echo "Backup failed!"
    exit 1
fi
```

### Database Restore

```bash
#!/bin/bash
# scripts/restore_database.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore_database.sh <backup_file>"
    exit 1
fi

echo "Restoring database from ${BACKUP_FILE}..."

# Stop application
docker-compose stop backend

# Restore database
gunzip < ${BACKUP_FILE} | psql -h localhost -U vulcan_user -d vulcan

# Run migrations
alembic upgrade head

# Start application
docker-compose start backend

echo "Restore completed"
```

### Database Maintenance

```sql
-- Analyze tables for query optimization
ANALYZE;

-- Vacuum to reclaim space
VACUUM ANALYZE;

-- Reindex for performance
REINDEX DATABASE vulcan;

-- Check table sizes
SELECT
    schemaname AS schema,
    tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan;
```

## Monitoring & Alerting

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'vulcan-engine'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/v1/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Alert Rules

```yaml
# alerts.yml
groups:
  - name: vulcan_engine
    interval: 30s
    rules:
      - alert: HighRequestLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High request latency detected"
          description: "95th percentile latency is {{ $value }}s"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: SolverTimeout
        expr: rate(solver_timeout_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Solver timeouts increasing"
          description: "Solver timeout rate is {{ $value | humanizePercentage }}"

      - alert: DatabaseConnectionPool
        expr: database_connection_pool_usage > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool almost full"
          description: "Connection pool usage is {{ $value | humanizePercentage }}"

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / node_memory_MemTotal_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Vulcan Engine Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Solver Performance",
        "targets": [
          {
            "expr": "rate(solver_problems_solved_total[5m])"
          },
          {
            "expr": "histogram_quantile(0.95, rate(solver_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Database Connections",
        "targets": [
          {
            "expr": "database_connection_pool_size"
          },
          {
            "expr": "database_connection_pool_usage"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

### Custom Metrics

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# Create registry
registry = CollectorRegistry()

# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    registry=registry
)

# Solver metrics
solver_problems = Counter(
    'solver_problems_total',
    'Total scheduling problems submitted',
    ['status'],
    registry=registry
)

solver_duration = Histogram(
    'solver_duration_seconds',
    'Solver execution time',
    registry=registry
)

solver_memory = Gauge(
    'solver_memory_bytes',
    'Solver memory usage',
    registry=registry
)

# Database metrics
db_pool_size = Gauge(
    'database_connection_pool_size',
    'Database connection pool size',
    registry=registry
)

db_pool_usage = Gauge(
    'database_connection_pool_usage',
    'Database connection pool usage ratio',
    registry=registry
)

# Business metrics
active_schedules = Gauge(
    'active_schedules_total',
    'Number of active schedules',
    registry=registry
)

jobs_scheduled = Counter(
    'jobs_scheduled_total',
    'Total jobs scheduled',
    ['priority'],
    registry=registry
)
```

## Performance Tuning

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_tasks_job_id ON tasks(job_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_assignments_schedule_id ON assignments(schedule_id);
CREATE INDEX idx_assignments_task_id ON assignments(task_id);
CREATE INDEX idx_machines_zone ON machines(zone);
CREATE INDEX idx_operators_skills ON operators USING GIN(skills);

-- Partial indexes for active records
CREATE INDEX idx_active_schedules ON schedules(id) WHERE status = 'active';
CREATE INDEX idx_pending_tasks ON tasks(id) WHERE status IN ('pending', 'ready');

-- Composite indexes for complex queries
CREATE INDEX idx_task_schedule ON assignments(schedule_id, task_id, planned_start);
```

### Application Optimization

```python
# config.py
class Settings:
    # Connection pooling
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # Redis caching
    REDIS_CACHE_TTL: int = 300
    REDIS_MAX_CONNECTIONS: int = 50

    # Solver optimization
    SOLVER_NUM_WORKERS: int = 4
    SOLVER_PARALLEL_SEARCH: bool = True
    SOLVER_USE_LNS: bool = True  # Large Neighborhood Search

    # API optimization
    API_PAGE_SIZE: int = 20
    API_MAX_PAGE_SIZE: int = 100
    API_RESPONSE_CACHE_TTL: int = 60
```

### Caching Strategy

```python
# app/core/cache.py
import json
import hashlib
from typing import Optional, Any
from redis import Redis
from functools import wraps

redis_client = Redis.from_url(settings.REDIS_URL)

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(ttl: int = 300):
    """Cache decorator for expensive operations."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = redis_client.get(key)
            if cached_value:
                return json.loads(cached_value)

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            redis_client.setex(key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator

# Usage
@cached(ttl=600)
async def get_machine_availability(machine_id: str, date_range: tuple):
    """Get machine availability (cached for 10 minutes)."""
    # Expensive database query
    pass
```

## Security Configuration

### SSL/TLS Setup

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.vulcan-engine.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### API Security

```python
# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(
                    status_code=403,
                    detail="Invalid authentication scheme."
                )
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(
                    status_code=403,
                    detail="Invalid token or expired token."
                )
            return credentials.credentials
        else:
            raise HTTPException(
                status_code=403,
                detail="Invalid authorization code."
            )

    def verify_jwt(self, jwtoken: str) -> bool:
        isTokenValid: bool = False
        try:
            payload = decode_jwt(jwtoken)
        except:
            payload = None
        if payload:
            isTokenValid = True
        return isTokenValid
```

### Rate Limiting

```python
# app/core/rate_limit.py
from fastapi import HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Usage in routes
@router.post("/solve")
@limiter.limit("10 per minute")
async def solve_scheduling_problem(request: Request, problem: SchedulingProblem):
    pass
```

## Backup & Recovery

### Automated Backup Script

```bash
#!/bin/bash
# scripts/automated_backup.sh

set -e

# Configuration
BACKUP_DIR="/var/backups/vulcan"
S3_BUCKET="vulcan-backups"
RETENTION_DAYS=30
SLACK_WEBHOOK="https://hooks.slack.com/services/XXX"

# Function to send Slack notification
notify_slack() {
    local message=$1
    local status=$2

    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"${status}: ${message}\"}" \
        ${SLACK_WEBHOOK}
}

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Backup timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Database backup
echo "Starting database backup..."
DB_BACKUP="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
pg_dump -h localhost -U vulcan_user -d vulcan | gzip > ${DB_BACKUP}

# Application data backup
echo "Backing up application data..."
APP_BACKUP="${BACKUP_DIR}/app_${TIMESTAMP}.tar.gz"
tar -czf ${APP_BACKUP} /app/data /app/uploads

# Redis backup
echo "Backing up Redis..."
REDIS_BACKUP="${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"
redis-cli BGSAVE
sleep 5
cp /var/lib/redis/dump.rdb ${REDIS_BACKUP}

# Upload to S3
echo "Uploading to S3..."
aws s3 cp ${DB_BACKUP} s3://${S3_BUCKET}/database/
aws s3 cp ${APP_BACKUP} s3://${S3_BUCKET}/application/
aws s3 cp ${REDIS_BACKUP} s3://${S3_BUCKET}/redis/

# Clean old local backups
find ${BACKUP_DIR} -type f -mtime +${RETENTION_DAYS} -delete

# Verify backup integrity
echo "Verifying backup..."
gunzip -t ${DB_BACKUP}
tar -tzf ${APP_BACKUP} > /dev/null

# Send notification
notify_slack "Backup completed successfully at ${TIMESTAMP}" "✅ SUCCESS"

echo "Backup completed successfully"
```

### Disaster Recovery Plan

```markdown
# Disaster Recovery Procedure

## 1. Assessment Phase (15 minutes)
- [ ] Identify the issue (data loss, corruption, system failure)
- [ ] Determine the last known good state
- [ ] Notify stakeholders
- [ ] Activate incident response team

## 2. Recovery Decision (10 minutes)
- [ ] Choose recovery strategy:
  - Point-in-time recovery
  - Full restoration from backup
  - Failover to standby system
- [ ] Estimate recovery time
- [ ] Get approval from management

## 3. Recovery Execution (Variable)

### Database Recovery
```bash
# Stop application
docker-compose stop backend

# Restore database from backup
gunzip < /backups/db_20250807_120000.sql.gz | psql -h localhost -U vulcan_user -d vulcan_restore

# Verify data integrity
psql -h localhost -U vulcan_user -d vulcan_restore -c "SELECT COUNT(*) FROM jobs;"

# Switch to restored database
export DATABASE_URL="postgresql://user:pass@localhost/vulcan_restore"

# Run migrations
alembic upgrade head
```

### Application Recovery
```bash
# Restore application data
tar -xzf /backups/app_20250807_120000.tar.gz -C /

# Restore Redis data
service redis-server stop
cp /backups/redis_20250807_120000.rdb /var/lib/redis/dump.rdb
service redis-server start

# Start application
docker-compose up -d backend
```

## 4. Validation Phase (30 minutes)
- [ ] Verify system accessibility
- [ ] Run health checks
- [ ] Test critical functionality
- [ ] Verify data consistency
- [ ] Check integration points

## 5. Post-Recovery (1 hour)
- [ ] Monitor system stability
- [ ] Document incident timeline
- [ ] Conduct root cause analysis
- [ ] Update recovery procedures
- [ ] Schedule post-mortem meeting
```

## Troubleshooting

### Common Issues

#### High Memory Usage

```bash
# Check memory usage
docker stats

# Analyze Python memory
pip install memory_profiler
python -m memory_profiler app/main.py

# Profile specific endpoints
from memory_profiler import profile

@profile
def solve_scheduling_problem():
    pass

# Check for memory leaks
import tracemalloc
tracemalloc.start()
# ... application code ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 10**6}MB")
tracemalloc.stop()
```

#### Slow Query Performance

```sql
-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;
ALTER SYSTEM SET log_min_duration_statement = 100; -- Log queries > 100ms
SELECT pg_reload_conf();

-- Analyze slow query
EXPLAIN ANALYZE SELECT * FROM tasks WHERE status = 'pending';

-- Check missing indexes
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE tablename = 'tasks'
ORDER BY n_distinct DESC;
```

#### Solver Performance Issues

```python
# Enable solver debugging
from ortools.sat.python import cp_model

class SolverCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.solutions = []

    def on_solution_callback(self):
        print(f"Solution {len(self.solutions)}: "
              f"Objective = {self.ObjectiveValue()}, "
              f"Time = {self.WallTime()}s")
        self.solutions.append({
            'objective': self.ObjectiveValue(),
            'time': self.WallTime(),
            'branches': self.NumBranches(),
            'conflicts': self.NumConflicts()
        })

# Use callback
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 60
solver.parameters.log_search_progress = True
callback = SolverCallback()
status = solver.Solve(model, callback)

# Analyze performance
import pandas as pd
df = pd.DataFrame(callback.solutions)
print(df.describe())
```

### Debug Tools

```bash
# API debugging
curl -X POST http://localhost:8000/api/v1/debug/profile \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"duration": 30}'

# Database debugging
psql -h localhost -U vulcan_user -d vulcan \
  -c "SELECT * FROM pg_stat_activity WHERE state != 'idle';"

# Container debugging
docker exec -it vulcan_backend_1 bash
python -m pdb app/main.py

# Network debugging
docker run --rm -it --network vulcan_default nicolaka/netshoot
nslookup backend
curl -v http://backend:8000/api/v1/health

# Log analysis
docker logs vulcan_backend_1 --tail 100 --follow
grep ERROR /var/log/vulcan/app.log | tail -50
```

### Performance Profiling

```python
# scripts/profile.py
import cProfile
import pstats
from io import StringIO

def profile_endpoint(endpoint_func):
    """Profile an API endpoint."""
    profiler = cProfile.Profile()
    profiler.enable()

    # Run the endpoint
    result = endpoint_func()

    profiler.disable()

    # Generate report
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

    print(stream.getvalue())
    return result

# Usage
from app.api.routes.scheduling import solve_scheduling_problem
profile_endpoint(lambda: solve_scheduling_problem(test_problem))
```
