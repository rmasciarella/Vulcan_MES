-- Database schema optimizations for scheduling read models
-- Focus on query performance with appropriate indexes and materialized views

-- Create indexes for machine utilization queries
-- These indexes support time-bucketed aggregations and filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_machine_planned_time 
ON tasks (assigned_machine_id, planned_start_time, planned_end_time)
WHERE assigned_machine_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_machine_actual_time
ON tasks (assigned_machine_id, actual_start_time, actual_end_time) 
WHERE assigned_machine_id IS NOT NULL AND actual_start_time IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_status_time
ON tasks (status, planned_start_time, planned_end_time);

-- Composite index for machine utilization with status filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_machines_status_dept
ON machines (status, department, is_active)
WHERE is_active = true;

-- Create indexes for operator load queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_operator_assignments_time
ON operator_assignments (operator_id, planned_start_time, planned_end_time, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_operators_dept_status
ON operators (department, status, is_active)
WHERE is_active = true;

-- Index for skill-based queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_operator_skills_active
ON operator_skills (operator_id, skill_code, proficiency_level, is_active)
WHERE is_active = true AND (expiry_date IS NULL OR expiry_date > CURRENT_DATE);

-- Create indexes for job flow metrics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_status_times
ON jobs (status, created_at, started_at, completed_at, department);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_type_dept_created
ON jobs (job_type, department, created_at);

-- Index for schedule analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_schedule_critical
ON tasks (job_id, is_critical_path, planned_start_time, planned_end_time);

-- Create materialized view for daily machine utilization summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_machine_utilization AS
WITH daily_buckets AS (
    SELECT 
        t.assigned_machine_id as machine_id,
        m.name as machine_name,
        m.department,
        DATE_TRUNC('day', t.planned_start_time) as utilization_date,
        
        -- Scheduled metrics
        SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/60) as scheduled_minutes,
        SUM(EXTRACT(EPOCH FROM (COALESCE(t.actual_end_time, t.planned_end_time) - 
                                COALESCE(t.actual_start_time, t.planned_start_time)))/60) as actual_minutes,
        
        -- Task metrics
        COUNT(*) as tasks_scheduled,
        COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as tasks_completed,
        COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) as tasks_failed,
        SUM(t.rework_count) as total_rework,
        SUM(t.delay_minutes) as total_delay_minutes,
        
        -- Available time (8 hours = 480 minutes default)
        480 as available_minutes
    FROM tasks t
    JOIN machines m ON m.id = t.assigned_machine_id
    WHERE t.assigned_machine_id IS NOT NULL
        AND t.planned_start_time >= CURRENT_DATE - INTERVAL '90 days'
        AND t.planned_start_time IS NOT NULL
        AND t.planned_end_time IS NOT NULL
    GROUP BY t.assigned_machine_id, m.name, m.department, DATE_TRUNC('day', t.planned_start_time)
)
SELECT 
    machine_id,
    machine_name,
    department,
    utilization_date,
    scheduled_minutes,
    actual_minutes,
    available_minutes,
    CASE WHEN available_minutes > 0 
         THEN LEAST(1.0, scheduled_minutes::float / available_minutes)
         ELSE 0.0 END as scheduled_utilization_rate,
    CASE WHEN available_minutes > 0 
         THEN LEAST(1.0, actual_minutes::float / available_minutes)
         ELSE 0.0 END as actual_utilization_rate,
    tasks_scheduled,
    tasks_completed,
    tasks_failed,
    total_rework,
    total_delay_minutes,
    CASE WHEN tasks_scheduled > 0
         THEN tasks_completed::float / tasks_scheduled
         ELSE 0.0 END as completion_rate
FROM daily_buckets;

-- Index for the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_machine_util_unique
ON mv_daily_machine_utilization (machine_id, utilization_date);

CREATE INDEX IF NOT EXISTS idx_mv_daily_machine_util_date_dept
ON mv_daily_machine_utilization (utilization_date, department);

