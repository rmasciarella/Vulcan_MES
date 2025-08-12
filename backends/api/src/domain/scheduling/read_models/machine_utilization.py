"""
Machine utilization read model with time-bucketed aggregations.

Provides optimized queries for machine utilization metrics, capacity planning,
and efficiency analysis using pre-computed time buckets for fast dashboard queries.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session


class TimeBucketType:
    """Time bucket aggregation types for different reporting needs."""
    
    HOURLY = "hourly"
    DAILY = "daily" 
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MachineUtilizationBucket(BaseModel):
    """Time-bucketed machine utilization data."""
    
    machine_id: UUID
    machine_name: str = ""
    bucket_start: datetime
    bucket_end: datetime
    bucket_type: str
    
    # Utilization metrics
    total_scheduled_minutes: int = Field(ge=0)
    total_actual_minutes: int = Field(ge=0) 
    total_available_minutes: int = Field(ge=0)
    
    # Performance metrics
    setup_minutes: int = Field(ge=0, default=0)
    idle_minutes: int = Field(ge=0, default=0)
    maintenance_minutes: int = Field(ge=0, default=0)
    breakdown_minutes: int = Field(ge=0, default=0)
    
    # Task completion metrics
    tasks_scheduled: int = Field(ge=0, default=0)
    tasks_completed: int = Field(ge=0, default=0)
    tasks_failed: int = Field(ge=0, default=0)
    
    # Quality metrics
    rework_count: int = Field(ge=0, default=0)
    average_task_duration_minutes: float = Field(ge=0.0, default=0.0)
    
    @property
    def scheduled_utilization_rate(self) -> float:
        """Calculate scheduled utilization rate (0.0 to 1.0)."""
        if self.total_available_minutes <= 0:
            return 0.0
        return min(1.0, self.total_scheduled_minutes / self.total_available_minutes)
    
    @property
    def actual_utilization_rate(self) -> float:
        """Calculate actual utilization rate (0.0 to 1.0)."""
        if self.total_available_minutes <= 0:
            return 0.0
        return min(1.0, self.total_actual_minutes / self.total_available_minutes)
    
    @property
    def efficiency_rate(self) -> float:
        """Calculate efficiency rate (actual vs scheduled)."""
        if self.total_scheduled_minutes <= 0:
            return 0.0
        return min(1.0, self.total_actual_minutes / self.total_scheduled_minutes)
    
    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate."""
        if self.tasks_scheduled <= 0:
            return 0.0
        return min(1.0, self.tasks_completed / self.tasks_scheduled)
    
    @property
    def setup_percentage(self) -> float:
        """Calculate setup time as percentage of total scheduled time."""
        if self.total_scheduled_minutes <= 0:
            return 0.0
        return min(1.0, self.setup_minutes / self.total_scheduled_minutes)


class MachineUtilizationSummary(BaseModel):
    """Aggregated machine utilization summary across multiple time periods."""
    
    machine_id: UUID
    machine_name: str
    period_start: datetime
    period_end: datetime
    
    # Aggregated metrics
    average_utilization: float = Field(ge=0.0, le=1.0)
    peak_utilization: float = Field(ge=0.0, le=1.0)
    total_productive_hours: float = Field(ge=0.0)
    total_idle_hours: float = Field(ge=0.0)
    
    # Performance trends
    utilization_trend: str = "stable"  # improving, declining, stable
    efficiency_score: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Capacity insights
    capacity_constraint_score: float = Field(ge=0.0, le=1.0, default=0.0)
    recommended_additional_capacity_hours: float = Field(ge=0.0, default=0.0)


