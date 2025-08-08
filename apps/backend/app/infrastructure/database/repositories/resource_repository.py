"""
Resource repository implementations for machines and operators.

This module provides repository implementations for Machine and Operator
entities, including availability checking and resource allocation support.
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, or_, select

from app.domain.scheduling.value_objects.enums import (
    MachineAutomationLevel,
    MachineStatus,
    OperatorStatus,
    SkillLevel,
)
from app.infrastructure.database.models import (
    Machine,
    MachineCreate,
    MachineSkillRequirement,
    MachineUpdate,
    Operator,
    OperatorAssignment,
    OperatorCreate,
    OperatorSkill,
    OperatorUpdate,
    Task,
)

from .base import BaseRepository, DatabaseError


class MachineRepository(BaseRepository[Machine, MachineCreate, MachineUpdate]):
    """
    Repository implementation for Machine entities.

    Provides CRUD operations plus domain-specific queries for machines,
    including availability checking and capability-based filtering.
    """

    @property
    def entity_class(self):
        """Return the Machine entity class."""
        return Machine

    def find_by_zone(self, zone: str) -> list[Machine]:
        """
        Find machines in a specific production zone.

        Args:
            zone: Production zone name

        Returns:
            List of machines in the zone

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Machine).where(Machine.zone == zone)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding machines by zone {zone}: {str(e)}"
            ) from e

    def find_by_type(self, machine_type: str) -> list[Machine]:
        """
        Find machines of a specific type.

        Args:
            machine_type: Type of machine to find

        Returns:
            List of machines of the specified type

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Machine).where(Machine.machine_type == machine_type)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding machines by type {machine_type}: {str(e)}"
            ) from e

    def find_available(self, at_time: datetime | None = None) -> list[Machine]:
        """
        Find machines that are available for work.

        Args:
            at_time: Time to check availability (defaults to now)

        Returns:
            List of available machines

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # First get machines with available status
            available_machines_statement = select(Machine).where(
                Machine.status == MachineStatus.AVAILABLE
            )
            available_machines = list(
                self.session.exec(available_machines_statement).all()
            )

            if at_time is None:
                return available_machines

            # Filter out machines that have scheduled tasks at the specified time
            truly_available = []
            for machine in available_machines:
                if self._is_machine_available_at_time(machine.id, at_time):
                    truly_available.append(machine)

            return truly_available
        except Exception as e:
            raise DatabaseError(f"Error finding available machines: {str(e)}") from e

    def find_by_automation_level(
        self, automation_level: MachineAutomationLevel
    ) -> list[Machine]:
        """
        Find machines by automation level.

        Args:
            automation_level: Automation level to filter by

        Returns:
            List of machines with specified automation level

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Machine).where(
                Machine.automation_level == automation_level
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding machines by automation level: {str(e)}"
            ) from e

    def find_with_skill_requirements(self, machine_id: UUID) -> Machine | None:
        """
        Find machine with skill requirements eagerly loaded.

        Args:
            machine_id: UUID of the machine

        Returns:
            Machine with skill requirements loaded, None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Machine)
                .options(selectinload(Machine.skill_requirements))
                .where(Machine.id == machine_id)
            )
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding machine with skill requirements: {str(e)}"
            ) from e

    def find_requiring_maintenance(self, within_days: int = 7) -> list[Machine]:
        """
        Find machines requiring maintenance within specified days.

        Args:
            within_days: Number of days to look ahead for maintenance

        Returns:
            List of machines requiring maintenance

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.utcnow() + timedelta(days=within_days)
            statement = select(Machine).where(
                and_(
                    Machine.next_maintenance_date.is_not(None),
                    Machine.next_maintenance_date <= cutoff_date,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding machines requiring maintenance: {str(e)}"
            ) from e

    def _is_machine_available_at_time(
        self, machine_id: UUID, check_time: datetime
    ) -> bool:
        """
        Check if machine is available at a specific time.

        Args:
            machine_id: UUID of the machine
            check_time: Time to check

        Returns:
            True if machine is available, False otherwise
        """
        try:
            # Check for scheduled tasks overlapping the check time
            statement = select(Task).where(
                and_(
                    Task.assigned_machine_id == machine_id,
                    Task.planned_start_time <= check_time,
                    Task.planned_end_time > check_time,
                    Task.status.in_(["scheduled", "in_progress"]),
                )
            )
            conflicting_tasks = list(self.session.exec(statement).all())
            return len(conflicting_tasks) == 0
        except Exception:
            # If we can't determine availability, assume not available for safety
            return False

    def get_utilization_stats(self, machine_id: UUID, days_back: int = 30) -> dict:
        """
        Get utilization statistics for a machine.

        Args:
            machine_id: UUID of the machine
            days_back: Number of days to look back

        Returns:
            Dictionary with utilization statistics

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from sqlalchemy import func

            start_date = datetime.utcnow() - timedelta(days=days_back)

            # Total scheduled time
            scheduled_time_query = select(
                func.sum(Task.planned_duration_minutes)
            ).where(
                and_(
                    Task.assigned_machine_id == machine_id,
                    Task.planned_start_time >= start_date,
                    Task.status != "cancelled",
                )
            )
            total_scheduled_minutes = self.session.exec(scheduled_time_query).one() or 0

            # Total actual time
            actual_time_query = select(func.sum(Task.actual_duration_minutes)).where(
                and_(
                    Task.assigned_machine_id == machine_id,
                    Task.actual_start_time >= start_date,
                    Task.status == "completed",
                )
            )
            total_actual_minutes = self.session.exec(actual_time_query).one() or 0

            # Available hours in the period (assuming 16 hours/day, 5 days/week)
            available_hours_per_day = 16
            working_days = min(
                days_back, days_back * 5 // 7
            )  # Approximate working days
            total_available_minutes = working_days * available_hours_per_day * 60

            utilization_percentage = (
                (float(total_scheduled_minutes) / total_available_minutes * 100)
                if total_available_minutes > 0
                else 0
            )
            efficiency_percentage = (
                (float(total_actual_minutes) / float(total_scheduled_minutes) * 100)
                if total_scheduled_minutes > 0
                else 0
            )

            return {
                "machine_id": str(machine_id),
                "period_days": days_back,
                "total_scheduled_minutes": int(total_scheduled_minutes),
                "total_actual_minutes": int(total_actual_minutes),
                "total_available_minutes": total_available_minutes,
                "utilization_percentage": round(utilization_percentage, 2),
                "efficiency_percentage": round(efficiency_percentage, 2),
            }
        except Exception as e:
            raise DatabaseError(
                f"Error getting machine utilization stats: {str(e)}"
            ) from e


