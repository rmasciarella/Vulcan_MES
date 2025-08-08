"""Operator entity for human resources and skills management."""

from datetime import date, datetime, timedelta
from uuid import UUID

from pydantic import Field, validator

from ...shared.base import BusinessRuleViolation, DomainEvent, Entity
from ...shared.validation import (
    DataSanitizer,
    ValidationError,
)
from ..value_objects.common import ContactInfo, OperatorSkill, WorkingHours
from ..value_objects.enums import OperatorStatus


class OperatorStatusChanged(DomainEvent):
    """Event raised when operator status changes."""

    operator_id: UUID
    employee_id: str
    old_status: OperatorStatus
    new_status: OperatorStatus
    reason: str | None = None


class SkillCertificationExpiring(DomainEvent):
    """Event raised when operator skill certification is expiring soon."""

    operator_id: UUID
    employee_id: str
    skill_code: str
    expiry_date: datetime
    days_until_expiry: int


class Operator(Entity):
    """
    Operator entity representing human resources in the production system.

    Operators have skills with proficiency levels, work schedules, and availability.
    They can be assigned to tasks that match their capabilities and schedule.
    """

    employee_id: str = Field(min_length=1, max_length=20)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)

    @validator("first_name")
    def sanitize_first_name(cls, v):
        """Sanitize first name input."""
        try:
            return DataSanitizer.sanitize_string(v, max_length=50, allow_empty=False)
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("last_name")
    def sanitize_last_name(cls, v):
        """Sanitize last name input."""
        try:
            return DataSanitizer.sanitize_string(v, max_length=50, allow_empty=False)
        except ValidationError as e:
            raise ValueError(e.message)

    contact_info: ContactInfo | None = None
    status: OperatorStatus = Field(default=OperatorStatus.AVAILABLE)

    # Organizational grouping
    department: str = Field(default="general", min_length=1, max_length=50)

    # Work schedule
    default_working_hours: WorkingHours = Field(default_factory=WorkingHours)

    # Skills (managed as collection)
    _skills: dict[str, OperatorSkill] = Field(default_factory=dict)

    # Availability overrides (date -> availability info)
    _availability_overrides: dict[date, "AvailabilityOverride"] = Field(
        default_factory=dict
    )

    # Configuration
    is_active: bool = Field(default=True)
    hire_date: date | None = None

    @validator("employee_id")
    def validate_employee_id(cls, v):
        """Employee ID should be alphanumeric."""
        try:
            return DataSanitizer.sanitize_code(v, r"^[A-Z0-9_-]+$")
        except ValidationError as e:
            raise ValueError(e.message)

    def is_valid(self) -> bool:
        """Validate business rules."""
        return bool(self.employee_id) and bool(self.first_name) and bool(self.last_name)

    @property
    def full_name(self) -> str:
        """Get operator's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_available_for_work(self) -> bool:
        """Check if operator is available for scheduling work."""
        return (
            self.is_active
            and self.status.is_available_for_work
            and self.status.is_present
        )

    @property
    def skill_count(self) -> int:
        """Get number of skills this operator has."""
        return len([skill for skill in self._skills.values() if skill.is_valid])

    @property
    def active_skills(self) -> list[OperatorSkill]:
        """Get list of active (non-expired) skills."""
        return [skill for skill in self._skills.values() if skill.is_valid]

    @property
    def expiring_skills(self) -> list[OperatorSkill]:
        """Get list of skills that are expiring soon."""
        return [skill for skill in self._skills.values() if skill.is_expiring_soon]

    def has_skill(self, skill_code: str) -> bool:
        """
        Check if operator has a specific skill.

        Args:
            skill_code: Code of the skill to check

        Returns:
            True if operator has the skill and it's valid
        """
        skill = self._skills.get(skill_code)
        return skill is not None and skill.is_valid

    def get_skill(self, skill_code: str) -> OperatorSkill | None:
        """Get operator's skill by code."""
        return self._skills.get(skill_code)

    def add_skill(self, skill: OperatorSkill) -> None:
        """
        Add a skill to the operator.

        Args:
            skill: Operator skill to add

        Raises:
            BusinessRuleViolation: If skill already exists
        """
        if skill.skill.skill_code in self._skills:
            raise BusinessRuleViolation(
                "DUPLICATE_SKILL",
                f"Operator {self.employee_id} already has skill {skill.skill.skill_code}",
            )

        self._skills[skill.skill.skill_code] = skill
        self.mark_updated()

    def update_skill(self, skill: OperatorSkill) -> None:
        """
        Update an existing skill.

        Args:
            skill: Updated operator skill

        Raises:
            BusinessRuleViolation: If skill doesn't exist
        """
        if skill.skill.skill_code not in self._skills:
            raise BusinessRuleViolation(
                "SKILL_NOT_FOUND",
                f"Operator {self.employee_id} doesn't have skill {skill.skill.skill_code}",
            )

        self._skills[skill.skill.skill_code] = skill
        self.mark_updated()

    def remove_skill(self, skill_code: str) -> None:
        """
        Remove a skill from the operator.

        Args:
            skill_code: Code of the skill to remove
        """
        if skill_code in self._skills:
            del self._skills[skill_code]
            self.mark_updated()

    def is_available_during(self, start_time: datetime, end_time: datetime) -> bool:
        """
        Check if operator is available during a specific time window.

        Args:
            start_time: Start of the time window
            end_time: End of the time window

        Returns:
            True if available during the entire window
        """
        if not self.is_available_for_work:
            return False

        # Check each date in the range
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            if not self._is_available_on_date(current_date, start_time, end_time):
                return False
            current_date += timedelta(days=1)

        return True

    def _is_available_on_date(
        self, check_date: date, start_time: datetime, end_time: datetime
    ) -> bool:
        """Check if operator is available on a specific date."""
        # Get working hours for this date (override or default)
        availability = self._availability_overrides.get(check_date)
        if availability and not availability.is_available:
            return False

        working_hours = (
            availability.working_hours
            if availability and availability.working_hours
            else self.default_working_hours
        )

        # Check if requested time falls within working hours
        if check_date == start_time.date():
            if start_time.time() < working_hours.start_time:
                return False

        if check_date == end_time.date():
            if end_time.time() > working_hours.end_time:
                return False

        return True

    def set_availability_override(
        self,
        override_date: date,
        is_available: bool = True,
        working_hours: WorkingHours | None = None,
        reason: str | None = None,
    ) -> None:
        """
        Set availability override for a specific date.

        Args:
            override_date: Date to override
            is_available: Whether operator is available
            working_hours: Custom working hours for the date
            reason: Reason for override (e.g., vacation, training)
        """
        override = AvailabilityOverride(
            date=override_date,
            is_available=is_available,
            working_hours=working_hours,
            reason=reason,
        )

        self._availability_overrides[override_date] = override
        self.mark_updated()

    def remove_availability_override(self, override_date: date) -> None:
        """Remove availability override for a specific date."""
        if override_date in self._availability_overrides:
            del self._availability_overrides[override_date]
            self.mark_updated()

    def get_availability_for_date(self, check_date: date) -> "AvailabilityInfo":
        """Get availability information for a specific date."""
        override = self._availability_overrides.get(check_date)

        if override:
            return AvailabilityInfo(
                date=check_date,
                is_available=override.is_available,
                working_hours=override.working_hours or self.default_working_hours,
                reason=override.reason,
                is_override=True,
            )

        return AvailabilityInfo(
            date=check_date,
            is_available=self.is_available_for_work,
            working_hours=self.default_working_hours,
            is_override=False,
        )

    def change_status(
        self, new_status: OperatorStatus, reason: str | None = None
    ) -> None:
        """
        Change operator status with domain event.

        Args:
            new_status: New operator status
            reason: Optional reason for status change
        """
        if new_status == self.status:
            return  # No change needed

        old_status = self.status
        self.status = new_status
        self.mark_updated()

        # Raise domain event
        self.add_domain_event(
            OperatorStatusChanged(
                aggregate_id=self.id,
                operator_id=self.id,
                employee_id=self.employee_id,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
            )
        )

    def check_skill_expirations(self) -> None:
        """Check for expiring skills and raise events."""
        for skill in self.expiring_skills:
            if skill.expiry_date:
                days_until_expiry = (
                    skill.expiry_date.date() - datetime.utcnow().date()
                ).days

                self.add_domain_event(
                    SkillCertificationExpiring(
                        aggregate_id=self.id,
                        operator_id=self.id,
                        employee_id=self.employee_id,
                        skill_code=skill.skill.skill_code,
                        expiry_date=skill.expiry_date,
                        days_until_expiry=days_until_expiry,
                    )
                )

    def update_working_hours(self, new_working_hours: WorkingHours) -> None:
        """Update default working hours."""
        self.default_working_hours = new_working_hours
        self.mark_updated()

    def deactivate(self, reason: str | None = None) -> None:
        """
        Deactivate the operator.

        Args:
            reason: Optional reason for deactivation
        """
        if self.is_active:
            self.is_active = False
            self.change_status(OperatorStatus.ABSENT, reason or "deactivated")

    def reactivate(self) -> None:
        """Reactivate the operator."""
        if not self.is_active:
            self.is_active = True
            self.change_status(OperatorStatus.AVAILABLE, "reactivated")

    def get_operator_summary(self) -> dict:
        """Get operator information summary."""
        return {
            "employee_id": self.employee_id,
            "full_name": self.full_name,
            "status": self.status.value,
            "is_active": self.is_active,
            "skill_count": self.skill_count,
            "active_skills": len(self.active_skills),
            "expiring_skills": len(self.expiring_skills),
            "default_shift": f"{self.default_working_hours.start_time} - {self.default_working_hours.end_time}",
            "is_available_for_work": self.is_available_for_work,
            "availability_overrides": len(self._availability_overrides),
        }

    @staticmethod
    def create(
        employee_id: str,
        first_name: str,
        last_name: str,
        working_hours: WorkingHours | None = None,
        contact_info: ContactInfo | None = None,
        hire_date: date | None = None,
    ) -> "Operator":
        """
        Factory method to create a new Operator.

        Args:
            employee_id: Unique employee identifier
            first_name: Operator's first name
            last_name: Operator's last name
            working_hours: Custom working hours (defaults to standard)
            contact_info: Contact information
            hire_date: Date of hire

        Returns:
            New Operator instance
        """
        operator = Operator(
            employee_id=employee_id,
            first_name=first_name,
            last_name=last_name,
            default_working_hours=working_hours or WorkingHours(),
            contact_info=contact_info,
            hire_date=hire_date,
        )
        operator.validate()
        return operator


class AvailabilityOverride(Entity):
    """Represents an availability override for a specific date."""

    date: date
    is_available: bool = True
    working_hours: WorkingHours | None = None
    reason: str | None = None

    def is_valid(self) -> bool:
        """Validate business rules."""
        return True  # Simple override, always valid


class AvailabilityInfo(Entity):
    """Represents availability information for a specific date."""

    date: date
    is_available: bool
    working_hours: WorkingHours
    reason: str | None = None
    is_override: bool = False

    def is_valid(self) -> bool:
        """Validate business rules."""
        return True  # Information object, always valid
