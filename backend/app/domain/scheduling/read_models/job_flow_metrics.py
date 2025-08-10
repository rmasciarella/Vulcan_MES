"""
Job flow metrics read model for throughput and makespan analysis.

Provides optimized queries for production flow analysis, cycle time measurement,
bottleneck identification, and manufacturing performance KPIs.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session


class FlowMetricType(str, Enum):
    """Types of flow metrics for different analysis needs."""
    THROUGHPUT = "throughput"
    CYCLE_TIME = "cycle_time"
    MAKESPAN = "makespan"
    WIP = "work_in_progress"
    UTILIZATION = "utilization"


class ThroughputMetrics(BaseModel):
    """Throughput analysis metrics."""
    
    period_start: datetime
    period_end: datetime
    department: str = "all"
    
    # Job-level metrics
    jobs_started: int = Field(ge=0, default=0)
    jobs_completed: int = Field(ge=0, default=0)
    jobs_in_progress: int = Field(ge=0, default=0)
    jobs_failed: int = Field(ge=0, default=0)
    
    # Task-level metrics  
    tasks_completed: int = Field(ge=0, default=0)
    tasks_failed: int = Field(ge=0, default=0)
    total_processing_hours: float = Field(ge=0.0, default=0.0)
    
    # Quality metrics
    first_pass_jobs: int = Field(ge=0, default=0)
    rework_jobs: int = Field(ge=0, default=0)
    total_rework_hours: float = Field(ge=0.0, default=0.0)
    
    # Efficiency indicators
    average_job_completion_time_hours: float = Field(ge=0.0, default=0.0)
    theoretical_minimum_time_hours: float = Field(ge=0.0, default=0.0)
    
    @property
    def completion_rate(self) -> float:
        """Calculate job completion rate."""
        if self.jobs_started <= 0:
            return 0.0
        return min(1.0, self.jobs_completed / self.jobs_started)
    
    @property
    def first_pass_yield(self) -> float:
        """Calculate first pass yield rate.""" 
        if self.jobs_completed <= 0:
            return 0.0
        return min(1.0, self.first_pass_jobs / self.jobs_completed)
    
    @property
    def throughput_jobs_per_hour(self) -> float:
        """Calculate jobs per hour throughput."""
        period_hours = (self.period_end - self.period_start).total_seconds() / 3600
        if period_hours <= 0:
            return 0.0
        return self.jobs_completed / period_hours
    
    @property
    def throughput_tasks_per_hour(self) -> float:
        """Calculate tasks per hour throughput."""
        period_hours = (self.period_end - self.period_start).total_seconds() / 3600
        if period_hours <= 0:
            return 0.0
        return self.tasks_completed / period_hours
    
    @property
    def efficiency_ratio(self) -> float:
        """Calculate flow efficiency (theoretical vs actual)."""
        if self.average_job_completion_time_hours <= 0:
            return 0.0
        if self.theoretical_minimum_time_hours <= 0:
            return 1.0
        return min(1.0, self.theoretical_minimum_time_hours / self.average_job_completion_time_hours)


class CycleTimeAnalysis(BaseModel):
    """Cycle time analysis for individual job types."""
    
    job_type: str = ""
    department: str = "all"
    analysis_period_days: int = Field(ge=1)
    
    # Sample size
    jobs_analyzed: int = Field(ge=0)
    
    # Cycle time statistics (in hours)
    mean_cycle_time: float = Field(ge=0.0, default=0.0)
    median_cycle_time: float = Field(ge=0.0, default=0.0)
    p90_cycle_time: float = Field(ge=0.0, default=0.0)
    p95_cycle_time: float = Field(ge=0.0, default=0.0)
    min_cycle_time: float = Field(ge=0.0, default=0.0)
    max_cycle_time: float = Field(ge=0.0, default=0.0)
    
    # Breakdown by stage
    avg_queue_time: float = Field(ge=0.0, default=0.0)
    avg_setup_time: float = Field(ge=0.0, default=0.0)
    avg_processing_time: float = Field(ge=0.0, default=0.0)
    avg_wait_time: float = Field(ge=0.0, default=0.0)
    
    # Variability indicators
    cycle_time_std_dev: float = Field(ge=0.0, default=0.0)
    coefficient_of_variation: float = Field(ge=0.0, default=0.0)
    
    @property
    def processing_ratio(self) -> float:
        """Calculate processing time ratio (value-add vs total)."""
        total_time = self.avg_queue_time + self.avg_setup_time + self.avg_processing_time + self.avg_wait_time
        if total_time <= 0:
            return 0.0
        return min(1.0, self.avg_processing_time / total_time)
    
    @property
    def variability_level(self) -> str:
        """Classify cycle time variability."""
        if self.coefficient_of_variation < 0.2:
            return "low"
        elif self.coefficient_of_variation < 0.5:
            return "moderate"
        elif self.coefficient_of_variation < 1.0:
            return "high"
        else:
            return "very_high"


class MakespanAnalysis(BaseModel):
    """Makespan analysis for schedule optimization."""
    
    schedule_id: UUID
    schedule_name: str = ""
    department: str = "all"
    
    # Time boundaries
    schedule_start: datetime
    schedule_end: datetime
    
    # Makespan metrics
    total_makespan_hours: float = Field(ge=0.0)
    critical_path_hours: float = Field(ge=0.0)
    total_slack_hours: float = Field(ge=0.0, default=0.0)
    
    # Resource utilization during makespan
    machine_utilization_avg: float = Field(ge=0.0, le=1.0, default=0.0)
    operator_utilization_avg: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Efficiency indicators
    theoretical_minimum_makespan: float = Field(ge=0.0, default=0.0)
    makespan_efficiency: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Critical path analysis
    critical_path_tasks: int = Field(ge=0, default=0)
    longest_task_sequence: int = Field(ge=0, default=0)
    bottleneck_resources: List[str] = Field(default_factory=list)
    
    @property
    def schedule_compression_potential(self) -> float:
        """Estimate potential for schedule compression."""
        if self.total_makespan_hours <= 0:
            return 0.0
        return min(1.0, self.total_slack_hours / self.total_makespan_hours)
    
    @property
    def resource_balance_score(self) -> float:
        """Calculate resource utilization balance."""
        if self.machine_utilization_avg <= 0 and self.operator_utilization_avg <= 0:
            return 0.0
        
        utilization_diff = abs(self.machine_utilization_avg - self.operator_utilization_avg)
        max_utilization = max(self.machine_utilization_avg, self.operator_utilization_avg)
        
        if max_utilization <= 0:
            return 1.0
        
        return max(0.0, 1.0 - (utilization_diff / max_utilization))


class WIPAnalysis(BaseModel):
    """Work in Progress analysis for flow management."""
    
    snapshot_time: datetime
    department: str = "all"
    
    # WIP counts by status
    pending_jobs: int = Field(ge=0, default=0)
    ready_jobs: int = Field(ge=0, default=0)
    in_progress_jobs: int = Field(ge=0, default=0)
    blocked_jobs: int = Field(ge=0, default=0)
    
    # Task-level WIP
    pending_tasks: int = Field(ge=0, default=0)
    ready_tasks: int = Field(ge=0, default=0)
    in_progress_tasks: int = Field(ge=0, default=0)
    blocked_tasks: int = Field(ge=0, default=0)
    
    # Age analysis (hours)
    avg_job_age: float = Field(ge=0.0, default=0.0)
    max_job_age: float = Field(ge=0.0, default=0.0)
    jobs_over_sla: int = Field(ge=0, default=0)
    
    # Resource constraints
    resource_constrained_jobs: int = Field(ge=0, default=0)
    material_constrained_jobs: int = Field(ge=0, default=0)
    
    @property
    def total_wip_jobs(self) -> int:
        """Total work in progress jobs."""
        return self.pending_jobs + self.ready_jobs + self.in_progress_jobs + self.blocked_jobs
    
    @property
    def total_wip_tasks(self) -> int:
        """Total work in progress tasks."""
        return self.pending_tasks + self.ready_tasks + self.in_progress_tasks + self.blocked_tasks
    
    @property
    def flow_efficiency(self) -> float:
        """Calculate flow efficiency (active vs waiting)."""
        total_wip = self.total_wip_tasks
        if total_wip <= 0:
            return 1.0
        return min(1.0, self.in_progress_tasks / total_wip)
    
    @property
    def constraint_impact(self) -> float:
        """Calculate impact of constraints on flow."""
        total_wip = self.total_wip_jobs
        if total_wip <= 0:
            return 0.0
        constrained = self.resource_constrained_jobs + self.material_constrained_jobs + self.blocked_jobs
        return min(1.0, constrained / total_wip)


class JobFlowMetricsReadModel:
    """
    Read model service for job flow and manufacturing metrics.
    
    Provides high-performance queries for throughput analysis, cycle time measurement,
    makespan optimization, and work-in-progress management.
    """
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    async def get_throughput_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        department: Optional[str] = None,
        job_types: Optional[List[str]] = None
    ) -> ThroughputMetrics:
        """
        Calculate throughput metrics for a time period.
        
        Args:
            start_time: Analysis period start (defaults to 30 days ago)
            end_time: Analysis period end (defaults to now)
            department: Filter by department
            job_types: Filter by job types
            
        Returns:
            Throughput metrics analysis
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=30)
        if not end_time:
            end_time = datetime.utcnow()
        
        query = """
        WITH job_metrics AS (
            SELECT 
                j.id,
                j.status,
                j.created_at,
                j.started_at,
                j.completed_at,
                j.department,
                j.job_type,
                CASE WHEN j.completed_at IS NOT NULL AND j.started_at IS NOT NULL
                     THEN EXTRACT(EPOCH FROM (j.completed_at - j.started_at))/3600
                     ELSE 0
                END as completion_time_hours,
                -- Calculate theoretical minimum time (sum of minimum processing times)
                COALESCE(SUM(t.planned_duration_minutes)/60.0, 0) as theoretical_min_hours,
                -- Rework indicator
                CASE WHEN SUM(t.rework_count) > 0 THEN 1 ELSE 0 END as has_rework,
                COALESCE(SUM(t.rework_count * COALESCE(t.actual_duration_minutes, t.planned_duration_minutes, 0))/60.0, 0) as rework_hours
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE j.created_at >= :start_time 
                AND j.created_at <= :end_time
                AND (:department IS NULL OR j.department = :department)
                AND (:job_types IS NULL OR j.job_type = ANY(:job_types::text[]))
            GROUP BY j.id, j.status, j.created_at, j.started_at, j.completed_at, j.department, j.job_type
        ),
        task_metrics AS (
            SELECT 
                COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) as failed_tasks,
                COALESCE(SUM(CASE WHEN t.actual_duration_minutes IS NOT NULL 
                                  THEN t.actual_duration_minutes 
                                  ELSE t.planned_duration_minutes END)/60.0, 0) as processing_hours
            FROM tasks t
            JOIN jobs j ON j.id = t.job_id
            WHERE j.created_at >= :start_time 
                AND j.created_at <= :end_time
                AND (:department IS NULL OR j.department = :department)
                AND (:job_types IS NULL OR j.job_type = ANY(:job_types::text[]))
        )
        SELECT 
            COUNT(*) as jobs_started,
            COUNT(CASE WHEN status IN ('COMPLETED') THEN 1 END) as jobs_completed,
            COUNT(CASE WHEN status IN ('IN_PROGRESS', 'SCHEDULED') THEN 1 END) as jobs_in_progress,
            COUNT(CASE WHEN status IN ('FAILED', 'CANCELLED') THEN 1 END) as jobs_failed,
            COUNT(CASE WHEN status = 'COMPLETED' AND has_rework = 0 THEN 1 END) as first_pass_jobs,
            COUNT(CASE WHEN status = 'COMPLETED' AND has_rework = 1 THEN 1 END) as rework_jobs,
            COALESCE(AVG(CASE WHEN completion_time_hours > 0 THEN completion_time_hours END), 0) as avg_completion_hours,
            COALESCE(AVG(CASE WHEN theoretical_min_hours > 0 THEN theoretical_min_hours END), 0) as avg_theoretical_hours,
            COALESCE(SUM(rework_hours), 0) as total_rework_hours,
            tm.completed_tasks,
            tm.failed_tasks,  
            tm.processing_hours
        FROM job_metrics jm
        CROSS JOIN task_metrics tm
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'department': department,
            'job_types': job_types or []
        }).fetchone()
        
        if not result:
            return ThroughputMetrics(
                period_start=start_time,
                period_end=end_time,
                department=department or "all"
            )
        
        return ThroughputMetrics(
            period_start=start_time,
            period_end=end_time,
            department=department or "all",
            jobs_started=result.jobs_started or 0,
            jobs_completed=result.jobs_completed or 0,
            jobs_in_progress=result.jobs_in_progress or 0,
            jobs_failed=result.jobs_failed or 0,
            tasks_completed=result.completed_tasks or 0,
            tasks_failed=result.failed_tasks or 0,
            total_processing_hours=float(result.processing_hours or 0),
            first_pass_jobs=result.first_pass_jobs or 0,
            rework_jobs=result.rework_jobs or 0,
            total_rework_hours=float(result.total_rework_hours or 0),
            average_job_completion_time_hours=float(result.avg_completion_hours or 0),
            theoretical_minimum_time_hours=float(result.avg_theoretical_hours or 0)
        )
    
    async def get_cycle_time_analysis(
        self,
        job_type: Optional[str] = None,
        department: Optional[str] = None,
        analysis_days: int = 30
    ) -> CycleTimeAnalysis:
        """
        Analyze cycle times for job completion.
        
        Args:
            job_type: Specific job type to analyze
            department: Filter by department
            analysis_days: Number of days to analyze
            
        Returns:
            Cycle time analysis results
        """
        start_time = datetime.utcnow() - timedelta(days=analysis_days)
        
        query = """
        WITH job_cycle_times AS (
            SELECT 
                j.id,
                j.job_type,
                j.department,
                EXTRACT(EPOCH FROM (j.completed_at - j.created_at))/3600 as cycle_time_hours,
                -- Breakdown into stages (simplified)
                COALESCE(EXTRACT(EPOCH FROM (j.started_at - j.created_at))/3600, 0) as queue_time,
                COALESCE(SUM(t.planned_setup_duration_minutes)/60.0, 0) as setup_time,
                COALESCE(SUM(COALESCE(t.actual_duration_minutes, t.planned_duration_minutes))/60.0, 0) as processing_time,
                -- Wait time estimated as total - (queue + setup + processing)
                GREATEST(0, 
                    EXTRACT(EPOCH FROM (j.completed_at - j.created_at))/3600 -
                    COALESCE(EXTRACT(EPOCH FROM (j.started_at - j.created_at))/3600, 0) -
                    COALESCE(SUM(t.planned_setup_duration_minutes)/60.0, 0) -
                    COALESCE(SUM(COALESCE(t.actual_duration_minutes, t.planned_duration_minutes))/60.0, 0)
                ) as wait_time
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE j.status = 'COMPLETED'
                AND j.completed_at IS NOT NULL
                AND j.created_at >= :start_time
                AND (:job_type IS NULL OR j.job_type = :job_type)
                AND (:department IS NULL OR j.department = :department)
            GROUP BY j.id, j.job_type, j.department, j.created_at, j.started_at, j.completed_at
            HAVING EXTRACT(EPOCH FROM (j.completed_at - j.created_at))/3600 > 0
        ),
        percentiles AS (
            SELECT 
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cycle_time_hours) as median_ct,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY cycle_time_hours) as p90_ct,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cycle_time_hours) as p95_ct
            FROM job_cycle_times
        )
        SELECT 
            COUNT(*) as jobs_analyzed,
            AVG(cycle_time_hours) as mean_cycle_time,
            MIN(cycle_time_hours) as min_cycle_time,
            MAX(cycle_time_hours) as max_cycle_time,
            STDDEV(cycle_time_hours) as std_dev,
            AVG(queue_time) as avg_queue_time,
            AVG(setup_time) as avg_setup_time, 
            AVG(processing_time) as avg_processing_time,
            AVG(wait_time) as avg_wait_time,
            p.median_ct,
            p.p90_ct,
            p.p95_ct
        FROM job_cycle_times jct
        CROSS JOIN percentiles p
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'job_type': job_type,
            'department': department
        }).fetchone()
        
        if not result or result.jobs_analyzed == 0:
            return CycleTimeAnalysis(
                job_type=job_type or "all",
                department=department or "all",
                analysis_period_days=analysis_days,
                jobs_analyzed=0
            )
        
        mean_ct = float(result.mean_cycle_time or 0)
        std_dev = float(result.std_dev or 0)
        coefficient_of_variation = std_dev / mean_ct if mean_ct > 0 else 0
        
        return CycleTimeAnalysis(
            job_type=job_type or "all",
            department=department or "all", 
            analysis_period_days=analysis_days,
            jobs_analyzed=result.jobs_analyzed,
            mean_cycle_time=mean_ct,
            median_cycle_time=float(result.median_ct or 0),
            p90_cycle_time=float(result.p90_ct or 0),
            p95_cycle_time=float(result.p95_ct or 0),
            min_cycle_time=float(result.min_cycle_time or 0),
            max_cycle_time=float(result.max_cycle_time or 0),
            avg_queue_time=float(result.avg_queue_time or 0),
            avg_setup_time=float(result.avg_setup_time or 0),
            avg_processing_time=float(result.avg_processing_time or 0),
            avg_wait_time=float(result.avg_wait_time or 0),
            cycle_time_std_dev=std_dev,
            coefficient_of_variation=coefficient_of_variation
        )
    
    async def get_makespan_analysis(
        self,
        schedule_id: UUID,
        include_resource_utilization: bool = True
    ) -> Optional[MakespanAnalysis]:
        """
        Analyze makespan for a specific schedule.
        
        Args:
            schedule_id: Schedule to analyze
            include_resource_utilization: Calculate resource utilization metrics
            
        Returns:
            Makespan analysis or None if schedule not found
        """
        query = """
        WITH schedule_bounds AS (
            SELECT 
                s.id,
                s.name,
                s.department,
                MIN(t.planned_start_time) as schedule_start,
                MAX(t.planned_end_time) as schedule_end,
                EXTRACT(EPOCH FROM (MAX(t.planned_end_time) - MIN(t.planned_start_time)))/3600 as makespan_hours
            FROM schedules s
            JOIN jobs j ON j.schedule_id = s.id
            JOIN tasks t ON t.job_id = j.id
            WHERE s.id = :schedule_id
                AND t.planned_start_time IS NOT NULL
                AND t.planned_end_time IS NOT NULL
            GROUP BY s.id, s.name, s.department
        ),
        critical_path AS (
            SELECT 
                COUNT(t.id) as critical_tasks,
                SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/3600) as critical_path_hours
            FROM tasks t
            JOIN jobs j ON j.id = t.job_id
            WHERE j.schedule_id = :schedule_id
                AND t.is_critical_path = true
        ),
        resource_utilization AS (
            SELECT 
                AVG(CASE 
                    WHEN m.total_capacity_hours > 0 
                    THEN LEAST(1.0, mu.utilized_hours / m.total_capacity_hours)
                    ELSE 0 
                END) as avg_machine_util,
                AVG(CASE 
                    WHEN o.total_capacity_hours > 0
                    THEN LEAST(1.0, ou.utilized_hours / o.total_capacity_hours) 
                    ELSE 0
                END) as avg_operator_util
            FROM (
                -- Machine utilization during schedule
                SELECT 
                    t.assigned_machine_id,
                    SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/3600) as utilized_hours
                FROM tasks t
                JOIN jobs j ON j.id = t.job_id
                WHERE j.schedule_id = :schedule_id 
                    AND t.assigned_machine_id IS NOT NULL
                GROUP BY t.assigned_machine_id
            ) mu
            JOIN (
                SELECT 
                    m.id,
                    EXTRACT(EPOCH FROM (sb.schedule_end - sb.schedule_start))/3600 as total_capacity_hours
                FROM machines m
                CROSS JOIN schedule_bounds sb
                WHERE m.is_active = true
            ) m ON m.id = mu.assigned_machine_id
            FULL OUTER JOIN (
                -- Operator utilization during schedule
                SELECT 
                    oa.operator_id,
                    SUM(EXTRACT(EPOCH FROM (oa.planned_end_time - oa.planned_start_time))/3600) as utilized_hours
                FROM operator_assignments oa
                JOIN tasks t ON t.id = oa.task_id
                JOIN jobs j ON j.id = t.job_id
                WHERE j.schedule_id = :schedule_id
                GROUP BY oa.operator_id
            ) ou ON false  -- Simplified join
            JOIN (
                SELECT 
                    o.id,
                    EXTRACT(EPOCH FROM (sb.schedule_end - sb.schedule_start))/3600 as total_capacity_hours
                FROM operators o
                CROSS JOIN schedule_bounds sb
                WHERE o.is_active = true
            ) o ON o.id = ou.operator_id
        ),
        theoretical_minimum AS (
            SELECT 
                SUM(EXTRACT(EPOCH FROM LEAST(
                    t.planned_end_time - t.planned_start_time,
                    INTERVAL '1 hour' * COALESCE(t.planned_duration_minutes/60.0, 1)
                ))/3600) as theoretical_hours
            FROM tasks t
            JOIN jobs j ON j.id = t.job_id  
            WHERE j.schedule_id = :schedule_id
        )
        SELECT 
            sb.id,
            sb.name,
            sb.department,
            sb.schedule_start,
            sb.schedule_end,
            sb.makespan_hours,
            COALESCE(cp.critical_tasks, 0) as critical_tasks,
            COALESCE(cp.critical_path_hours, 0) as critical_path_hours,
            GREATEST(0, sb.makespan_hours - COALESCE(cp.critical_path_hours, 0)) as total_slack,
            COALESCE(ru.avg_machine_util, 0) as machine_utilization,
            COALESCE(ru.avg_operator_util, 0) as operator_utilization,
            COALESCE(tm.theoretical_hours, 0) as theoretical_min_hours
        FROM schedule_bounds sb
        LEFT JOIN critical_path cp ON true
        LEFT JOIN resource_utilization ru ON true  
        LEFT JOIN theoretical_minimum tm ON true
        """
        
        result = self.db.execute(text(query), {
            'schedule_id': schedule_id
        }).fetchone()
        
        if not result:
            return None
        
        # Calculate makespan efficiency
        makespan_efficiency = 0.0
        if result.makespan_hours > 0 and result.theoretical_min_hours > 0:
            makespan_efficiency = min(1.0, result.theoretical_min_hours / result.makespan_hours)
        
        return MakespanAnalysis(
            schedule_id=schedule_id,
            schedule_name=result.name or "",
            department=result.department or "all",
            schedule_start=result.schedule_start,
            schedule_end=result.schedule_end,
            total_makespan_hours=float(result.makespan_hours or 0),
            critical_path_hours=float(result.critical_path_hours or 0),
            total_slack_hours=float(result.total_slack or 0),
            machine_utilization_avg=float(result.machine_utilization or 0),
            operator_utilization_avg=float(result.operator_utilization or 0),
            theoretical_minimum_makespan=float(result.theoretical_min_hours or 0),
            makespan_efficiency=makespan_efficiency,
            critical_path_tasks=result.critical_tasks or 0,
            bottleneck_resources=[]  # Would need additional analysis
        )
    
    async def get_wip_analysis(
        self,
        department: Optional[str] = None,
        snapshot_time: Optional[datetime] = None
    ) -> WIPAnalysis:
        """
        Analyze current work in progress.
        
        Args:
            department: Filter by department
            snapshot_time: Analysis snapshot time (defaults to now)
            
        Returns:
            Work in progress analysis
        """
        if not snapshot_time:
            snapshot_time = datetime.utcnow()
        
        query = """
        WITH job_wip AS (
            SELECT 
                COUNT(CASE WHEN j.status = 'PENDING' THEN 1 END) as pending_jobs,
                COUNT(CASE WHEN j.status = 'READY' THEN 1 END) as ready_jobs,
                COUNT(CASE WHEN j.status IN ('IN_PROGRESS', 'SCHEDULED') THEN 1 END) as in_progress_jobs,
                COUNT(CASE WHEN j.status = 'BLOCKED' THEN 1 END) as blocked_jobs,
                AVG(CASE WHEN j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                         THEN EXTRACT(EPOCH FROM (:snapshot_time - j.created_at))/3600 
                         ELSE NULL END) as avg_job_age,
                MAX(CASE WHEN j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                         THEN EXTRACT(EPOCH FROM (:snapshot_time - j.created_at))/3600 
                         ELSE 0 END) as max_job_age,
                COUNT(CASE WHEN j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                           AND j.due_date IS NOT NULL 
                           AND j.due_date < :snapshot_time 
                           THEN 1 END) as jobs_over_sla
            FROM jobs j
            WHERE j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                AND (:department IS NULL OR j.department = :department)
        ),
        task_wip AS (
            SELECT 
                COUNT(CASE WHEN t.status = 'PENDING' THEN 1 END) as pending_tasks,
                COUNT(CASE WHEN t.status = 'READY' THEN 1 END) as ready_tasks,
                COUNT(CASE WHEN t.status = 'IN_PROGRESS' THEN 1 END) as in_progress_tasks,
                COUNT(CASE WHEN t.status IN ('BLOCKED', 'FAILED') THEN 1 END) as blocked_tasks
            FROM tasks t
            JOIN jobs j ON j.id = t.job_id
            WHERE t.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'BLOCKED', 'FAILED')
                AND j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                AND (:department IS NULL OR j.department = :department)
        ),
        constraint_analysis AS (
            SELECT 
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM tasks t2 
                    WHERE t2.job_id = j.id 
                        AND t2.assigned_machine_id IS NULL 
                        AND t2.status IN ('READY', 'SCHEDULED')
                ) THEN 1 END) as resource_constrained,
                0 as material_constrained  -- Would need material tracking
            FROM jobs j
            WHERE j.status IN ('PENDING', 'READY', 'IN_PROGRESS', 'SCHEDULED', 'BLOCKED')
                AND (:department IS NULL OR j.department = :department)
        )
        SELECT 
            jw.pending_jobs,
            jw.ready_jobs,
            jw.in_progress_jobs,
            jw.blocked_jobs,
            tw.pending_tasks,
            tw.ready_tasks,
            tw.in_progress_tasks,
            tw.blocked_tasks,
            COALESCE(jw.avg_job_age, 0) as avg_job_age,
            COALESCE(jw.max_job_age, 0) as max_job_age,
            COALESCE(jw.jobs_over_sla, 0) as jobs_over_sla,
            COALESCE(ca.resource_constrained, 0) as resource_constrained,
            COALESCE(ca.material_constrained, 0) as material_constrained
        FROM job_wip jw
        CROSS JOIN task_wip tw
        CROSS JOIN constraint_analysis ca
        """
        
        result = self.db.execute(text(query), {
            'snapshot_time': snapshot_time,
            'department': department
        }).fetchone()
        
        if not result:
            return WIPAnalysis(
                snapshot_time=snapshot_time,
                department=department or "all"
            )
        
        return WIPAnalysis(
            snapshot_time=snapshot_time,
            department=department or "all",
            pending_jobs=result.pending_jobs or 0,
            ready_jobs=result.ready_jobs or 0,
            in_progress_jobs=result.in_progress_jobs or 0,
            blocked_jobs=result.blocked_jobs or 0,
            pending_tasks=result.pending_tasks or 0,
            ready_tasks=result.ready_tasks or 0,
            in_progress_tasks=result.in_progress_tasks or 0,
            blocked_tasks=result.blocked_tasks or 0,
            avg_job_age=float(result.avg_job_age or 0),
            max_job_age=float(result.max_job_age or 0),
            jobs_over_sla=result.jobs_over_sla or 0,
            resource_constrained_jobs=result.resource_constrained or 0,
            material_constrained_jobs=result.material_constrained or 0
        )
    
    async def get_flow_bottlenecks(
        self,
        department: Optional[str] = None,
        analysis_days: int = 7
    ) -> List[Dict]:
        """
        Identify flow bottlenecks in the production system.
        
        Args:
            department: Filter by department
            analysis_days: Number of days to analyze
            
        Returns:
            List of bottleneck analysis results
        """
        start_time = datetime.utcnow() - timedelta(days=analysis_days)
        
        query = """
        WITH resource_flow AS (
            SELECT 
                'machine' as resource_type,
                m.id::text as resource_id,
                m.name as resource_name,
                m.department,
                COUNT(t.id) as tasks_processed,
                SUM(t.delay_minutes) as total_delay_minutes,
                AVG(t.delay_minutes) as avg_delay_minutes,
                COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) as failed_tasks
            FROM machines m
            LEFT JOIN tasks t ON t.assigned_machine_id = m.id
                AND t.planned_start_time >= :start_time
            WHERE m.is_active = true
                AND (:department IS NULL OR m.department = :department)
            GROUP BY m.id, m.name, m.department
            
            UNION ALL
            
            SELECT 
                'operator' as resource_type,
                o.id::text as resource_id,
                o.first_name || ' ' || o.last_name as resource_name,
                o.department,
                COUNT(oa.id) as tasks_processed,
                SUM(COALESCE(t.delay_minutes, 0)) as total_delay_minutes,
                AVG(COALESCE(t.delay_minutes, 0)) as avg_delay_minutes,
                COUNT(CASE WHEN oa.status = 'COMPLETED' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN oa.status = 'FAILED' THEN 1 END) as failed_tasks
            FROM operators o
            LEFT JOIN operator_assignments oa ON oa.operator_id = o.id
                AND oa.planned_start_time >= :start_time
            LEFT JOIN tasks t ON t.id = oa.task_id
            WHERE o.is_active = true
                AND (:department IS NULL OR o.department = :department)
            GROUP BY o.id, o.first_name, o.last_name, o.department
        )
        SELECT 
            resource_type,
            resource_id,
            resource_name,
            department,
            tasks_processed,
            total_delay_minutes,
            avg_delay_minutes,
            completed_tasks,
            failed_tasks,
            CASE 
                WHEN tasks_processed > 0 
                THEN completed_tasks::float / tasks_processed 
                ELSE 0 
            END as completion_rate,
            CASE 
                WHEN avg_delay_minutes > 60 AND completion_rate < 0.8 THEN 'critical'
                WHEN avg_delay_minutes > 30 AND completion_rate < 0.9 THEN 'high'
                WHEN avg_delay_minutes > 15 OR completion_rate < 0.95 THEN 'medium'
                ELSE 'low'
            END as bottleneck_severity
        FROM resource_flow
        WHERE tasks_processed > 0
        ORDER BY avg_delay_minutes DESC, completion_rate ASC
        LIMIT 20
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'department': department
        })
        
        bottlenecks = []
        for row in result.fetchall():
            bottlenecks.append({
                'resource_type': row.resource_type,
                'resource_id': row.resource_id,
                'resource_name': row.resource_name,
                'department': row.department,
                'tasks_processed': row.tasks_processed,
                'total_delay_minutes': row.total_delay_minutes or 0,
                'avg_delay_minutes': float(row.avg_delay_minutes or 0),
                'completed_tasks': row.completed_tasks or 0,
                'failed_tasks': row.failed_tasks or 0,
                'completion_rate': float(row.completion_rate or 0),
                'bottleneck_severity': row.bottleneck_severity,
                'throughput_impact': self._calculate_throughput_impact(
                    row.tasks_processed or 0,
                    float(row.avg_delay_minutes or 0),
                    float(row.completion_rate or 0)
                )
            })
        
        return bottlenecks
    
    def _calculate_throughput_impact(self, tasks_processed: int, avg_delay: float, completion_rate: float) -> str:
        """Calculate the impact of a bottleneck on overall throughput."""
        if tasks_processed < 5:
            return "minimal"
        
        impact_score = (tasks_processed / 100.0) * (avg_delay / 60.0) * (1.0 - completion_rate)
        
        if impact_score > 2.0:
            return "high"
        elif impact_score > 1.0:
            return "medium"
        else:
            return "low"