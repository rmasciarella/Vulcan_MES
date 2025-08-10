"""Operator SQLModel for human resources and skills management."""

from datetime import date, datetime, time

from sqlmodel import Field, Relationship, SQLModel

from .base import OperatorStatus, SkillLevel


class OperatorBase(SQLModel):
    """Base operator fields."""

    employee_id: str = Field(max_length=20, unique=True, index=True)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    email: str | None = Field(default=None, max_length=100, unique=True)
    status: OperatorStatus = Field(
        default=OperatorStatus.AVAILABLE, description="Current operator status"
    )

    # Default work schedule
    default_shift_start: time = Field(
        default=time(7, 0), description="Default shift start time"
    )
    default_shift_end: time = Field(
        default=time(16, 0), description="Default shift end time"
    )
    lunch_start: time = Field(default=time(12, 0), description="Lunch break start time")
    lunch_duration_minutes: int = Field(
        default=30, ge=0, description="Lunch break duration"
    )

    is_active: bool = Field(default=True, description="Whether operator is active")
    department: str | None = Field(default="general", max_length=50, index=True)


class Operator(OperatorBase, table=True):
    """
    Operator table model.

    Represents human resources with skills and work schedules.
    """

    __tablename__ = "operators"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    skills: list["OperatorSkill"] = Relationship(
        back_populates="operator", cascade_delete=True
    )
    task_assignments: list["TaskOperatorAssignment"] = Relationship(
        back_populates="operator"
    )

    # Note: Validation logic will be implemented in business layer

    @property
    def full_name(self) -> str:
        """Get operator's full name."""
        return f"{self.first_name} {self.last_name}"


class OperatorSkillBase(SQLModel):
    """Base operator skill fields."""

    operator_id: int = Field(foreign_key="operators.id")
    skill_id: int = Field(foreign_key="skills.id")
    proficiency_level: SkillLevel = Field(description="Operator's skill level")
    certified_date: date | None = Field(default=None, description="Certification date")
    expiry_date: date | None = Field(
        default=None, description="Certification expiry date"
    )


class OperatorSkill(OperatorSkillBase, table=True):
    """
    OperatorSkill table model.

    Represents an operator's proficiency in a specific skill.
    """

    __tablename__ = "operator_skills"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    operator: "Operator" = Relationship(back_populates="skills")

    # Note: Validation logic will be implemented in business layer

    @property
    def is_valid(self) -> bool:
        """Check if certification is currently valid."""
        if not self.certified_date:
            return True  # No expiry requirement
        if self.expiry_date and datetime.now().date() >= self.expiry_date:
            return False
        return True

    @property
    def is_expiring_soon(self, days_ahead: int = 30) -> bool:
        """Check if certification is expiring soon."""
        if not self.expiry_date:
            return False
        days_until_expiry = (self.expiry_date - datetime.now().date()).days
        return 0 < days_until_expiry <= days_ahead


class OperatorCreate(OperatorBase):
    """Operator creation model."""

    pass


class OperatorUpdate(SQLModel):
    """Operator update model."""

    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=100)
    status: OperatorStatus | None = Field(default=None)
    default_shift_start: time | None = Field(default=None)
    default_shift_end: time | None = Field(default=None)
    lunch_start: time | None = Field(default=None)
    lunch_duration_minutes: int | None = Field(default=None, ge=0)
    is_active: bool | None = Field(default=None)


class OperatorRead(OperatorBase):
    """Operator read model."""

    id: int
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Get operator's full name."""
        return f"{self.first_name} {self.last_name}"


class OperatorReadWithSkills(OperatorRead):
    """Operator read model with skills."""

    skills: list["OperatorSkillRead"] = []


class OperatorSkillCreate(OperatorSkillBase):
    """OperatorSkill creation model."""

    pass


class OperatorSkillUpdate(SQLModel):
    """OperatorSkill update model."""

    proficiency_level: SkillLevel | None = Field(default=None)
    certified_date: date | None = Field(default=None)
    expiry_date: date | None = Field(default=None)


class OperatorSkillRead(OperatorSkillBase):
    """OperatorSkill read model."""

    id: int
    created_at: datetime
    updated_at: datetime

    @property
    def is_valid(self) -> bool:
        """Check if certification is currently valid."""
        if not self.certified_date:
            return True
        if self.expiry_date and datetime.now().date() >= self.expiry_date:
            return False
        return True


# Fix forward references - will be resolved by SQLModel
TaskOperatorAssignment = "TaskOperatorAssignment"