-- Create materialized view for operator workload summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_operator_workload AS  
WITH daily_workload AS (
    SELECT 
        o.id as operator_id,
        o.employee_id,
        o.first_name || ' ' || o.last_name as full_name,
        o.department,
        DATE_TRUNC('day', oa.planned_start_time) as workload_date,
        
        -- Assignment metrics
        COUNT(oa.id) as assignments_count,
        SUM(EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/60) as assigned_minutes,
        SUM(EXTRACT(EPOCH FROM (COALESCE(oa.actual_end_time, oa.planned_end_time) - 
                                COALESCE(oa.actual_start_time, oa.planned_start_time)))/60) as working_minutes,
        
        -- Status counts
        COUNT(CASE WHEN oa.status = 'COMPLETED' THEN 1 END) as completed_assignments,
        COUNT(CASE WHEN oa.status = 'IN_PROGRESS' THEN 1 END) as active_assignments,
        COUNT(CASE WHEN oa.status = 'FAILED' THEN 1 END) as failed_assignments,
        
        -- Available time based on working hours (8 hours = 480 minutes default)
        480 as available_minutes
    FROM operators o
    LEFT JOIN operator_assignments oa ON oa.operator_id = o.id
        AND oa.planned_start_time >= CURRENT_DATE - INTERVAL '90 days'
        AND oa.planned_start_time IS NOT NULL
    WHERE o.is_active = true
    GROUP BY o.id, o.employee_id, o.first_name, o.last_name, o.department,
             DATE_TRUNC('day', COALESCE(oa.planned_start_time, CURRENT_DATE))
)
SELECT 
    operator_id,
    employee_id,
    full_name,
    department,
    workload_date,
    assignments_count,
    assigned_minutes,
    working_minutes,
    available_minutes,
    CASE WHEN available_minutes > 0
         THEN LEAST(1.0, assigned_minutes::float / available_minutes)
         ELSE 0.0 END as load_percentage,
    CASE WHEN available_minutes > 0
         THEN LEAST(1.0, working_minutes::float / available_minutes)  
         ELSE 0.0 END as utilization_rate,
    completed_assignments,
    active_assignments,
    failed_assignments,
    CASE WHEN assignments_count > 0
         THEN completed_assignments::float / assignments_count
         ELSE 0.0 END as completion_rate
FROM daily_workload;

-- Index for operator workload view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_operator_workload_unique
ON mv_daily_operator_workload (operator_id, workload_date);

CREATE INDEX IF NOT EXISTS idx_mv_daily_operator_workload_date_dept
ON mv_daily_operator_workload (workload_date, department);

-- Create materialized view for job flow metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_job_flow_metrics AS
WITH daily_job_metrics AS (
    SELECT 
        j.department,
        j.job_type,
        DATE_TRUNC('day', j.created_at) as metrics_date,
        
        -- Job counts by status
        COUNT(*) as total_jobs,
        COUNT(CASE WHEN j.status = 'COMPLETED' THEN 1 END) as completed_jobs,
        COUNT(CASE WHEN j.status IN ('IN_PROGRESS', 'SCHEDULED') THEN 1 END) as active_jobs,
        COUNT(CASE WHEN j.status IN ('FAILED', 'CANCELLED') THEN 1 END) as failed_jobs,
        
        -- Timing metrics (in hours)
        AVG(CASE WHEN j.completed_at IS NOT NULL AND j.started_at IS NOT NULL
                 THEN EXTRACT(EPOCH FROM (j.completed_at - j.started_at))/3600
                 ELSE NULL END) as avg_completion_time_hours,
        AVG(CASE WHEN j.started_at IS NOT NULL
                 THEN EXTRACT(EPOCH FROM (j.started_at - j.created_at))/3600
                 ELSE NULL END) as avg_queue_time_hours,
        
        -- Quality metrics
        COUNT(CASE WHEN j.status = 'COMPLETED' 
                   AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.job_id = j.id AND t.rework_count > 0)
                   THEN 1 END) as first_pass_jobs
    FROM jobs j
    WHERE j.created_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY j.department, j.job_type, DATE_TRUNC('day', j.created_at)
),
daily_task_metrics AS (
    SELECT 
        j.department,
        j.job_type,
        DATE_TRUNC('day', j.created_at) as metrics_date,
        
        -- Task metrics
        COUNT(t.id) as total_tasks,
        COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks,
        COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) as failed_tasks,
        SUM(t.rework_count) as total_rework_count,
        SUM(COALESCE(t.actual_duration_minutes, t.planned_duration_minutes, 0))/60.0 as total_processing_hours
    FROM jobs j
    LEFT JOIN tasks t ON t.job_id = j.id
    WHERE j.created_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY j.department, j.job_type, DATE_TRUNC('day', j.created_at)
)
SELECT 
    COALESCE(jm.department, tm.department, 'unknown') as department,
    COALESCE(jm.job_type, tm.job_type, 'unknown') as job_type,
    COALESCE(jm.metrics_date, tm.metrics_date) as metrics_date,
    
    -- Job metrics
    COALESCE(jm.total_jobs, 0) as total_jobs,
    COALESCE(jm.completed_jobs, 0) as completed_jobs,  
    COALESCE(jm.active_jobs, 0) as active_jobs,
    COALESCE(jm.failed_jobs, 0) as failed_jobs,
    COALESCE(jm.first_pass_jobs, 0) as first_pass_jobs,
    
    -- Task metrics
    COALESCE(tm.total_tasks, 0) as total_tasks,
    COALESCE(tm.completed_tasks, 0) as completed_tasks,
    COALESCE(tm.failed_tasks, 0) as failed_tasks,
    COALESCE(tm.total_rework_count, 0) as total_rework_count,
    COALESCE(tm.total_processing_hours, 0) as total_processing_hours,
    
    -- Calculated metrics
    COALESCE(jm.avg_completion_time_hours, 0) as avg_completion_time_hours,
    COALESCE(jm.avg_queue_time_hours, 0) as avg_queue_time_hours,
    
    -- Rates
    CASE WHEN COALESCE(jm.total_jobs, 0) > 0
         THEN COALESCE(jm.completed_jobs, 0)::float / jm.total_jobs
         ELSE 0.0 END as completion_rate,
    CASE WHEN COALESCE(jm.completed_jobs, 0) > 0
         THEN COALESCE(jm.first_pass_jobs, 0)::float / jm.completed_jobs
         ELSE 0.0 END as first_pass_yield
