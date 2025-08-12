"""
Unified scheduling dashboard read model with optimized queries.

Provides a single interface for dashboard views combining machine utilization,
operator load, and job flow metrics with CQRS pattern implementation.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .machine_utilization import MachineUtilizationReadModel, MachineUtilizationSummary
from .operator_load import OperatorLoadReadModel, OperatorAvailabilityForecast
from .job_flow_metrics import JobFlowMetricsReadModel, ThroughputMetrics, WIPAnalysis


class DashboardTimeRange(BaseModel):
    """Time range specification for dashboard queries."""
    
    start_time: datetime
    end_time: datetime
    
    @property 
    def duration_hours(self) -> float:
        """Calculate duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600
    
    @property
    def duration_days(self) -> int:
        """Calculate duration in days."""
        return (self.end_time.date() - self.start_time.date()).days + 1


class DashboardKPIs(BaseModel):
    """Key Performance Indicators for the scheduling dashboard."""
    
    time_range: DashboardTimeRange
    department: str = "all"
    
    # Overall efficiency metrics
    overall_oee: float = Field(ge=0.0, le=1.0, default=0.0)  # Overall Equipment Effectiveness
    schedule_adherence: float = Field(ge=0.0, le=1.0, default=0.0)
    throughput_efficiency: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Resource utilization
    avg_machine_utilization: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_operator_utilization: float = Field(ge=0.0, le=1.0, default=0.0)
    resource_balance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Job flow metrics
    jobs_completed_today: int = Field(ge=0, default=0)
    avg_cycle_time_hours: float = Field(ge=0.0, default=0.0)
    first_pass_yield: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Current status
    active_jobs: int = Field(ge=0, default=0)
    jobs_at_risk: int = Field(ge=0, default=0)  # Behind schedule or blocked
    critical_bottlenecks: int = Field(ge=0, default=0)
    
    # Trends (compared to previous period)
    utilization_trend: str = "stable"  # improving, declining, stable
    throughput_trend: str = "stable"
    efficiency_trend: str = "stable"


class ResourceAlert(BaseModel):
    """Alert for resource issues requiring attention."""
    
    alert_id: str
    alert_type: str  # utilization, bottleneck, breakdown, overload
    severity: str  # low, medium, high, critical
    resource_type: str  # machine, operator, department
    resource_id: UUID
    resource_name: str
    
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    
    # Action recommendations
    recommended_actions: List[str] = Field(default_factory=list)
    estimated_impact_hours: Optional[float] = None


class ScheduleHealthStatus(BaseModel):
    """Overall health status of the current schedule."""
    
    schedule_id: Optional[UUID] = None
    assessment_time: datetime = Field(default_factory=datetime.utcnow)
    
    # Overall health score (0-100)
    health_score: int = Field(ge=0, le=100, default=100)
    health_status: str = "healthy"  # healthy, warning, critical
    
    # Component scores
    resource_availability_score: int = Field(ge=0, le=100, default=100)
    schedule_feasibility_score: int = Field(ge=0, le=100, default=100)
    bottleneck_impact_score: int = Field(ge=0, le=100, default=100)
    quality_risk_score: int = Field(ge=0, le=100, default=100)
    
    # Issues summary
    critical_issues: int = Field(ge=0, default=0)
    warning_issues: int = Field(ge=0, default=0)
    
    # Forecast
    projected_completion: Optional[datetime] = None
    delay_risk: str = "low"  # low, medium, high
    
    @property
    def overall_status_color(self) -> str:
        """Get status color for UI display."""
        if self.health_score >= 80:
            return "green"
        elif self.health_score >= 60:
            return "yellow"
        else:
            return "red"


class DepartmentSummary(BaseModel):
    """Summary metrics for a specific department."""
    
    department: str
    analysis_time: datetime = Field(default_factory=datetime.utcnow)
    
    # Resource counts
    total_machines: int = Field(ge=0, default=0)
    active_machines: int = Field(ge=0, default=0)
    total_operators: int = Field(ge=0, default=0)
    available_operators: int = Field(ge=0, default=0)
    
    # Utilization metrics
    machine_utilization_avg: float = Field(ge=0.0, le=1.0, default=0.0)
    operator_utilization_avg: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Job flow
    jobs_in_progress: int = Field(ge=0, default=0)
    jobs_completed_today: int = Field(ge=0, default=0)
    jobs_behind_schedule: int = Field(ge=0, default=0)
    
    # Issues
    active_alerts: int = Field(ge=0, default=0)
    critical_alerts: int = Field(ge=0, default=0)


