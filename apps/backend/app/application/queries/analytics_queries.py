"""
Analytics query service for business intelligence and reporting.

This service provides complex analytical queries and metrics calculations
for production scheduling performance, resource utilization, and trends.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from sqlmodel import Session, and_, func, select, text

from app.infrastructure.database.sqlmodel_entities import Job, JobStatusEnum
from app.infrastructure.database.unit_of_work import transaction

from .base_query import BaseQueryService


class MetricPeriod(Enum):
    """Time periods for metrics calculation."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass
class JobMetrics:
    """Job-related metrics."""

    total_jobs: int
    completed_jobs: int
    overdue_jobs: int
    on_time_completion_rate: float
    average_completion_time_hours: float
    average_delay_hours: float


@dataclass
class ResourceMetrics:
    """Resource utilization metrics."""

    machine_utilization_rate: float
    operator_utilization_rate: float
    bottleneck_machines: list[dict[str, Any]]
    underutilized_resources: list[dict[str, Any]]


@dataclass
class ProductionMetrics:
    """Production performance metrics."""

    throughput_rate: float
    cycle_time_hours: float
    lead_time_hours: float
    setup_time_percentage: float
    rework_rate: float


@dataclass
class SchedulingMetrics:
    """Scheduling effectiveness metrics."""

    schedule_adherence_rate: float
    resource_conflicts: int
    last_minute_changes: int
    planning_horizon_coverage: float