FROM daily_job_metrics jm
FULL OUTER JOIN daily_task_metrics tm ON tm.department = jm.department 
    AND tm.job_type = jm.job_type 
    AND tm.metrics_date = jm.metrics_date;

-- Index for job flow metrics view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_job_flow_unique
ON mv_daily_job_flow_metrics (department, job_type, metrics_date);

CREATE INDEX IF NOT EXISTS idx_mv_daily_job_flow_date
ON mv_daily_job_flow_metrics (metrics_date);

-- Create function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_scheduling_read_models()
RETURNS void AS $$
BEGIN
    -- Refresh materialized views concurrently to minimize locking
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_machine_utilization;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_operator_workload;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_job_flow_metrics;
    
    -- Update statistics for better query planning
    ANALYZE mv_daily_machine_utilization;
    ANALYZE mv_daily_operator_workload;
    ANALYZE mv_daily_job_flow_metrics;
END;
$$ LANGUAGE plpgsql;

-- Schedule automatic refresh (would be set up via cron or job scheduler)
-- This is just documentation of the recommended refresh schedule
-- COMMENT: 'Run every hour: 0 * * * * psql -c "SELECT refresh_scheduling_read_models();"'

-- Create helper function for time bucket generation
CREATE OR REPLACE FUNCTION generate_time_buckets(
    start_time timestamptz,
    end_time timestamptz, 
    bucket_interval interval DEFAULT '1 hour'::interval
)
RETURNS TABLE(bucket_start timestamptz, bucket_end timestamptz) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        generate_series AS bucket_start,
        generate_series + bucket_interval AS bucket_end
    FROM generate_series(start_time, end_time - bucket_interval, bucket_interval);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create optimized function for machine utilization bucketing
CREATE OR REPLACE FUNCTION get_machine_utilization_buckets(
    p_machine_ids uuid[] DEFAULT NULL,
    p_start_time timestamptz DEFAULT NULL,
    p_end_time timestamptz DEFAULT NULL,
    p_bucket_hours integer DEFAULT 1
)
RETURNS TABLE(
    machine_id uuid,
    machine_name text,
    bucket_start timestamptz,
    bucket_end timestamptz,
    scheduled_minutes integer,
    actual_minutes integer,
    available_minutes integer,
    tasks_scheduled integer,
    tasks_completed integer,
    utilization_rate numeric
) AS $$
DECLARE
    v_start_time timestamptz := COALESCE(p_start_time, CURRENT_TIMESTAMP - INTERVAL '7 days');
    v_end_time timestamptz := COALESCE(p_end_time, CURRENT_TIMESTAMP);
    v_bucket_interval interval := (p_bucket_hours || ' hours')::interval;
