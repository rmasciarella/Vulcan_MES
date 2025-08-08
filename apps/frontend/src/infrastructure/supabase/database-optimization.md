# Database Optimization Strategy for Manufacturing Data Pipeline

## Index Strategy for Production Database

### Critical Indexes for Manufacturing Workload (1000+ concurrent jobs)

#### Job Instances Table Optimization

```sql
-- Primary query patterns optimized for manufacturing scheduling
CREATE INDEX CONCURRENTLY idx_job_instances_status_due_date
ON job_instances(status, due_date ASC)
WHERE status IN ('SCHEDULED', 'IN_PROGRESS', 'ON_HOLD');

CREATE INDEX CONCURRENTLY idx_job_instances_template_due_date
ON job_instances(template_id, due_date ASC)
WHERE template_id IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_job_instances_release_date_status
ON job_instances(earliest_start_date, status)
WHERE status != 'COMPLETED' AND status != 'CANCELLED';

-- Manufacturing-specific composite index for batch scheduling
CREATE INDEX CONCURRENTLY idx_job_instances_manufacturing_batch
ON job_instances(due_date ASC, status, template_id)
INCLUDE (instance_id, name);

-- Version-aware updates for concurrent manufacturing operations
CREATE INDEX CONCURRENTLY idx_job_instances_version_updates
ON job_instances(instance_id, version DESC);
```

#### Task Table Optimization

```sql
-- Critical for task sequencing and job relationship queries
CREATE INDEX CONCURRENTLY idx_tasks_job_sequence
ON tasks(job_id, sequence_number ASC);

CREATE INDEX CONCURRENTLY idx_tasks_status_scheduling
ON tasks(status, sequence_number ASC)
WHERE status IN ('ready', 'in_progress');

-- Manufacturing skill-based task assignment
CREATE INDEX CONCURRENTLY idx_tasks_attendance_setup
ON tasks(is_unattended, is_setup_task, status);

-- Task precedence optimization
CREATE INDEX CONCURRENTLY idx_tasks_precedence_ready
ON tasks(job_id, status)
WHERE status = 'ready';
```

#### TaskMode Relationship Optimization

```sql
-- Resource requirement lookups for manufacturing scheduling
CREATE INDEX CONCURRENTLY idx_task_modes_resource_lookup
ON task_modes(task_id, is_primary_mode DESC, duration_minutes ASC);

-- Skill requirement joins
CREATE INDEX CONCURRENTLY idx_task_mode_skill_reqs_level
ON task_mode_skill_requirements(skill_level, quantity DESC);

-- WorkCell requirement joins
CREATE INDEX CONCURRENTLY idx_task_mode_workcell_reqs
ON task_mode_workcell_requirements(workcell_id, task_mode_id);

-- Manufacturing optimization queries
CREATE INDEX CONCURRENTLY idx_task_modes_duration_type
ON task_modes(duration_minutes ASC, type, is_primary_mode DESC);
```

#### Cross-Domain Join Optimization

```sql
-- Efficient jobs-to-tasks data loading (prevents N+1)
CREATE INDEX CONCURRENTLY idx_tasks_job_id_coverage
ON tasks(job_id)
INCLUDE (id, name, sequence_number, status, is_setup_task, is_unattended);

-- Task-to-TaskMode efficient loading
CREATE INDEX CONCURRENTLY idx_task_modes_task_id_coverage
ON task_modes(task_id)
INCLUDE (id, name, type, duration_minutes, is_primary_mode);
```

## Connection Pooling Strategy

### Supabase Connection Pool Configuration

```typescript
// Recommended pooling for manufacturing workload
const supabaseConfig = {
  poolSize: 20, // Handle 1000+ concurrent jobs efficiently
  maxConnections: 25, // Reserve connections for critical operations
  idleTimeoutMillis: 30000, // 30s - manufacturing data changes frequently
  connectionTimeoutMillis: 10000, // 10s max connection wait
  statement_timeout: '30s', // Prevent long-running queries in production
  idle_in_transaction_session_timeout: '10s', // Quick transaction cleanup
}
```

### Connection Pool Best Practices

```typescript
// Repository-level connection management
export class OptimizedSupabaseClient {
  private static instance: SupabaseClient

  static getInstance(): SupabaseClient {
    if (!this.instance) {
      this.instance = createClient(url, key, {
        db: {
          // Manufacturing-optimized pool settings
          pool: {
            max: 20,
            min: 5,
            acquireTimeoutMillis: 10000,
            createTimeoutMillis: 10000,
            destroyTimeoutMillis: 5000,
            idleTimeoutMillis: 30000,
            reapIntervalMillis: 1000,
            createRetryIntervalMillis: 200,
          },
        },
        realtime: {
          // Disable for batch operations to preserve connections
          disabled: true,
        },
      })
    }
    return this.instance
  }
}
```

## Query Optimization Patterns

### Manufacturing-Specific Patterns

1. **Batch Size Optimization**: Limit queries to 500 records per batch for optimal performance
2. **Status-Based Partitioning**: Query active jobs separately from completed/cancelled
3. **Date Range Constraints**: Always include date boundaries for scheduling queries
4. **Composite Filtering**: Combine status + date + template filters for efficiency

### Performance Monitoring Queries

```sql
-- Monitor index usage for manufacturing workload
SELECT
  indexrelname,
  idx_tup_read,
  idx_tup_fetch,
  idx_scan,
  pg_size_pretty(pg_relation_size(indexrelname::regclass)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND indexrelname LIKE 'idx_%manufacturing%'
ORDER BY idx_scan DESC;

-- Query performance monitoring
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%job_instances%'
  OR query LIKE '%tasks%'
ORDER BY mean_exec_time DESC;
```

## Memory Management for Large Datasets

### Batch Processing Guidelines

- **Job Loading**: Process in batches of 500 jobs maximum
- **Task Association**: Load tasks separately when needed (lazy loading)
- **Value Object Caching**: Cache frequently used status/type objects
- **Connection Reuse**: Minimize connection churn for batch operations

### Manufacturing Data Pipeline Recommendations

1. **ETL Batch Size**: 200-500 jobs per batch for optimal throughput
2. **Incremental Processing**: Use version-based updates for changed jobs only
3. **Cache Strategy**: 5-minute cache for job status lookups, 30-minute cache for templates
4. **Connection Pooling**: Reserve 25% of pool for critical real-time operations