class MachineUtilizationReadModel:
    """
    Read model service for machine utilization analytics.
    
    Provides high-performance queries for machine utilization data
    with time-bucketed aggregations and dashboard-optimized views.
    """
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    async def get_machine_utilization_buckets(
        self,
        machine_ids: Optional[List[UUID]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bucket_type: str = TimeBucketType.HOURLY,
        include_inactive: bool = False
    ) -> List[MachineUtilizationBucket]:
        """
        Get time-bucketed machine utilization data.
        
        Args:
            machine_ids: Specific machines to query (None for all)
            start_time: Query start time (defaults to 7 days ago)
            end_time: Query end time (defaults to now)
            bucket_type: Time bucket aggregation type
            include_inactive: Include inactive/down machines
            
        Returns:
            List of utilization buckets ordered by machine and time
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)
        if not end_time:
            end_time = datetime.utcnow()
            
        # Build the optimized query based on bucket type
        query = self._build_utilization_query(
            machine_ids, start_time, end_time, bucket_type, include_inactive
        )
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'machine_ids': [str(mid) for mid in (machine_ids or [])]
        })
        
        buckets = []
        for row in result.fetchall():
            buckets.append(MachineUtilizationBucket(
                machine_id=UUID(row.machine_id),
                machine_name=row.machine_name or "",
                bucket_start=row.bucket_start,
                bucket_end=row.bucket_end,
                bucket_type=bucket_type,
                total_scheduled_minutes=row.scheduled_minutes or 0,
                total_actual_minutes=row.actual_minutes or 0,
                total_available_minutes=row.available_minutes or 0,
                setup_minutes=row.setup_minutes or 0,
                idle_minutes=row.idle_minutes or 0,
                maintenance_minutes=row.maintenance_minutes or 0,
                breakdown_minutes=row.breakdown_minutes or 0,
                tasks_scheduled=row.tasks_scheduled or 0,
                tasks_completed=row.tasks_completed or 0,
                tasks_failed=row.tasks_failed or 0,
                rework_count=row.rework_count or 0,
                average_task_duration_minutes=row.avg_task_duration or 0.0
            ))
        
        return buckets
    
    async def get_machine_utilization_summary(
        self,
        machine_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> MachineUtilizationSummary:
        """
        Get aggregated utilization summary for a specific machine.
        
        Args:
            machine_id: Machine to analyze
            start_time: Analysis period start
            end_time: Analysis period end
            
        Returns:
            Utilization summary with trends and recommendations
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=30)
        if not end_time:
            end_time = datetime.utcnow()
            
        # Get daily buckets for trend analysis
        buckets = await self.get_machine_utilization_buckets(
            machine_ids=[machine_id],
            start_time=start_time,
            end_time=end_time,
            bucket_type=TimeBucketType.DAILY
        )
        
        if not buckets:
            return MachineUtilizationSummary(
                machine_id=machine_id,
                machine_name="",
                period_start=start_time,
                period_end=end_time,
                average_utilization=0.0,
                peak_utilization=0.0,
                total_productive_hours=0.0,
                total_idle_hours=0.0
            )
        
        # Calculate aggregated metrics
        utilization_rates = [b.actual_utilization_rate for b in buckets]
        avg_utilization = sum(utilization_rates) / len(utilization_rates)
        peak_utilization = max(utilization_rates)
        
        total_productive_minutes = sum(b.total_actual_minutes for b in buckets)
        total_idle_minutes = sum(b.idle_minutes for b in buckets)
        
        # Determine utilization trend
        if len(buckets) >= 7:  # Need at least a week of data for trend
            recent_avg = sum(utilization_rates[-3:]) / 3  # Last 3 days
            earlier_avg = sum(utilization_rates[:3]) / 3   # First 3 days
            
            if recent_avg > earlier_avg + 0.1:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Calculate efficiency score based on completion rate and actual vs scheduled
        completion_rates = [b.completion_rate for b in buckets if b.tasks_scheduled > 0]
        efficiency_rates = [b.efficiency_rate for b in buckets if b.total_scheduled_minutes > 0]
        
        avg_completion = sum(completion_rates) / len(completion_rates) if completion_rates else 0.0
        avg_efficiency = sum(efficiency_rates) / len(efficiency_rates) if efficiency_rates else 0.0
        efficiency_score = (avg_completion + avg_efficiency) / 2.0
        
        # Capacity constraint analysis
        high_utilization_days = sum(1 for rate in utilization_rates if rate > 0.85)
        capacity_constraint_score = high_utilization_days / len(buckets)
        
        # Recommend additional capacity if consistently over 85% utilization
        recommended_hours = 0.0
        if capacity_constraint_score > 0.5:  # More than 50% of days over 85%
            avg_over_capacity = sum(max(0, rate - 0.85) for rate in utilization_rates) / len(utilization_rates)
            recommended_hours = avg_over_capacity * 8.0  # 8 hours per day
        
        machine_name = buckets[0].machine_name if buckets else ""
        
        return MachineUtilizationSummary(
            machine_id=machine_id,
            machine_name=machine_name,
            period_start=start_time,
            period_end=end_time,
            average_utilization=avg_utilization,
            peak_utilization=peak_utilization,
            total_productive_hours=total_productive_minutes / 60.0,
            total_idle_hours=total_idle_minutes / 60.0,
            utilization_trend=trend,
            efficiency_score=efficiency_score,
            capacity_constraint_score=capacity_constraint_score,
            recommended_additional_capacity_hours=recommended_hours
        )
    
    async def get_top_utilized_machines(
        self,
        limit: int = 10,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Tuple[UUID, str, float]]:
        """
        Get top utilized machines by average utilization rate.
        
        Args:
            limit: Number of top machines to return
            start_time: Query period start
            end_time: Query period end
            
        Returns:
            List of (machine_id, machine_name, utilization_rate) tuples
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)
        if not end_time:
            end_time = datetime.utcnow()
        
        query = """
        WITH machine_utilization AS (
            SELECT 
                t.assigned_machine_id as machine_id,
                m.name as machine_name,
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.actual_end_time - t.actual_start_time))/60), 0) as actual_minutes,
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/60), 0) as scheduled_minutes,
                COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks
            FROM tasks t
            JOIN machines m ON m.id = t.assigned_machine_id  
            WHERE t.planned_start_time >= :start_time 
                AND t.planned_end_time <= :end_time
                AND t.assigned_machine_id IS NOT NULL
            GROUP BY t.assigned_machine_id, m.name
        )
        SELECT 
            machine_id,
            machine_name,
            CASE 
                WHEN scheduled_minutes > 0 
                THEN LEAST(1.0, actual_minutes / scheduled_minutes)
                ELSE 0.0 
            END as utilization_rate
        FROM machine_utilization
        WHERE scheduled_minutes > 0
        ORDER BY utilization_rate DESC
        LIMIT :limit
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'limit': limit
        })
        
        return [
            (UUID(row.machine_id), row.machine_name, float(row.utilization_rate))
            for row in result.fetchall()
        ]
    
    async def get_machine_bottlenecks(
        self,
        threshold_utilization: float = 0.90,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Identify machine bottlenecks based on high utilization and task queues.
        
        Args:
            threshold_utilization: Minimum utilization rate to consider bottleneck
            start_time: Analysis period start  
            end_time: Analysis period end
            
        Returns:
            List of bottleneck analysis dictionaries
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)
        if not end_time:
            end_time = datetime.utcnow()
        
        query = """
        WITH machine_metrics AS (
            SELECT 
                t.assigned_machine_id as machine_id,
                m.name as machine_name,
                m.department,
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN t.delay_minutes > 0 THEN 1 END) as delayed_tasks,
                AVG(t.delay_minutes) as avg_delay_minutes,
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.actual_end_time - t.actual_start_time))/60), 0) as actual_minutes,
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/60), 0) as scheduled_minutes
            FROM tasks t
            JOIN machines m ON m.id = t.assigned_machine_id
            WHERE t.planned_start_time >= :start_time 
                AND t.planned_end_time <= :end_time
                AND t.assigned_machine_id IS NOT NULL
            GROUP BY t.assigned_machine_id, m.name, m.department
        )
        SELECT 
            machine_id,
            machine_name,
            department,
            total_tasks,
            completed_tasks,
            delayed_tasks,
            avg_delay_minutes,
            CASE 
                WHEN scheduled_minutes > 0 
                THEN LEAST(1.0, actual_minutes / scheduled_minutes)
                ELSE 0.0 
            END as utilization_rate,
            CASE 
                WHEN total_tasks > 0
                THEN delayed_tasks::float / total_tasks
                ELSE 0.0
            END as delay_rate
        FROM machine_metrics  
        WHERE scheduled_minutes > 0
            AND (actual_minutes / scheduled_minutes) >= :threshold
        ORDER BY utilization_rate DESC, delay_rate DESC
        """
        
        result = self.db.execute(text(query), {
            'start_time': start_time,
            'end_time': end_time,
            'threshold': threshold_utilization
        })
        
        bottlenecks = []
        for row in result.fetchall():
            bottlenecks.append({
                'machine_id': str(row.machine_id),
                'machine_name': row.machine_name,
                'department': row.department,
                'utilization_rate': float(row.utilization_rate),
                'total_tasks': row.total_tasks,
                'completed_tasks': row.completed_tasks,
                'delayed_tasks': row.delayed_tasks,
                'delay_rate': float(row.delay_rate),
                'avg_delay_minutes': float(row.avg_delay_minutes or 0),
                'bottleneck_severity': self._calculate_bottleneck_severity(
                    float(row.utilization_rate), 
                    float(row.delay_rate)
                )
            })
        
        return bottlenecks
    
    def _build_utilization_query(
        self,
        machine_ids: Optional[List[UUID]],
        start_time: datetime,
        end_time: datetime,
        bucket_type: str,
        include_inactive: bool
    ) -> str:
        """Build optimized utilization query based on bucket type."""
        
        # Time bucket SQL expressions
        bucket_expressions = {
            TimeBucketType.HOURLY: "date_trunc('hour', t.planned_start_time)",
            TimeBucketType.DAILY: "date_trunc('day', t.planned_start_time)",
            TimeBucketType.WEEKLY: "date_trunc('week', t.planned_start_time)",
            TimeBucketType.MONTHLY: "date_trunc('month', t.planned_start_time)"
        }
        
        bucket_expr = bucket_expressions.get(bucket_type, bucket_expressions[TimeBucketType.HOURLY])
        
        # Bucket duration for calculating availability
        bucket_minutes = {
            TimeBucketType.HOURLY: 60,
            TimeBucketType.DAILY: 1440,  # 24 * 60
            TimeBucketType.WEEKLY: 10080,  # 7 * 24 * 60
            TimeBucketType.MONTHLY: 43200  # 30 * 24 * 60 (approximate)
        }
        
        duration = bucket_minutes.get(bucket_type, 60)
        
        machine_filter = ""
        if machine_ids:
            machine_filter = "AND t.assigned_machine_id = ANY(:machine_ids::uuid[])"
        
        status_filter = ""
        if not include_inactive:
            status_filter = "AND m.status IN ('AVAILABLE', 'BUSY')"
        
        return f"""
        WITH time_buckets AS (
            SELECT 
                t.assigned_machine_id as machine_id,
                m.name as machine_name,
                {bucket_expr} as bucket_start,
                {bucket_expr} + INTERVAL '{duration} minutes' as bucket_end,
                
                -- Scheduled metrics
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.planned_end_time - t.planned_start_time))/60), 0) as scheduled_minutes,
                COALESCE(SUM(EXTRACT(EPOCH FROM (t.actual_end_time - t.actual_start_time))/60), 0) as actual_minutes,
                COALESCE(SUM(COALESCE(t.planned_setup_duration_minutes, 0)), 0) as setup_minutes,
                
                -- Task metrics  
                COUNT(*) as tasks_scheduled,
                COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as tasks_completed,
                COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) as tasks_failed,
                SUM(t.rework_count) as rework_count,
                
                -- Duration analysis
                CASE 
                    WHEN COUNT(CASE WHEN t.actual_duration_minutes IS NOT NULL THEN 1 END) > 0
                    THEN AVG(t.actual_duration_minutes)
                    ELSE 0.0
                END as avg_task_duration
                
            FROM tasks t
            JOIN machines m ON m.id = t.assigned_machine_id
            WHERE t.planned_start_time >= :start_time 
                AND t.planned_start_time < :end_time
                AND t.assigned_machine_id IS NOT NULL
                {machine_filter}
                {status_filter}
            GROUP BY t.assigned_machine_id, m.name, {bucket_expr}
        )
        SELECT 
            machine_id,
            machine_name,
            bucket_start,
            bucket_end,
            scheduled_minutes,
            actual_minutes,
            {duration} as available_minutes,
            setup_minutes,
            GREATEST(0, {duration} - scheduled_minutes) as idle_minutes,
            0 as maintenance_minutes,  -- Would need maintenance log data
            0 as breakdown_minutes,   -- Would need breakdown log data  
            tasks_scheduled,
            tasks_completed,
            tasks_failed,
            rework_count,
            avg_task_duration
        FROM time_buckets
        ORDER BY machine_id, bucket_start
        """
    
    def _calculate_bottleneck_severity(self, utilization_rate: float, delay_rate: float) -> str:
        """Calculate bottleneck severity level."""
        if utilization_rate >= 0.95 and delay_rate >= 0.3:
            return "critical"
        elif utilization_rate >= 0.90 and delay_rate >= 0.2:
            return "high"
        elif utilization_rate >= 0.85 and delay_rate >= 0.1:
            return "medium" 
        else:
            return "low"