"""
Query definitions for scheduling domain CQRS implementation.

Queries represent read operations that retrieve data from optimized read models
without modifying domain state. They provide fast, specialized views for UI and reporting.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from uuid import UUID, uuid4
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class Query(BaseModel, ABC):
    """Base class for all queries."""
    
    query_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    
    class Config:
        frozen = True  # Queries are immutable


class QueryResult(BaseModel):
    """Result of query execution."""
    
    query_id: UUID
    success: bool
    data: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    cache_hit: bool = False
    data_freshness: Optional[datetime] = None


class GetMachineUtilizationQuery(Query):
    """Query for machine utilization metrics and analytics."""
    
    # Time scope
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Filtering
    machine_ids: Optional[List[UUID]] = None
    department: Optional[str] = None
    machine_types: Optional[List[str]] = None
    
    # Aggregation options
    bucket_type: str = "hourly"  # hourly, daily, weekly, monthly
    include_inactive: bool = False
    
    # Metrics selection
    include_efficiency_metrics: bool = True
    include_bottleneck_analysis: bool = False
    include_trend_analysis: bool = False
    
    # Output format
    format: str = "summary"  # summary, detailed, raw
    max_results: int = Field(default=1000, ge=1, le=10000)


class GetOperatorWorkloadQuery(Query):
    """Query for operator workload and availability metrics."""
    
    # Time scope
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    forecast_days: int = Field(default=7, ge=1, le=30)
    
    # Filtering
    operator_ids: Optional[List[UUID]] = None
    department: Optional[str] = None
    skill_codes: Optional[List[str]] = None
    
    # Analysis options
    include_availability_forecast: bool = True
    include_skill_analysis: bool = False
    include_overload_detection: bool = True
    
    # Grouping
    group_by_department: bool = False
    group_by_shift: bool = False
    
    # Thresholds
    overload_threshold: float = Field(default=0.90, ge=0.5, le=1.5)
    underutilization_threshold: float = Field(default=0.60, ge=0.1, le=0.9)


class GetJobFlowMetricsQuery(Query):
    """Query for job flow, throughput, and cycle time metrics."""
    
    # Time scope
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    analysis_period_days: int = Field(default=30, ge=1, le=365)
    
    # Filtering
    job_ids: Optional[List[UUID]] = None
    job_types: Optional[List[str]] = None
    department: Optional[str] = None
    
    # Metrics selection
    include_throughput_analysis: bool = True
    include_cycle_time_analysis: bool = True
    include_makespan_analysis: bool = False
    include_wip_analysis: bool = True
    include_bottleneck_analysis: bool = False
    
    # Statistical options
    percentiles: List[float] = Field(default=[0.5, 0.9, 0.95])
    include_trends: bool = True
    compare_to_previous_period: bool = False


class GetDashboardSummaryQuery(Query):
    """Query for executive dashboard summary with KPIs."""
    
    # Time scope (defaults to today)
    date: Optional[date] = None
    time_range_hours: int = Field(default=24, ge=1, le=168)  # 1 hour to 1 week
    
    # Scope filtering
    department: Optional[str] = None
    production_line: Optional[str] = None
    
    # Dashboard sections
    include_kpis: bool = True
    include_alerts: bool = True
    include_resource_status: bool = True
    include_schedule_health: bool = True
    include_department_summaries: bool = False
    
    # Alert configuration
    alert_severity_threshold: str = "medium"  # low, medium, high, critical
    max_alerts: int = Field(default=20, ge=5, le=100)
    
    # Freshness requirements
    max_data_age_minutes: int = Field(default=60, ge=1, le=1440)  # 1 minute to 1 day


class GetTaskScheduleQuery(Query):
    """Query for task scheduling information and timeline."""
    
    # Scope
    task_ids: Optional[List[UUID]] = None
    job_ids: Optional[List[UUID]] = None
    
    # Time filtering
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Status filtering
    task_statuses: Optional[List[str]] = None
    include_completed: bool = False
    
    # Detail level
    include_resource_assignments: bool = True
    include_dependencies: bool = True
    include_constraints: bool = False
    include_optimization_metadata: bool = False
    
    # Sorting and pagination
    sort_by: str = "planned_start_time"  # planned_start_time, priority, job_id
    sort_order: str = "asc"  # asc, desc
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class GetResourceAvailabilityQuery(Query):
    """Query for resource availability and capacity information."""
    
    # Time scope
    start_time: datetime
    end_time: datetime
    
    # Resource filtering
    resource_types: List[str] = Field(default=["machine", "operator"])
    resource_ids: Optional[List[UUID]] = None
    department: Optional[str] = None
    
    # Capability filtering
    required_capabilities: Optional[List[str]] = None
    required_skills: Optional[Dict[str, int]] = None  # skill_code -> min_level
    
    # Analysis options
    include_utilization: bool = True
    include_conflicts: bool = True
    include_maintenance_windows: bool = False
    
    # Output options
    time_granularity_minutes: int = Field(default=60, ge=15, le=1440)
    group_by_department: bool = False


class GetOptimizationHistoryQuery(Query):
    """Query for optimization run history and results."""
    
    # Time filtering
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Filtering
    optimization_objectives: Optional[List[str]] = None
    departments: Optional[List[str]] = None
    user_ids: Optional[List[UUID]] = None
    
    # Result filtering
    min_improvement_percentage: Optional[float] = None
    solution_statuses: Optional[List[str]] = None  # optimal, feasible, infeasible
    
    # Analysis options
    include_performance_metrics: bool = True
    include_comparison_analysis: bool = False
    
    # Pagination
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class GetConstraintViolationsQuery(Query):
    """Query for constraint violations and scheduling conflicts."""
    
    # Time scope
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Scope filtering
    task_ids: Optional[List[UUID]] = None
    job_ids: Optional[List[UUID]] = None
    resource_ids: Optional[List[UUID]] = None
    
    # Violation filtering
    violation_types: Optional[List[str]] = None
    severity_levels: Optional[List[str]] = None
    
    # Analysis options
    include_resolution_suggestions: bool = True
    include_impact_analysis: bool = False
    group_by_type: bool = True
    
    # Status filtering
    include_resolved: bool = False
    only_active_violations: bool = True


class GetPerformanceAnalyticsQuery(Query):
    """Query for performance analytics and benchmarking."""
    
    # Analysis scope
    analysis_period_days: int = Field(default=30, ge=7, le=365)
    comparison_period_days: Optional[int] = None
    
    # Filtering
    departments: Optional[List[str]] = None
    job_types: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None
    
    # Metrics selection
    include_efficiency_metrics: bool = True
    include_quality_metrics: bool = True
    include_utilization_metrics: bool = True
    include_financial_metrics: bool = False
    
    # Benchmarking
    benchmark_against_targets: bool = False
    benchmark_against_historical: bool = True
    include_trend_forecasting: bool = False
    
    # Statistical options
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)
    include_statistical_tests: bool = False


class GetScheduleComparisonQuery(Query):
    """Query for comparing different scheduling scenarios."""
    
    # Scenarios to compare
    baseline_scenario_id: Optional[UUID] = None
    comparison_scenario_ids: List[UUID] = Field(default_factory=list)
    
    # Comparison metrics
    compare_makespan: bool = True
    compare_utilization: bool = True
    compare_costs: bool = False
    compare_quality: bool = False
    
    # Analysis depth
    include_detailed_differences: bool = False
    include_sensitivity_analysis: bool = False
    
    # Output format
    format: str = "summary"  # summary, detailed, tabular


# Query validation helpers
def validate_time_range(start_time: datetime, end_time: datetime, max_range_days: int = 365):
    """Validate query time range."""
    if start_time >= end_time:
        raise ValueError("start_time must be before end_time")
    
    range_days = (end_time - start_time).days
    if range_days > max_range_days:
        raise ValueError(f"Time range cannot exceed {max_range_days} days")


def validate_pagination(offset: int, limit: int, max_limit: int = 1000):
    """Validate pagination parameters."""
    if offset < 0:
        raise ValueError("offset must be non-negative")
    
    if limit <= 0 or limit > max_limit:
        raise ValueError(f"limit must be between 1 and {max_limit}")


# Query factory functions
def create_current_dashboard_query(
    department: Optional[str] = None,
    user_id: Optional[UUID] = None
) -> GetDashboardSummaryQuery:
    """Create query for current dashboard state."""
    return GetDashboardSummaryQuery(
        date=date.today(),
        time_range_hours=24,
        department=department,
        include_kpis=True,
        include_alerts=True,
        include_resource_status=True,
        include_schedule_health=True,
        user_id=user_id
    )


def create_weekly_performance_query(
    department: Optional[str] = None,
    user_id: Optional[UUID] = None
) -> GetPerformanceAnalyticsQuery:
    """Create query for weekly performance analytics."""
    return GetPerformanceAnalyticsQuery(
        analysis_period_days=7,
        comparison_period_days=7,  # Compare to previous week
        departments=[department] if department else None,
        include_efficiency_metrics=True,
        include_quality_metrics=True,
        include_utilization_metrics=True,
        benchmark_against_historical=True,
        user_id=user_id
    )


def create_resource_utilization_query(
    start_time: datetime,
    end_time: datetime,
    resource_type: str = "machine",
    department: Optional[str] = None,
    user_id: Optional[UUID] = None
) -> GetMachineUtilizationQuery:
    """Create query for resource utilization analysis."""
    return GetMachineUtilizationQuery(
        start_time=start_time,
        end_time=end_time,
        department=department,
        bucket_type="hourly",
        include_efficiency_metrics=True,
        include_bottleneck_analysis=True,
        format="detailed",
        user_id=user_id
    )


def create_job_flow_analysis_query(
    analysis_days: int = 30,
    job_types: Optional[List[str]] = None,
    department: Optional[str] = None,
    user_id: Optional[UUID] = None
) -> GetJobFlowMetricsQuery:
    """Create query for job flow analysis."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=analysis_days)
    
    return GetJobFlowMetricsQuery(
        start_time=start_time,
        end_time=end_time,
        analysis_period_days=analysis_days,
        job_types=job_types,
        department=department,
        include_throughput_analysis=True,
        include_cycle_time_analysis=True,
        include_wip_analysis=True,
        include_bottleneck_analysis=True,
        include_trends=True,
        compare_to_previous_period=True,
        user_id=user_id
    )