BEGIN
    RETURN QUERY
    WITH time_buckets AS (
        SELECT * FROM generate_time_buckets(v_start_time, v_end_time, v_bucket_interval)
    ),
    machine_buckets AS (
        SELECT 
            m.id,
            m.name,
            tb.bucket_start,
            tb.bucket_end
        FROM machines m
        CROSS JOIN time_buckets tb
        WHERE m.is_active = true
            AND (p_machine_ids IS NULL OR m.id = ANY(p_machine_ids))
    )
    SELECT 
        mb.id,
        mb.name,
        mb.bucket_start,
        mb.bucket_end,
        COALESCE(SUM(
            CASE WHEN t.planned_start_time < mb.bucket_end 
                 AND t.planned_end_time > mb.bucket_start
            THEN LEAST(
                EXTRACT(EPOCH FROM mb.bucket_end)::integer,
                EXTRACT(EPOCH FROM t.planned_end_time)::integer
            ) - GREATEST(
                EXTRACT(EPOCH FROM mb.bucket_start)::integer,
                EXTRACT(EPOCH FROM t.planned_start_time)::integer
            )
            ELSE 0 END
        )/60, 0)::integer,
        COALESCE(SUM(
            CASE WHEN t.actual_start_time IS NOT NULL 
                 AND t.actual_end_time IS NOT NULL
                 AND t.actual_start_time < mb.bucket_end 
                 AND t.actual_end_time > mb.bucket_start
            THEN LEAST(
                EXTRACT(EPOCH FROM mb.bucket_end)::integer,
                EXTRACT(EPOCH FROM t.actual_end_time)::integer
            ) - GREATEST(
                EXTRACT(EPOCH FROM mb.bucket_start)::integer,
                EXTRACT(EPOCH FROM t.actual_start_time)::integer
            )
            ELSE 0 END
        )/60, 0)::integer,
        (p_bucket_hours * 60)::integer,
        COUNT(CASE WHEN t.planned_start_time < mb.bucket_end 
                   AND t.planned_end_time > mb.bucket_start THEN 1 END)::integer,
        COUNT(CASE WHEN t.status = 'COMPLETED' 
                   AND t.planned_start_time < mb.bucket_end 
                   AND t.planned_end_time > mb.bucket_start THEN 1 END)::integer,
        CASE WHEN p_bucket_hours * 60 > 0
             THEN ROUND(COALESCE(SUM(
                CASE WHEN t.planned_start_time < mb.bucket_end 
                     AND t.planned_end_time > mb.bucket_start
                THEN LEAST(
                    EXTRACT(EPOCH FROM mb.bucket_end)::integer,
                    EXTRACT(EPOCH FROM t.planned_end_time)::integer
                ) - GREATEST(
                    EXTRACT(EPOCH FROM mb.bucket_start)::integer,
                    EXTRACT(EPOCH FROM t.planned_start_time)::integer
                )
                ELSE 0 END
            ), 0)::numeric / (p_bucket_hours * 60 * 60), 4)
             ELSE 0 END
    FROM machine_buckets mb
    LEFT JOIN tasks t ON t.assigned_machine_id = mb.id
        AND t.planned_start_time < mb.bucket_end
        AND t.planned_end_time > mb.bucket_start
    GROUP BY mb.id, mb.name, mb.bucket_start, mb.bucket_end
    ORDER BY mb.id, mb.bucket_start;
END;
$$ LANGUAGE plpgsql STABLE;

-- Performance monitoring query for read model efficiency
CREATE OR REPLACE VIEW v_read_model_performance AS
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation,
    most_common_vals,
    most_common_freqs
FROM pg_stats 
WHERE schemaname = 'public' 
    AND tablename IN ('mv_daily_machine_utilization', 'mv_daily_operator_workload', 'mv_daily_job_flow_metrics')
ORDER BY schemaname, tablename, attname;

-- Query to monitor index usage for read models
CREATE OR REPLACE VIEW v_read_model_index_usage AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan,
    idx_tup_read::float / NULLIF(idx_scan, 0) as avg_tuples_per_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND tablename LIKE 'mv_%'
ORDER BY idx_scan DESC, avg_tuples_per_scan DESC;