class OperatorRepository(BaseRepository[Operator, OperatorCreate, OperatorUpdate]):
    """
    Repository implementation for Operator entities.

    Provides CRUD operations plus domain-specific queries for operators,
    including skill-based matching and availability checking.
    """

    @property
    def entity_class(self):
        """Return the Operator entity class."""
        return Operator

    def find_by_employee_id(self, employee_id: str) -> Operator | None:
        """
        Find operator by employee ID.

        Args:
            employee_id: Employee ID to search for

        Returns:
            Operator if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Operator).where(Operator.employee_id == employee_id)
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding operator by employee_id {employee_id}: {str(e)}"
            ) from e

    def find_by_zone(self, zone: str) -> list[Operator]:
        """
        Find operators in a specific zone.

        Args:
            zone: Zone name to search for

        Returns:
            List of operators in the zone

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Operator).where(Operator.zone == zone)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding operators by zone {zone}: {str(e)}"
            ) from e

    def find_available(self, at_time: datetime | None = None) -> list[Operator]:
        """
        Find operators that are available for work.

        Args:
            at_time: Time to check availability (defaults to now)

        Returns:
            List of available operators

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # First get operators with available status
            available_operators_statement = select(Operator).where(
                Operator.status == OperatorStatus.AVAILABLE
            )
            available_operators = list(
                self.session.exec(available_operators_statement).all()
            )

            if at_time is None:
                return available_operators

            # Filter out operators that have active assignments at the specified time
            truly_available = []
            for operator in available_operators:
                if self._is_operator_available_at_time(operator.id, at_time):
                    truly_available.append(operator)

            return truly_available
        except Exception as e:
            raise DatabaseError(f"Error finding available operators: {str(e)}") from e

    def find_with_skills(self, operator_id: UUID) -> Operator | None:
        """
        Find operator with skills eagerly loaded.

        Args:
            operator_id: UUID of the operator

        Returns:
            Operator with skills loaded, None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Operator)
                .options(selectinload(Operator.skills))
                .where(Operator.id == operator_id)
            )
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(f"Error finding operator with skills: {str(e)}") from e

    def find_by_skill(
        self, skill_type_id: UUID, min_level: SkillLevel = SkillLevel.LEVEL_1
    ) -> list[Operator]:
        """
        Find operators with a specific skill at minimum level.

        Args:
            skill_type_id: UUID of the skill type
            min_level: Minimum skill level required

        Returns:
            List of operators with the skill

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Operator)
                .join(OperatorSkill)
                .where(
                    and_(
                        OperatorSkill.skill_type_id == skill_type_id,
                        OperatorSkill.level >= min_level,
                        or_(
                            OperatorSkill.expiry_date.is_(None),
                            OperatorSkill.expiry_date > datetime.utcnow(),
                        ),
                    )
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding operators by skill: {str(e)}") from e

    def find_qualified_for_machine(self, machine_id: UUID) -> list[Operator]:
        """
        Find operators qualified to operate a specific machine.

        Args:
            machine_id: UUID of the machine

        Returns:
            List of qualified operators

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Get machine skill requirements
            machine_reqs_statement = select(MachineSkillRequirement).where(
                MachineSkillRequirement.machine_id == machine_id
            )
            requirements = list(self.session.exec(machine_reqs_statement).all())

            if not requirements:
                # No skill requirements, any operator can use it
                return self.get_all()

            # Find operators who meet ALL requirements
            qualified_operators = []
            all_operators = self.get_all()

            for operator in all_operators:
                operator_with_skills = self.find_with_skills(operator.id)
                if not operator_with_skills:
                    continue

                meets_all_requirements = True
                for req in requirements:
                    if not req.is_required:
                        continue  # Skip non-required skills

                    # Check if operator has this skill at required level
                    has_skill = False
                    for skill in operator_with_skills.skills:
                        if (
                            skill.skill_type_id == req.skill_type_id
                            and skill.level >= req.minimum_level
                            and (
                                not skill.expiry_date
                                or skill.expiry_date > datetime.utcnow()
                            )
                        ):
                            has_skill = True
                            break

                    if not has_skill:
                        meets_all_requirements = False
                        break

                if meets_all_requirements:
                    qualified_operators.append(operator)

            return qualified_operators
        except Exception as e:
            raise DatabaseError(
                f"Error finding operators qualified for machine: {str(e)}"
            ) from e

    def find_by_shift(self, shift_pattern: str) -> list[Operator]:
        """
        Find operators by shift pattern.

        Args:
            shift_pattern: Shift pattern to filter by

        Returns:
            List of operators with the shift pattern

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Operator).where(Operator.shift_pattern == shift_pattern)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding operators by shift {shift_pattern}: {str(e)}"
            ) from e

    def _is_operator_available_at_time(
        self, operator_id: UUID, check_time: datetime
    ) -> bool:
        """
        Check if operator is available at a specific time.

        Args:
            operator_id: UUID of the operator
            check_time: Time to check

        Returns:
            True if operator is available, False otherwise
        """
        try:
            # Check for active assignments overlapping the check time
            statement = select(OperatorAssignment).where(
                and_(
                    OperatorAssignment.operator_id == operator_id,
                    OperatorAssignment.planned_start_time <= check_time,
                    OperatorAssignment.planned_end_time > check_time,
                )
            )
            conflicting_assignments = list(self.session.exec(statement).all())
            return len(conflicting_assignments) == 0
        except Exception:
            # If we can't determine availability, assume not available for safety
            return False

    def get_workload_stats(self, operator_id: UUID, days_back: int = 30) -> dict:
        """
        Get workload statistics for an operator.

        Args:
            operator_id: UUID of the operator
            days_back: Number of days to look back

        Returns:
            Dictionary with workload statistics

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from sqlalchemy import func

            start_date = datetime.utcnow() - timedelta(days=days_back)

            # Total assigned time
            assigned_time_query = select(
                func.sum(
                    func.extract(
                        "epoch",
                        OperatorAssignment.planned_end_time
                        - OperatorAssignment.planned_start_time,
                    )
                    / 60
                )
            ).where(
                and_(
                    OperatorAssignment.operator_id == operator_id,
                    OperatorAssignment.planned_start_time >= start_date,
                )
            )
            total_assigned_minutes = self.session.exec(assigned_time_query).one() or 0

            # Total actual time
            actual_time_query = select(
                func.sum(
                    func.extract(
                        "epoch",
                        OperatorAssignment.actual_end_time
                        - OperatorAssignment.actual_start_time,
                    )
                    / 60
                )
            ).where(
                and_(
                    OperatorAssignment.operator_id == operator_id,
                    OperatorAssignment.actual_start_time >= start_date,
                    OperatorAssignment.actual_end_time.is_not(None),
                )
            )
            total_actual_minutes = self.session.exec(actual_time_query).one() or 0

            # Number of assignments
            assignment_count_query = select(func.count(OperatorAssignment.id)).where(
                and_(
                    OperatorAssignment.operator_id == operator_id,
                    OperatorAssignment.planned_start_time >= start_date,
                )
            )
            assignment_count = self.session.exec(assignment_count_query).one()

            # Available hours in the period (assuming 8 hours/day, 5 days/week)
            available_hours_per_day = 8
            working_days = min(
                days_back, days_back * 5 // 7
            )  # Approximate working days
            total_available_minutes = working_days * available_hours_per_day * 60

            utilization_percentage = (
                (float(total_assigned_minutes) / total_available_minutes * 100)
                if total_available_minutes > 0
                else 0
            )
            efficiency_percentage = (
                (float(total_actual_minutes) / float(total_assigned_minutes) * 100)
                if total_assigned_minutes > 0
                else 0
            )

            return {
                "operator_id": str(operator_id),
                "period_days": days_back,
                "total_assigned_minutes": int(total_assigned_minutes),
                "total_actual_minutes": int(total_actual_minutes),
                "total_available_minutes": total_available_minutes,
                "assignment_count": assignment_count,
                "utilization_percentage": round(utilization_percentage, 2),
                "efficiency_percentage": round(efficiency_percentage, 2),
            }
        except Exception as e:
            raise DatabaseError(
                f"Error getting operator workload stats: {str(e)}"
            ) from e


