"""
Dashboard query service for real-time operational views.

This service provides optimized queries for dashboard displays,
combining data from multiple sources to provide comprehensive
operational views.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import text

from app.infrastructure.database.unit_of_work import transaction

from .base_query import BaseQueryService


@dataclass
class DashboardSummary:
    """Overall dashboard summary."""

    active_jobs: int
    overdue_jobs: int
    jobs_due_today: int
    completion_rate_today: float
    machine_utilization: float
    operator_utilization: float
    critical_alerts: int


@dataclass
class JobStatusDistribution:
    """Job status distribution."""

    planned: int = 0
    released: int = 0
    in_progress: int = 0
    completed: int = 0
    on_hold: int = 0
    cancelled: int = 0


@dataclass
class ResourceStatus:
    """Resource status summary."""

    resource_id: int
    resource_code: str
    resource_name: str
    status: str
    current_task: str | None = None
    utilization_today: float = 0.0
    next_available: datetime | None = None


@dataclass
class CriticalAlert:
    """Critical alert information."""

    alert_type: str
    severity: str
    message: str
    related_job_id: int | None = None
    related_resource_id: int | None = None
    created_at: datetime


@dataclass
class ProductionTrend:
    """Production trend data point."""

    period: str
    jobs_completed: int
    throughput_rate: float
    on_time_percentage: float


class DashboardQueryService(BaseQueryService):
    """
    Query service for dashboard data and real-time operational views.

    Provides optimized queries for dashboard components that need
    fast access to current operational status.
    """

    def get_dashboard_summary(self) -> DashboardSummary:
        """
        Get overall dashboard summary with key metrics.

        Returns:
            DashboardSummary with current operational metrics
        """
        with transaction() as uow:
            session = uow.session

            # Active jobs count
            active_jobs = session.exec(
                text("""
                    SELECT COUNT(*)
                    FROM jobs
                    WHERE status IN ('released', 'in_progress')
                """)
            ).first()[0]

            # Overdue jobs
            overdue_jobs = session.exec(
                text("""
                    SELECT COUNT(*)
                    FROM jobs
                    WHERE due_date < CURRENT_TIMESTAMP
                    AND status NOT IN ('completed', 'cancelled')
                """)
            ).first()[0]

            # Jobs due today
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_end = today_start + timedelta(days=1)

            jobs_due_today = session.exec(
                text("""
                    SELECT COUNT(*)
                    FROM jobs
                    WHERE due_date >= :today_start
                    AND due_date < :today_end
                    AND status NOT IN ('completed', 'cancelled')
                """),
                {"today_start": today_start, "today_end": today_end},
            ).first()[0]

            # Today's completion rate
            completed_today = session.exec(
                text("""
                    SELECT COUNT(*)
                    FROM jobs
                    WHERE actual_end_date >= :today_start
                    AND actual_end_date < :today_end
                    AND status = 'completed'
                """),
                {"today_start": today_start, "today_end": today_end},
            ).first()[0]

            started_today = session.exec(
                text("""
                    SELECT COUNT(*)
                    FROM jobs
                    WHERE actual_start_date >= :today_start
                    AND actual_start_date < :today_end
                """),
                {"today_start": today_start, "today_end": today_end},
            ).first()[0]

            completion_rate = (
                (completed_today / started_today * 100) if started_today > 0 else 0
            )

            # Machine utilization (simplified)
            machine_util_result = session.exec(
                text("""
                    WITH busy_machines AS (
                        SELECT COUNT(*) as busy_count
                        FROM machines
                        WHERE status = 'busy'
                    ),
                    total_machines AS (
                        SELECT COUNT(*) as total_count
                        FROM machines
                        WHERE status != 'offline'
                    )
                    SELECT
                        CASE
                            WHEN total_count > 0
                            THEN (busy_count::FLOAT / total_count * 100)
                            ELSE 0
                        END as utilization
                    FROM busy_machines, total_machines
                """)
            ).first()
            machine_utilization = machine_util_result[0] if machine_util_result else 0

            # Operator utilization (simplified)
            operator_util_result = session.exec(
                text("""
                    WITH assigned_operators AS (
                        SELECT COUNT(*) as assigned_count
                        FROM operators
                        WHERE status = 'assigned' AND is_active = true
                    ),
                    available_operators AS (
                        SELECT COUNT(*) as total_count
                        FROM operators
                        WHERE status != 'absent' AND is_active = true
                    )
                    SELECT
                        CASE
                            WHEN total_count > 0
                            THEN (assigned_count::FLOAT / total_count * 100)
                            ELSE 0
                        END as utilization
                    FROM assigned_operators, available_operators
                """)
            ).first()
            operator_utilization = (
                operator_util_result[0] if operator_util_result else 0
            )

            # Critical alerts (simplified count)
            critical_alerts = overdue_jobs + (1 if machine_utilization > 95 else 0)

            return DashboardSummary(
                active_jobs=active_jobs,
                overdue_jobs=overdue_jobs,
                jobs_due_today=jobs_due_today,
                completion_rate_today=round(completion_rate, 1),
                machine_utilization=round(machine_utilization, 1),
                operator_utilization=round(operator_utilization, 1),
                critical_alerts=critical_alerts,
            )

    def get_job_status_distribution(self) -> JobStatusDistribution:
        """
        Get distribution of jobs by status.

        Returns:
            JobStatusDistribution with counts by status
        """
        with transaction() as uow:
            session = uow.session

            result = session.exec(
                text("""
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM jobs
                    GROUP BY status
                """)
            ).all()

            distribution = JobStatusDistribution()
            for status, count in result:
                setattr(distribution, status, count)

            return distribution

    def get_active_resource_status(self) -> dict[str, list[ResourceStatus]]:
        """
        Get current status of all active resources.

        Returns:
            Dictionary with 'machines' and 'operators' lists of ResourceStatus
        """
        with transaction() as uow:
            session = uow.session

            # Machine status
            machines_result = session.exec(
                text("""
                    SELECT
                        m.id,
                        m.machine_code,
                        m.machine_name,
                        m.status::TEXT,
                        j.job_number as current_job,
                        CASE
                            WHEN t.planned_end_time IS NOT NULL AND t.planned_end_time > CURRENT_TIMESTAMP
                            THEN t.planned_end_time
                            ELSE CURRENT_TIMESTAMP
                        END as next_available
                    FROM machines m
                    LEFT JOIN tasks t ON t.assigned_machine_id = m.id
                        AND t.status = 'in_progress'
                    LEFT JOIN jobs j ON j.id = t.job_id
                    WHERE m.status != 'offline'
                    ORDER BY m.machine_code
                """)
            ).all()

            machines = [
                ResourceStatus(
                    resource_id=row[0],
                    resource_code=row[1],
                    resource_name=row[2],
                    status=row[3],
                    current_task=row[4],
                    next_available=row[5],
                )
                for row in machines_result
            ]

            # Operator status
            operators_result = session.exec(
                text("""
                    SELECT
                        o.id,
                        o.employee_id,
                        o.first_name || ' ' || o.last_name as full_name,
                        o.status::TEXT,
                        j.job_number as current_job,
                        toa.planned_end_time as next_available
                    FROM operators o
                    LEFT JOIN task_operator_assignments toa ON toa.operator_id = o.id
                        AND toa.actual_start_time IS NOT NULL
                        AND toa.actual_end_time IS NULL
                    LEFT JOIN tasks t ON t.id = toa.task_id
                    LEFT JOIN jobs j ON j.id = t.job_id
                    WHERE o.is_active = true
                    ORDER BY o.employee_id
                """)
            ).all()

            operators = [
                ResourceStatus(
                    resource_id=row[0],
                    resource_code=row[1],
                    resource_name=row[2],
                    status=row[3],
                    current_task=row[4],
                    next_available=row[5],
                )
                for row in operators_result
            ]

            return {"machines": machines, "operators": operators}

    def get_critical_alerts(self, limit: int = 20) -> list[CriticalAlert]:
        """
        Get current critical alerts requiring attention.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of CriticalAlert objects
        """
        alerts = []

        with transaction() as uow:
            session = uow.session

            # Overdue jobs
            overdue_jobs = session.exec(
                text("""
                    SELECT
                        id,
                        job_number,
                        customer_name,
                        due_date,
                        EXTRACT(HOURS FROM (CURRENT_TIMESTAMP - due_date)) as hours_overdue
                    FROM jobs
                    WHERE due_date < CURRENT_TIMESTAMP
                    AND status NOT IN ('completed', 'cancelled')
                    ORDER BY hours_overdue DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).all()

            for job in overdue_jobs:
                alerts.append(
                    CriticalAlert(
                        alert_type="overdue_job",
                        severity="high" if job[4] > 24 else "medium",
                        message=f"Job {job[1]} for {job[2]} is {job[4]:.1f} hours overdue",
                        related_job_id=job[0],
                        created_at=datetime.utcnow(),
                    )
                )

            # Resource conflicts
            conflicts = session.exec(
                text("""
                    SELECT DISTINCT
                        t1.assigned_machine_id,
                        m.machine_code,
                        COUNT(*) as conflict_count
                    FROM tasks t1
                    JOIN tasks t2 ON t1.assigned_machine_id = t2.assigned_machine_id
                        AND t1.id != t2.id
                        AND t1.planned_start_time < t2.planned_end_time
                        AND t1.planned_end_time > t2.planned_start_time
                        AND t1.status = 'scheduled'
                        AND t2.status = 'scheduled'
                    JOIN machines m ON m.id = t1.assigned_machine_id
                    GROUP BY t1.assigned_machine_id, m.machine_code
                    ORDER BY conflict_count DESC
                    LIMIT :limit
                """),
                {"limit": limit // 2},
            ).all()

            for conflict in conflicts:
                alerts.append(
                    CriticalAlert(
                        alert_type="resource_conflict",
                        severity="high",
                        message=f"Machine {conflict[1]} has {conflict[2]} scheduling conflicts",
                        related_resource_id=conflict[0],
                        created_at=datetime.utcnow(),
                    )
                )

            # Failed tasks
            failed_tasks = session.exec(
                text("""
                    SELECT
                        t.id,
                        j.job_number,
                        o.operation_name,
                        t.updated_at
                    FROM tasks t
                    JOIN jobs j ON j.id = t.job_id
                    JOIN operations o ON o.id = t.operation_id
                    WHERE t.status = 'failed'
                    AND t.updated_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                    ORDER BY t.updated_at DESC
                    LIMIT :limit
                """),
                {"limit": limit // 4},
            ).all()

            for task in failed_tasks:
                alerts.append(
                    CriticalAlert(
                        alert_type="failed_task",
                        severity="critical",
                        message=f"Task {task[2]} in job {task[1]} has failed",
                        related_job_id=task[0],
                        created_at=task[3],
                    )
                )

        # Sort by severity and creation time
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(
            key=lambda x: (severity_order.get(x.severity, 999), x.created_at),
            reverse=True,
        )

        return alerts[:limit]

    def get_production_trends(self, days: int = 30) -> list[ProductionTrend]:
        """
        Get production trend data for the specified number of days.

        Args:
            days: Number of days to include in trend

        Returns:
            List of ProductionTrend data points
        """
        with transaction() as uow:
            session = uow.session

            start_date = datetime.now() - timedelta(days=days)

            trends = session.exec(
                text("""
                    WITH daily_stats AS (
                        SELECT
                            DATE(actual_end_date) as completion_date,
                            COUNT(*) as jobs_completed,
                            COUNT(*) FILTER (WHERE actual_end_date <= due_date) as on_time_jobs
                        FROM jobs
                        WHERE actual_end_date >= :start_date
                        AND actual_end_date <= CURRENT_TIMESTAMP
                        AND status = 'completed'
                        GROUP BY DATE(actual_end_date)
                    )
                    SELECT
                        TO_CHAR(completion_date, 'YYYY-MM-DD') as period,
                        jobs_completed,
                        jobs_completed::FLOAT as throughput_rate,
                        CASE
                            WHEN jobs_completed > 0
                            THEN (on_time_jobs::FLOAT / jobs_completed * 100)
                            ELSE 0
                        END as on_time_percentage
                    FROM daily_stats
                    ORDER BY completion_date
                """),
                {"start_date": start_date},
            ).all()

            return [
                ProductionTrend(
                    period=row[0],
                    jobs_completed=row[1],
                    throughput_rate=row[2],
                    on_time_percentage=row[3],
                )
                for row in trends
            ]

    def get_capacity_utilization(self) -> dict[str, Any]:
        """
        Get current capacity utilization across all resources.

        Returns:
            Dictionary with capacity utilization metrics
        """
        with transaction() as uow:
            session = uow.session

            result = session.exec(
                text("""
                    WITH machine_capacity AS (
                        SELECT
                            COUNT(*) as total_machines,
                            COUNT(*) FILTER (WHERE status = 'busy') as busy_machines,
                            COUNT(*) FILTER (WHERE status = 'available') as available_machines,
                            COUNT(*) FILTER (WHERE status = 'maintenance') as maintenance_machines
                        FROM machines
                        WHERE status != 'offline'
                    ),
                    operator_capacity AS (
                        SELECT
                            COUNT(*) as total_operators,
                            COUNT(*) FILTER (WHERE status = 'assigned') as assigned_operators,
                            COUNT(*) FILTER (WHERE status = 'available') as available_operators,
                            COUNT(*) FILTER (WHERE status = 'on_break') as break_operators
                        FROM operators
                        WHERE is_active = true AND status != 'absent'
                    ),
                    zone_wip AS (
                        SELECT
                            pz.zone_name,
                            pz.wip_limit,
                            COUNT(DISTINCT t.job_id) as current_wip
                        FROM production_zones pz
                        LEFT JOIN operations op ON op.production_zone_id = pz.id
                        LEFT JOIN tasks t ON t.operation_id = op.id
                            AND t.status IN ('ready', 'scheduled', 'in_progress')
                        GROUP BY pz.zone_name, pz.wip_limit
                    )
                    SELECT
                        json_build_object(
                            'machines', json_build_object(
                                'total', mc.total_machines,
                                'busy', mc.busy_machines,
                                'available', mc.available_machines,
                                'maintenance', mc.maintenance_machines,
                                'utilization_rate',
                                CASE WHEN mc.total_machines > 0
                                     THEN (mc.busy_machines::FLOAT / mc.total_machines * 100)
                                     ELSE 0 END
                            ),
                            'operators', json_build_object(
                                'total', oc.total_operators,
                                'assigned', oc.assigned_operators,
                                'available', oc.available_operators,
                                'on_break', oc.break_operators,
                                'utilization_rate',
                                CASE WHEN oc.total_operators > 0
                                     THEN (oc.assigned_operators::FLOAT / oc.total_operators * 100)
                                     ELSE 0 END
                            ),
                            'zones', json_agg(
                                json_build_object(
                                    'zone_name', zw.zone_name,
                                    'wip_limit', zw.wip_limit,
                                    'current_wip', zw.current_wip,
                                    'utilization_rate',
                                    CASE WHEN zw.wip_limit > 0
                                         THEN (zw.current_wip::FLOAT / zw.wip_limit * 100)
                                         ELSE 0 END
                                )
                            )
                        ) as capacity_data
                    FROM machine_capacity mc, operator_capacity oc, zone_wip zw
                    GROUP BY mc.total_machines, mc.busy_machines, mc.available_machines, mc.maintenance_machines,
                             oc.total_operators, oc.assigned_operators, oc.available_operators, oc.break_operators
                """)
            ).first()

            return (
                result[0]
                if result
                else {
                    "machines": {
                        "total": 0,
                        "busy": 0,
                        "available": 0,
                        "utilization_rate": 0,
                    },
                    "operators": {
                        "total": 0,
                        "assigned": 0,
                        "available": 0,
                        "utilization_rate": 0,
                    },
                    "zones": [],
                }
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert all dashboard data to dictionary format."""
        return {
            "summary": asdict(self.get_dashboard_summary()),
            "job_distribution": asdict(self.get_job_status_distribution()),
            "resource_status": self.get_active_resource_status(),
            "critical_alerts": [asdict(alert) for alert in self.get_critical_alerts()],
            "production_trends": [
                asdict(trend) for trend in self.get_production_trends()
            ],
            "capacity_utilization": self.get_capacity_utilization(),
            "last_updated": datetime.utcnow().isoformat(),
        }