class SchedulingDashboardReadModel:
    """
    Unified read model service for scheduling dashboard.
    
    Implements CQRS pattern with optimized queries for dashboard views,
    combining machine utilization, operator load, and job flow metrics.
    """
    
    def __init__(self, db_session: Session):
        """Initialize with database session and sub-models."""
        self.db = db_session
        self.machine_model = MachineUtilizationReadModel(db_session)
        self.operator_model = OperatorLoadReadModel(db_session)
        self.job_flow_model = JobFlowMetricsReadModel(db_session)
    
    async def get_dashboard_kpis(
        self,
        time_range: Optional[DashboardTimeRange] = None,
        department: Optional[str] = None
    ) -> DashboardKPIs:
        """
        Get key performance indicators for the dashboard.
        
        Args:
            time_range: Time range for analysis (defaults to today)
            department: Department filter
            
        Returns:
            Dashboard KPIs with current metrics and trends
        """
        if not time_range:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            time_range = DashboardTimeRange(
                start_time=today,
                end_time=today + timedelta(days=1)
            )
        
        # Get core metrics using optimized materialized views
        query = """
        WITH current_metrics AS (
            SELECT 
                -- Machine utilization from materialized view
                AVG(mmu.actual_utilization_rate) as avg_machine_util,
                COUNT(CASE WHEN mmu.actual_utilization_rate > 0.9 THEN 1 END) as overutilized_machines,
                
                -- Job metrics from materialized view
                SUM(jfm.completed_jobs) as jobs_completed,
                AVG(jfm.avg_completion_time_hours) as avg_cycle_time,
                CASE WHEN SUM(jfm.completed_jobs) > 0
                     THEN SUM(jfm.first_pass_jobs)::float / SUM(jfm.completed_jobs)
                     ELSE 0 END as first_pass_yield,
                     
                -- Active jobs count
                SUM(jfm.active_jobs) as active_jobs_count
            FROM mv_daily_machine_utilization mmu
            JOIN mv_daily_job_flow_metrics jfm ON jfm.metrics_date = mmu.utilization_date
                AND (jfm.department = mmu.department OR :department IS NULL)
            WHERE mmu.utilization_date >= :start_date
                AND mmu.utilization_date < :end_date
                AND (:department IS NULL OR mmu.department = :department)
        ),
        operator_metrics AS (
            SELECT 
                AVG(mow.utilization_rate) as avg_operator_util,
                COUNT(CASE WHEN mow.load_percentage > 0.95 THEN 1 END) as overloaded_operators
            FROM mv_daily_operator_workload mow
            WHERE mow.workload_date >= :start_date
                AND mow.workload_date < :end_date
                AND (:department IS NULL OR mow.department = :department)
        ),
        risk_assessment AS (
            SELECT 
                COUNT(CASE WHEN j.due_date < CURRENT_TIMESTAMP AND j.status NOT IN ('COMPLETED', 'CANCELLED') 
                           THEN 1 END) as jobs_at_risk,
                COUNT(CASE WHEN t.delay_minutes > 30 THEN 1 END) as delayed_tasks
            FROM jobs j
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE j.created_at >= :start_time
                AND j.created_at < :end_time
                AND (:department IS NULL OR j.department = :department)
        ),
        previous_period AS (
            SELECT 
                AVG(mmu.actual_utilization_rate) as prev_machine_util,
                AVG(mow.utilization_rate) as prev_operator_util,
                SUM(jfm.completed_jobs) as prev_completed_jobs
            FROM mv_daily_machine_utilization mmu
            JOIN mv_daily_job_flow_metrics jfm ON jfm.metrics_date = mmu.utilization_date
            JOIN mv_daily_operator_workload mow ON mow.workload_date = mmu.utilization_date
            WHERE mmu.utilization_date >= :start_date - INTERVAL '7 days'
                AND mmu.utilization_date < :start_date
                AND (:department IS NULL OR mmu.department = :department)
        )
        SELECT 
            cm.*,
            om.avg_operator_util,
            om.overloaded_operators,
            ra.jobs_at_risk,
            ra.delayed_tasks,
            pp.prev_machine_util,
            pp.prev_operator_util,
            pp.prev_completed_jobs
        FROM current_metrics cm
        CROSS JOIN operator_metrics om
        CROSS JOIN risk_assessment ra
        CROSS JOIN previous_period pp
        """
        
        result = self.db.execute(text(query), {
            'start_time': time_range.start_time,
            'end_time': time_range.end_time,
            'start_date': time_range.start_time.date(),
            'end_date': time_range.end_time.date(),
            'department': department
        }).fetchone()
        
        if not result:
            return DashboardKPIs(
                time_range=time_range,
                department=department or "all"
            )
        
        # Calculate OEE (simplified)
        machine_util = float(result.avg_machine_util or 0)
        first_pass_yield = float(result.first_pass_yield or 0)
        schedule_adherence = max(0.0, 1.0 - (float(result.delayed_tasks or 0) / max(1, result.active_jobs_count or 1)))
        overall_oee = machine_util * first_pass_yield * schedule_adherence
        
        # Calculate resource balance
        operator_util = float(result.avg_operator_util or 0)
        resource_balance = 1.0 - abs(machine_util - operator_util) if machine_util > 0 and operator_util > 0 else 0.0
        
        # Determine trends
        util_trend = self._calculate_trend(machine_util, float(result.prev_machine_util or 0))
        throughput_trend = self._calculate_trend(
            float(result.jobs_completed or 0), 
            float(result.prev_completed_jobs or 0)
        )
        efficiency_trend = self._calculate_trend(first_pass_yield, 0.95)  # Compare to target
        
        return DashboardKPIs(
            time_range=time_range,
            department=department or "all",
            overall_oee=overall_oee,
            schedule_adherence=schedule_adherence,
            throughput_efficiency=first_pass_yield,
            avg_machine_utilization=machine_util,
            avg_operator_utilization=operator_util,
            resource_balance_score=resource_balance,
            jobs_completed_today=result.jobs_completed or 0,
            avg_cycle_time_hours=float(result.avg_cycle_time or 0),
            first_pass_yield=first_pass_yield,
            active_jobs=result.active_jobs_count or 0,
            jobs_at_risk=result.jobs_at_risk or 0,
            critical_bottlenecks=result.overutilized_machines or 0,
            utilization_trend=util_trend,
            throughput_trend=throughput_trend,
            efficiency_trend=efficiency_trend
        )
    
    async def get_resource_alerts(
        self,
        severity_threshold: str = "medium",
        department: Optional[str] = None,
        limit: int = 20
    ) -> List[ResourceAlert]:
        """
        Get current resource alerts requiring attention.
        
        Args:
            severity_threshold: Minimum severity level to include
            department: Department filter
            limit: Maximum number of alerts to return
            
        Returns:
            List of resource alerts ordered by severity and impact
        """
        alerts = []
        
        # Machine utilization alerts
        machine_bottlenecks = await self.machine_model.get_machine_bottlenecks(
            threshold_utilization=0.90,
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow()
        )
        
        for bottleneck in machine_bottlenecks[:10]:  # Top 10 bottlenecks
            severity = bottleneck.get('bottleneck_severity', 'low')
            if self._meets_severity_threshold(severity, severity_threshold):
                alerts.append(ResourceAlert(
                    alert_id=f"machine_bottleneck_{bottleneck['machine_id']}",
                    alert_type="bottleneck",
                    severity=severity,
                    resource_type="machine",
                    resource_id=UUID(bottleneck['machine_id']),
                    resource_name=bottleneck['machine_name'],
                    message=f"Machine {bottleneck['machine_name']} is a bottleneck with {bottleneck['utilization_rate']:.1%} utilization",
                    details=bottleneck,
                    recommended_actions=[
                        "Consider parallel processing options",
                        "Review task scheduling priorities",
                        "Evaluate additional capacity needs"
                    ],
                    estimated_impact_hours=float(bottleneck.get('avg_delay_minutes', 0)) / 60.0
                ))
        
        # Operator overload alerts
        overloaded_operators = await self.operator_model.get_overloaded_operators(
            threshold_load=0.90,
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow()
        )
        
        for operator in overloaded_operators[:10]:
            severity = operator.get('overload_severity', 'low')
            if self._meets_severity_threshold(severity, severity_threshold):
                alerts.append(ResourceAlert(
                    alert_id=f"operator_overload_{operator['operator_id']}",
                    alert_type="overload",
                    severity=severity,
                    resource_type="operator", 
                    resource_id=UUID(operator['operator_id']),
                    resource_name=operator['full_name'],
                    message=f"Operator {operator['full_name']} is overloaded at {operator['load_percentage']:.1%} capacity",
                    details=operator,
                    recommended_actions=[
                        "Redistribute workload to other operators",
                        "Consider overtime authorization",
                        "Review task priorities and dependencies"
                    ],
                    estimated_impact_hours=float(operator.get('assigned_hours', 0))
                ))
        
        # Job flow bottleneck alerts
        flow_bottlenecks = await self.job_flow_model.get_flow_bottlenecks(
            department=department,
            analysis_days=3
        )
        
        for bottleneck in flow_bottlenecks[:5]:
            severity = bottleneck.get('bottleneck_severity', 'low')
            if self._meets_severity_threshold(severity, severity_threshold):
                alerts.append(ResourceAlert(
                    alert_id=f"flow_bottleneck_{bottleneck['resource_type']}_{bottleneck['resource_id']}",
                    alert_type="bottleneck",
                    severity=severity,
                    resource_type=bottleneck['resource_type'],
                    resource_id=UUID(bottleneck['resource_id']),
                    resource_name=bottleneck['resource_name'],
                    message=f"{bottleneck['resource_type'].title()} {bottleneck['resource_name']} causing flow delays",
                    details=bottleneck,
                    recommended_actions=[
                        "Analyze root cause of delays",
                        "Consider process improvements",
                        "Review resource capacity planning"
                    ]
                ))
        
        # Sort by severity and impact
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(
            key=lambda a: (
                severity_order.get(a.severity, 0),
                a.estimated_impact_hours or 0
            ),
            reverse=True
        )
        
        return alerts[:limit]
    
    async def get_schedule_health_status(
        self,
        schedule_id: Optional[UUID] = None,
        department: Optional[str] = None
    ) -> ScheduleHealthStatus:
        """
        Assess overall health of the current or specified schedule.
        
        Args:
            schedule_id: Specific schedule to assess (None for current)
            department: Department filter
            
        Returns:
            Schedule health assessment with scores and recommendations
        """
        # Get current schedule if not specified
        current_schedule_id = schedule_id
        if not current_schedule_id:
            # Query for active schedule
            schedule_query = """
            SELECT id FROM schedules 
            WHERE status = 'ACTIVE' 
                AND (:department IS NULL OR department = :department)
            ORDER BY created_at DESC 
            LIMIT 1
            """
            result = self.db.execute(text(schedule_query), {'department': department}).fetchone()
            if result:
                current_schedule_id = result.id
        
        if not current_schedule_id:
            return ScheduleHealthStatus(
                health_score=50,
                health_status="warning",
                critical_issues=1
            )
        
        # Comprehensive health assessment query
        query = """
        WITH schedule_metrics AS (
            SELECT 
                s.id,
                s.name,
                COUNT(j.id) as total_jobs,
                COUNT(CASE WHEN j.status = 'COMPLETED' THEN 1 END) as completed_jobs,
                COUNT(CASE WHEN j.status IN ('FAILED', 'CANCELLED') THEN 1 END) as failed_jobs,
                COUNT(CASE WHEN j.due_date < CURRENT_TIMESTAMP AND j.status NOT IN ('COMPLETED', 'CANCELLED') 
                           THEN 1 END) as overdue_jobs,
                AVG(CASE WHEN t.delay_minutes > 0 THEN t.delay_minutes ELSE 0 END) as avg_delay,
                COUNT(CASE WHEN t.delay_minutes > 60 THEN 1 END) as severely_delayed_tasks,
                
                -- Resource availability
                COUNT(CASE WHEN t.assigned_machine_id IS NULL AND t.status = 'READY' THEN 1 END) as unassigned_tasks,
                
                -- Quality indicators
                SUM(t.rework_count) as total_rework,
                COUNT(CASE WHEN t.rework_count > 0 THEN 1 END) as rework_tasks
            FROM schedules s
            LEFT JOIN jobs j ON j.schedule_id = s.id
            LEFT JOIN tasks t ON t.job_id = j.id
            WHERE s.id = :schedule_id
            GROUP BY s.id, s.name
        ),
        resource_constraints AS (
            SELECT 
                COUNT(CASE WHEN m.status != 'AVAILABLE' AND m.is_active = true THEN 1 END) as unavailable_machines,
                COUNT(CASE WHEN m.is_active = true THEN 1 END) as total_machines,
                COUNT(CASE WHEN o.status != 'AVAILABLE' AND o.is_active = true THEN 1 END) as unavailable_operators,
                COUNT(CASE WHEN o.is_active = true THEN 1 END) as total_operators
            FROM machines m
            CROSS JOIN operators o
            WHERE (:department IS NULL OR (m.department = :department AND o.department = :department))
        )
        SELECT 
            sm.*,
            rc.unavailable_machines,
            rc.total_machines,
            rc.unavailable_operators, 
            rc.total_operators
        FROM schedule_metrics sm
        CROSS JOIN resource_constraints rc
        """
        
        result = self.db.execute(text(query), {
            'schedule_id': current_schedule_id,
            'department': department
        }).fetchone()
        
        if not result:
            return ScheduleHealthStatus(
                schedule_id=current_schedule_id,
                health_score=0,
                health_status="critical",
                critical_issues=1
            )
        
        # Calculate component scores (0-100)
        total_jobs = result.total_jobs or 1
        
        # Resource availability score
        machine_availability = 1.0 - (result.unavailable_machines or 0) / max(1, result.total_machines or 1)
        operator_availability = 1.0 - (result.unavailable_operators or 0) / max(1, result.total_operators or 1)
        resource_score = int(((machine_availability + operator_availability) / 2) * 100)
        
        # Schedule feasibility score
        completion_rate = (result.completed_jobs or 0) / total_jobs
        delay_penalty = min(50, (result.avg_delay or 0) / 120.0 * 50)  # Penalty for >2h avg delay
        feasibility_score = max(0, int((completion_rate * 100) - delay_penalty))
        
        # Bottleneck impact score  
        overdue_impact = (result.overdue_jobs or 0) / total_jobs * 30
        unassigned_impact = (result.unassigned_tasks or 0) / max(1, total_jobs * 3) * 30  # Assume ~3 tasks/job
        bottleneck_score = max(0, int(100 - overdue_impact - unassigned_impact))
        
        # Quality risk score
        rework_rate = (result.rework_tasks or 0) / max(1, total_jobs * 3)  
        quality_score = max(0, int(100 - (rework_rate * 50)))
        
        # Overall health score
        health_score = int((resource_score + feasibility_score + bottleneck_score + quality_score) / 4)
        
        # Determine status and issues
        critical_issues = 0
        warning_issues = 0
        
        if resource_score < 60:
            critical_issues += 1
        elif resource_score < 80:
            warning_issues += 1
            
        if feasibility_score < 60:
            critical_issues += 1
        elif feasibility_score < 80:
            warning_issues += 1
            
        if result.overdue_jobs and result.overdue_jobs > 0:
            critical_issues += 1
        
        if result.severely_delayed_tasks and result.severely_delayed_tasks > 5:
            warning_issues += 1
        
        # Determine overall status
        if health_score >= 80 and critical_issues == 0:
            status = "healthy"
        elif health_score >= 60 and critical_issues <= 1:
            status = "warning"
        else:
            status = "critical"
        
        # Estimate completion and delay risk
        delay_risk = "low"
        if result.avg_delay and result.avg_delay > 120:  # >2 hours avg delay
            delay_risk = "high"
        elif result.avg_delay and result.avg_delay > 60:  # >1 hour avg delay
            delay_risk = "medium"
        
        return ScheduleHealthStatus(
            schedule_id=current_schedule_id,
            health_score=health_score,
            health_status=status,
            resource_availability_score=resource_score,
            schedule_feasibility_score=feasibility_score,
            bottleneck_impact_score=bottleneck_score,
            quality_risk_score=quality_score,
            critical_issues=critical_issues,
            warning_issues=warning_issues,
            delay_risk=delay_risk
        )
    
    async def get_department_summaries(
        self,
        include_all: bool = True
    ) -> List[DepartmentSummary]:
        """
        Get summary metrics for all departments.
        
        Args:
            include_all: Include department-level aggregation
            
        Returns:
            List of department summaries ordered by activity level
        """
        query = """
        WITH dept_resources AS (
            SELECT 
                COALESCE(m.department, o.department, 'unknown') as department,
                COUNT(DISTINCT m.id) as total_machines,
                COUNT(DISTINCT CASE WHEN m.status = 'AVAILABLE' THEN m.id END) as active_machines,
                COUNT(DISTINCT o.id) as total_operators,
                COUNT(DISTINCT CASE WHEN o.status = 'AVAILABLE' THEN o.id END) as available_operators
            FROM machines m
            FULL OUTER JOIN operators o ON o.department = m.department
            WHERE (m.is_active = true OR m.id IS NULL)
                AND (o.is_active = true OR o.id IS NULL)
            GROUP BY COALESCE(m.department, o.department, 'unknown')
        ),
        dept_utilization AS (
            SELECT 
                department,
                AVG(actual_utilization_rate) as avg_machine_util
            FROM mv_daily_machine_utilization
            WHERE utilization_date = CURRENT_DATE
            GROUP BY department
            
            UNION ALL
            
            SELECT 
                department,
                AVG(utilization_rate) as avg_operator_util  
            FROM mv_daily_operator_workload
            WHERE workload_date = CURRENT_DATE
            GROUP BY department
        ),
        dept_jobs AS (
            SELECT 
                j.department,
                COUNT(CASE WHEN j.status IN ('IN_PROGRESS', 'SCHEDULED') THEN 1 END) as jobs_in_progress,
                COUNT(CASE WHEN j.status = 'COMPLETED' AND j.completed_at::date = CURRENT_DATE THEN 1 END) as jobs_completed_today,
                COUNT(CASE WHEN j.due_date < CURRENT_TIMESTAMP AND j.status NOT IN ('COMPLETED', 'CANCELLED') THEN 1 END) as jobs_behind
            FROM jobs j
            GROUP BY j.department
        )
        SELECT 
            dr.department,
            COALESCE(dr.total_machines, 0) as total_machines,
            COALESCE(dr.active_machines, 0) as active_machines,
            COALESCE(dr.total_operators, 0) as total_operators,
            COALESCE(dr.available_operators, 0) as available_operators,
            COALESCE(AVG(CASE WHEN du.department = dr.department THEN du.avg_machine_util END), 0) as machine_util,
            COALESCE(AVG(CASE WHEN du.department = dr.department THEN du.avg_operator_util END), 0) as operator_util,
            COALESCE(dj.jobs_in_progress, 0) as jobs_in_progress,
            COALESCE(dj.jobs_completed_today, 0) as jobs_completed_today,
            COALESCE(dj.jobs_behind, 0) as jobs_behind,
            0 as active_alerts,  -- Would need alerts table
            0 as critical_alerts
        FROM dept_resources dr
        LEFT JOIN dept_utilization du ON du.department = dr.department
        LEFT JOIN dept_jobs dj ON dj.department = dr.department
        WHERE dr.department != 'unknown'
        GROUP BY dr.department, dr.total_machines, dr.active_machines, 
                 dr.total_operators, dr.available_operators, 
                 dj.jobs_in_progress, dj.jobs_completed_today, dj.jobs_behind
        ORDER BY (COALESCE(dj.jobs_in_progress, 0) + COALESCE(dj.jobs_completed_today, 0)) DESC
        """
        
        result = self.db.execute(text(query))
        
        summaries = []
        for row in result.fetchall():
            summaries.append(DepartmentSummary(
                department=row.department,
                total_machines=row.total_machines,
                active_machines=row.active_machines,
                total_operators=row.total_operators,
                available_operators=row.available_operators,
                machine_utilization_avg=float(row.machine_util or 0),
                operator_utilization_avg=float(row.operator_util or 0),
                jobs_in_progress=row.jobs_in_progress,
                jobs_completed_today=row.jobs_completed_today,
                jobs_behind_schedule=row.jobs_behind,
                active_alerts=row.active_alerts,
                critical_alerts=row.critical_alerts
            ))
        
        return summaries
    
    def _calculate_trend(self, current: float, previous: float) -> str:
        """Calculate trend direction based on current vs previous values."""
        if previous <= 0:
            return "stable"
        
        change_pct = (current - previous) / previous
        if change_pct > 0.05:  # >5% improvement
            return "improving"
        elif change_pct < -0.05:  # >5% decline
            return "declining"
        else:
            return "stable"
    
    def _meets_severity_threshold(self, severity: str, threshold: str) -> bool:
        """Check if alert severity meets the minimum threshold."""
        severity_levels = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        return severity_levels.get(severity, 0) >= severity_levels.get(threshold, 0)