class ResourceRepository:
    """
    Combined repository for resource operations across machines and operators.

    Provides high-level resource allocation and availability queries.
    """

    def __init__(self, session: Session):
        """Initialize with database session."""
        self.session = session
        self.machine_repo = MachineRepository(session)
        self.operator_repo = OperatorRepository(session)

    def find_available_resources(
        self,
        resource_type: str,
        zone: str | None = None,
        at_time: datetime | None = None,
    ) -> dict:
        """
        Find available resources of specified type.

        Args:
            resource_type: 'machine' or 'operator' or 'all'
            zone: Optional zone filter
            at_time: Time to check availability

        Returns:
            Dictionary with available resources by type

        Raises:
            DatabaseError: If database operation fails
        """
        result = {}

        if resource_type in ["machine", "all"]:
            machines = self.machine_repo.find_available(at_time)
            if zone:
                machines = [m for m in machines if m.zone == zone]
            result["machines"] = machines

        if resource_type in ["operator", "all"]:
            operators = self.operator_repo.find_available(at_time)
            if zone:
                operators = [o for o in operators if o.zone == zone]
            result["operators"] = operators

        return result

    def get_resource_summary(self, zone: str | None = None) -> dict:
        """
        Get summary of resource availability and utilization.

        Args:
            zone: Optional zone filter

        Returns:
            Dictionary with resource summary
        """
        try:
            # Machine summary
            machine_query = select(Machine)
            if zone:
                machine_query = machine_query.where(Machine.zone == zone)
            machines = list(self.session.exec(machine_query).all())

            machine_summary = {
                "total": len(machines),
                "available": len(
                    [m for m in machines if m.status == MachineStatus.AVAILABLE]
                ),
                "busy": len([m for m in machines if m.status == MachineStatus.BUSY]),
                "maintenance": len(
                    [m for m in machines if m.status == MachineStatus.MAINTENANCE]
                ),
                "offline": len(
                    [m for m in machines if m.status == MachineStatus.OFFLINE]
                ),
            }

            # Operator summary
            operator_query = select(Operator)
            if zone:
                operator_query = operator_query.where(Operator.zone == zone)
            operators = list(self.session.exec(operator_query).all())

            operator_summary = {
                "total": len(operators),
                "available": len(
                    [o for o in operators if o.status == OperatorStatus.AVAILABLE]
                ),
                "assigned": len(
                    [o for o in operators if o.status == OperatorStatus.ASSIGNED]
                ),
                "on_break": len(
                    [o for o in operators if o.status == OperatorStatus.ON_BREAK]
                ),
                "off_shift": len(
                    [o for o in operators if o.status == OperatorStatus.OFF_SHIFT]
                ),
                "absent": len(
                    [o for o in operators if o.status == OperatorStatus.ABSENT]
                ),
            }

            return {
                "zone": zone,
                "machines": machine_summary,
                "operators": operator_summary,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            raise DatabaseError(f"Error getting resource summary: {str(e)}") from e