class AnalyticsQueryService(BaseQueryService):
    """
    Query service for analytics and business intelligence.

    Provides complex analytical queries for KPIs, trends, and performance metrics
    across the production scheduling system.
    """

    def get_job_performance_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> JobMetrics:
        """
        Get job performance metrics for a time period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            JobMetrics with performance indicators
        """
        with transaction() as uow:
            session = uow.session

            # Total jobs in period
            total_jobs_query = select(func.count(Job.id)).where(
                and_(Job.created_at >= start_date, Job.created_at <= end_date)
            )
            total_jobs = session.exec(total_jobs_query).first() or 0

            # Completed jobs
            completed_jobs_query = select(func.count(Job.id)).where(
                and_(
                    Job.created_at >= start_date,
                    Job.created_at <= end_date,
                    Job.status == JobStatusEnum.COMPLETED,
                )
            )
            completed_jobs = session.exec(completed_jobs_query).first() or 0

            # Overdue jobs
            overdue_jobs_query = select(func.count(Job.id)).where(
                and_(
                    Job.created_at >= start_date,
                    Job.created_at <= end_date,
                    Job.due_date < datetime.utcnow(),
                    Job.status.not_in(
                        [JobStatusEnum.COMPLETED, JobStatusEnum.CANCELLED]
                    ),
                )
            )
            overdue_jobs = session.exec(overdue_jobs_query).first() or 0

            # On-time completion rate
            on_time_completed_query = select(func.count(Job.id)).where(
                and_(
                    Job.created_at >= start_date,
                    Job.created_at <= end_date,
                    Job.status == JobStatusEnum.COMPLETED,
                    Job.actual_end_date <= Job.due_date,
                )
            )
            on_time_completed = session.exec(on_time_completed_query).first() or 0
            on_time_rate = (
                (on_time_completed / completed_jobs * 100) if completed_jobs > 0 else 0
            )

            # Average completion time (planned vs actual)
            completion_time_query = text("""
                SELECT AVG(EXTRACT(EPOCH FROM (actual_end_date - actual_start_date))/3600.0) as avg_completion_hours
                FROM jobs
                WHERE created_at >= :start_date
                AND created_at <= :end_date
                AND status = 'completed'
                AND actual_start_date IS NOT NULL
                AND actual_end_date IS NOT NULL
            """)
            result = session.exec(
                completion_time_query, {"start_date": start_date, "end_date": end_date}
            ).first()
            avg_completion_time = float(result[0]) if result and result[0] else 0.0

            # Average delay for late jobs
            delay_query = text("""
                SELECT AVG(EXTRACT(EPOCH FROM (actual_end_date - due_date))/3600.0) as avg_delay_hours
                FROM jobs
                WHERE created_at >= :start_date
                AND created_at <= :end_date
                AND status = 'completed'
                AND actual_end_date > due_date
            """)
            delay_result = session.exec(
                delay_query, {"start_date": start_date, "end_date": end_date}
            ).first()
            avg_delay = (
                float(delay_result[0]) if delay_result and delay_result[0] else 0.0
            )

            return JobMetrics(
                total_jobs=total_jobs,
                completed_jobs=completed_jobs,
                overdue_jobs=overdue_jobs,
                on_time_completion_rate=round(on_time_rate, 2),
                average_completion_time_hours=round(avg_completion_time, 2),
                average_delay_hours=round(avg_delay, 2),
            )

    def get_resource_utilization_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> ResourceMetrics:
        """
        Get resource utilization metrics.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            ResourceMetrics with utilization data
        """
        with transaction() as uow:
            session = uow.session

            # Machine utilization rate
            machine_util_query = text("""
                WITH machine_hours AS (
                    SELECT
                        m.id,
                        m.machine_code,
                        COUNT(t.id) * 8 as available_hours,  -- Assuming 8 hours per day
                        COALESCE(SUM(EXTRACT(EPOCH FROM (t.actual_end_time - t.actual_start_time))/3600.0), 0) as utilized_hours
                    FROM machines m
                    LEFT JOIN tasks t ON t.assigned_machine_id = m.id
                        AND t.actual_start_time >= :start_date
                        AND t.actual_end_time <= :end_date
                    GROUP BY m.id, m.machine_code
                )
                SELECT
                    AVG(utilized_hours / NULLIF(available_hours, 0) * 100) as avg_utilization,
                    ARRAY_AGG(
                        JSON_BUILD_OBJECT(
                            'machine_code', machine_code,
                            'utilization_rate', utilized_hours / NULLIF(available_hours, 0) * 100
                        ) ORDER BY utilized_hours / NULLIF(available_hours, 0) DESC
                    ) FILTER (WHERE utilized_hours / NULLIF(available_hours, 0) > 0.9) as bottlenecks,
                    ARRAY_AGG(
                        JSON_BUILD_OBJECT(
                            'machine_code', machine_code,
                            'utilization_rate', utilized_hours / NULLIF(available_hours, 0) * 100
                        ) ORDER BY utilized_hours / NULLIF(available_hours, 0) ASC
                    ) FILTER (WHERE utilized_hours / NULLIF(available_hours, 0) < 0.3) as underutilized
                FROM machine_hours
            """)

            machine_result = session.exec(
                machine_util_query, {"start_date": start_date, "end_date": end_date}
            ).first()

            machine_utilization = (
                float(machine_result[0])
                if machine_result and machine_result[0]
                else 0.0
            )
            bottleneck_machines = (
                machine_result[1] if machine_result and machine_result[1] else []
            )
            underutilized_machines = (
                machine_result[2] if machine_result and machine_result[2] else []
            )

            # Operator utilization (simplified - assuming 8-hour shifts)
            operator_util_query = text("""
                WITH operator_hours AS (
                    SELECT
                        o.id,
                        o.employee_id,
                        COUNT(DISTINCT DATE(toa.planned_start_time)) * 8 as available_hours,
                        COALESCE(SUM(EXTRACT(EPOCH FROM (toa.actual_end_time - toa.actual_start_time))/3600.0), 0) as utilized_hours
                    FROM operators o
                    LEFT JOIN task_operator_assignments toa ON toa.operator_id = o.id
                        AND toa.actual_start_time >= :start_date
                        AND toa.actual_end_time <= :end_date
                    WHERE o.is_active = true
                    GROUP BY o.id, o.employee_id
                )
                SELECT AVG(utilized_hours / NULLIF(available_hours, 0) * 100) as avg_utilization
                FROM operator_hours
            """)

            operator_result = session.exec(
                operator_util_query, {"start_date": start_date, "end_date": end_date}
            ).first()

            operator_utilization = (
                float(operator_result[0])
                if operator_result and operator_result[0]
                else 0.0
            )

            return ResourceMetrics(
                machine_utilization_rate=round(machine_utilization, 2),
                operator_utilization_rate=round(operator_utilization, 2),
                bottleneck_machines=bottleneck_machines,
                underutilized_resources=underutilized_machines,
            )

    def get_production_performance_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> ProductionMetrics:
        """
        Get production performance metrics.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            ProductionMetrics with performance indicators
        """
        with transaction() as uow:
            session = uow.session

            # Throughput rate (jobs completed per day)
            days_in_period = (end_date - start_date).days or 1
            completed_jobs = (
                session.exec(
                    select(func.count(Job.id)).where(
                        and_(
                            Job.actual_end_date >= start_date,
                            Job.actual_end_date <= end_date,
                            Job.status == JobStatusEnum.COMPLETED,
                        )
                    )
                ).first()
                or 0
            )
            throughput_rate = completed_jobs / days_in_period

            # Cycle time (average time from start to completion)
            cycle_time_query = text("""
                SELECT AVG(EXTRACT(EPOCH FROM (actual_end_date - actual_start_date))/3600.0) as avg_cycle_time
                FROM jobs
                WHERE actual_end_date >= :start_date
                AND actual_end_date <= :end_date
                AND status = 'completed'
                AND actual_start_date IS NOT NULL
            """)
            cycle_result = session.exec(
                cycle_time_query, {"start_date": start_date, "end_date": end_date}
            ).first()
            cycle_time = (
                float(cycle_result[0]) if cycle_result and cycle_result[0] else 0.0
            )

            # Lead time (from job creation to completion)
            lead_time_query = text("""
                SELECT AVG(EXTRACT(EPOCH FROM (actual_end_date - created_at))/3600.0) as avg_lead_time
                FROM jobs
                WHERE actual_end_date >= :start_date
                AND actual_end_date <= :end_date
                AND status = 'completed'
            """)
            lead_result = session.exec(
                lead_time_query, {"start_date": start_date, "end_date": end_date}
            ).first()
            lead_time = float(lead_result[0]) if lead_result and lead_result[0] else 0.0

            # Setup time percentage
            setup_time_query = text("""
                SELECT
                    SUM(actual_setup_minutes) as total_setup,
                    SUM(actual_duration_minutes) as total_processing
                FROM tasks t
                JOIN jobs j ON j.id = t.job_id
                WHERE j.actual_end_date >= :start_date
                AND j.actual_end_date <= :end_date
                AND t.status = 'completed'
                AND actual_setup_minutes IS NOT NULL
                AND actual_duration_minutes IS NOT NULL
            """)
            setup_result = session.exec(
                setup_time_query, {"start_date": start_date, "end_date": end_date}
            ).first()

            setup_percentage = 0.0
            if setup_result and setup_result[0] and setup_result[1]:
                total_setup = float(setup_result[0])
                total_processing = float(setup_result[1])
                setup_percentage = (
                    total_setup / (total_setup + total_processing)
                ) * 100

            # Rework rate
            rework_query = text("""
                SELECT
                    COUNT(*) FILTER (WHERE rework_count > 0) as rework_tasks,
                    COUNT(*) as total_tasks
                FROM tasks t
                JOIN jobs j ON j.id = t.job_id
                WHERE j.actual_end_date >= :start_date
                AND j.actual_end_date <= :end_date
                AND t.status = 'completed'
            """)
            rework_result = session.exec(
                rework_query, {"start_date": start_date, "end_date": end_date}
            ).first()

            rework_rate = 0.0
            if rework_result and rework_result[1] > 0:
                rework_rate = (rework_result[0] / rework_result[1]) * 100

            return ProductionMetrics(
                throughput_rate=round(throughput_rate, 2),
                cycle_time_hours=round(cycle_time, 2),
                lead_time_hours=round(lead_time, 2),
                setup_time_percentage=round(setup_percentage, 2),
                rework_rate=round(rework_rate, 2),
            )

    def get_scheduling_effectiveness_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> SchedulingMetrics:
        """
        Get scheduling effectiveness metrics.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            SchedulingMetrics with effectiveness indicators
        """
        with transaction() as uow:
            session = uow.session

            # Schedule adherence (tasks that started/ended within planned windows)
            adherence_query = text("""
                SELECT
                    COUNT(*) FILTER (WHERE
                        ABS(EXTRACT(EPOCH FROM (actual_start_time - planned_start_time))/60.0) <= 30
                        AND ABS(EXTRACT(EPOCH FROM (actual_end_time - planned_end_time))/60.0) <= 30
                    ) as adherent_tasks,
                    COUNT(*) as total_scheduled_tasks
                FROM tasks t
                JOIN jobs j ON j.id = t.job_id
                WHERE j.created_at >= :start_date
                AND j.created_at <= :end_date
                AND t.status = 'completed'
                AND planned_start_time IS NOT NULL
                AND planned_end_time IS NOT NULL
                AND actual_start_time IS NOT NULL
                AND actual_end_time IS NOT NULL
            """)
            adherence_result = session.exec(
                adherence_query, {"start_date": start_date, "end_date": end_date}
            ).first()

            adherence_rate = 0.0
            if adherence_result and adherence_result[1] > 0:
                adherence_rate = (adherence_result[0] / adherence_result[1]) * 100

            # Resource conflicts (simplified approximation)
            conflict_query = text("""
                SELECT COUNT(*) as conflicts
                FROM tasks t1
                JOIN tasks t2 ON t1.assigned_machine_id = t2.assigned_machine_id
                    AND t1.id != t2.id
                    AND t1.planned_start_time < t2.planned_end_time
                    AND t1.planned_end_time > t2.planned_start_time
                JOIN jobs j ON j.id = t1.job_id
                WHERE j.created_at >= :start_date
                AND j.created_at <= :end_date
                AND t1.assigned_machine_id IS NOT NULL
            """)
            conflict_result = session.exec(
                conflict_query, {"start_date": start_date, "end_date": end_date}
            ).first()
            conflicts = conflict_result[0] if conflict_result else 0

            # Last minute changes (schedule changes within 24 hours of planned start)
            changes_query = text("""
                SELECT COUNT(*) as last_minute_changes
                FROM task_schedule_history tsh
                JOIN tasks t ON t.id = tsh.task_id
                JOIN jobs j ON j.id = t.job_id
                WHERE j.created_at >= :start_date
                AND j.created_at <= :end_date
                AND tsh.changed_at >= (tsh.new_planned_start - INTERVAL '24 hours')
                AND (tsh.old_planned_start != tsh.new_planned_start
                     OR tsh.old_machine_id != tsh.new_machine_id)
            """)
            try:
                changes_result = session.exec(
                    changes_query, {"start_date": start_date, "end_date": end_date}
                ).first()
                last_minute_changes = changes_result[0] if changes_result else 0
            except:
                # If table doesn't exist, return 0
                last_minute_changes = 0

            # Planning horizon coverage (percentage of future work that's scheduled)
            horizon_query = text("""
                WITH future_tasks AS (
                    SELECT
                        COUNT(*) as total_future_tasks,
                        COUNT(*) FILTER (WHERE planned_start_time IS NOT NULL) as scheduled_future_tasks
                    FROM tasks t
                    JOIN jobs j ON j.id = t.job_id
                    WHERE j.due_date > CURRENT_TIMESTAMP
                    AND t.status IN ('pending', 'ready', 'scheduled')
                )
                SELECT
                    CASE
                        WHEN total_future_tasks > 0
                        THEN (scheduled_future_tasks::FLOAT / total_future_tasks * 100)
                        ELSE 0
                    END as coverage_percentage
                FROM future_tasks
            """)
            horizon_result = session.exec(horizon_query, {}).first()
            horizon_coverage = float(horizon_result[0]) if horizon_result else 0.0

            return SchedulingMetrics(
                schedule_adherence_rate=round(adherence_rate, 2),
                resource_conflicts=conflicts,
                last_minute_changes=last_minute_changes,
                planning_horizon_coverage=round(horizon_coverage, 2),
            )

    def get_trend_analysis(
        self,
        metric_name: str,
        period: MetricPeriod,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get trend analysis for a specific metric over time.

        Args:
            metric_name: Name of metric to analyze
            period: Time period granularity
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            List of time periods with metric values
        """
        # This would implement time-series analysis for specific metrics
        # Implementation would depend on specific metrics and database capabilities

        with transaction() as uow:
            session = uow.session

            if metric_name == "job_completion_rate":
                return self._get_completion_rate_trend(
                    session, period, start_date, end_date
                )
            elif metric_name == "resource_utilization":
                return self._get_utilization_trend(
                    session, period, start_date, end_date
                )
            elif metric_name == "throughput":
                return self._get_throughput_trend(session, period, start_date, end_date)
            else:
                return []

    def _get_completion_rate_trend(
        self,
        session: Session,
        period: MetricPeriod,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get job completion rate trend."""
        period_format = {
            MetricPeriod.DAILY: "%Y-%m-%d",
            MetricPeriod.WEEKLY: "%Y-W%W",
            MetricPeriod.MONTHLY: "%Y-%m",
            MetricPeriod.QUARTERLY: "%Y-Q%q",
        }

        query = text(f"""
            SELECT
                TO_CHAR(actual_end_date, '{period_format[period]}') as period,
                COUNT(*) as completed_jobs,
                COUNT(*) FILTER (WHERE actual_end_date <= due_date) as on_time_jobs
            FROM jobs
            WHERE actual_end_date >= :start_date
            AND actual_end_date <= :end_date
            AND status = 'completed'
            GROUP BY TO_CHAR(actual_end_date, '{period_format[period]}')
            ORDER BY period
        """)

        results = session.exec(
            query, {"start_date": start_date, "end_date": end_date}
        ).all()

        return [
            {
                "period": result[0],
                "completion_rate": (result[2] / result[1] * 100)
                if result[1] > 0
                else 0,
                "total_jobs": result[1],
                "on_time_jobs": result[2],
            }
            for result in results
        ]

    def _get_utilization_trend(
        self,
        session: Session,
        period: MetricPeriod,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get resource utilization trend."""
        # Simplified implementation - would need more complex logic for accurate utilization
        return []

    def _get_throughput_trend(
        self,
        session: Session,
        period: MetricPeriod,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get throughput trend."""
        period_format = {
            MetricPeriod.DAILY: "%Y-%m-%d",
            MetricPeriod.WEEKLY: "%Y-W%W",
            MetricPeriod.MONTHLY: "%Y-%m",
            MetricPeriod.QUARTERLY: "%Y-Q%q",
        }

        query = text(f"""
            SELECT
                TO_CHAR(actual_end_date, '{period_format[period]}') as period,
                COUNT(*) as completed_jobs
            FROM jobs
            WHERE actual_end_date >= :start_date
            AND actual_end_date <= :end_date
            AND status = 'completed'
            GROUP BY TO_CHAR(actual_end_date, '{period_format[period]}')
            ORDER BY period
        """)

        results = session.exec(
            query, {"start_date": start_date, "end_date": end_date}
        ).all()

        return [{"period": result[0], "throughput": result[1]} for result in results]
