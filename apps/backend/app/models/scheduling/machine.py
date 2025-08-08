"""Machine SQLModel for production equipment and capabilities."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel

from .base import MachineAutomationLevel, MachineStatus, SkillLevel


class MachineBase(SQLModel):
    """Base machine fields."""

    machine_code: str = Field(max_length=20, unique=True, index=True)
    machine_name: str = Field(max_length=100)
    automation_level: MachineAutomationLevel = Field(
        description="Attended or unattended operation"
    )
    production_zone_id: int | None = Field(
        default=None, foreign_key="production_zones.id"
    )
    status: MachineStatus = Field(
        default=MachineStatus.AVAILABLE, description="Current machine status"
    )
    efficiency_factor: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0.1"),
        le=Decimal("2.0"),
        description="Efficiency multiplier",
    )
    is_bottleneck: bool = Field(
        default=False, description="Identified as bottleneck resource"
    )


class Machine(MachineBase, table=True):
    """
    Machine table model.

    Represents production equipment with capabilities and skill requirements.
    """

    __tablename__ = "machines"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    capabilities: list["MachineCapability"] = Relationship(
        back_populates="machine", cascade_delete=True
    )
    required_skills: list["MachineRequiredSkill"] = Relationship(
        back_populates="machine", cascade_delete=True
    )
    tasks: list["Task"] = Relationship(back_populates="assigned_machine")

    # Note: Validation logic will be implemented in business layer


class MachineCapabilityBase(SQLModel):
    """Base machine capability fields."""

    machine_id: int = Field(foreign_key="machines.id")
    operation_id: int = Field(foreign_key="operations.id")
    is_primary: bool = Field(
        default=False, description="Primary vs alternative machine"
    )
    processing_time_minutes: int = Field(gt=0, description="Processing time per unit")
    setup_time_minutes: int = Field(default=0, ge=0, description="Setup time")


class MachineCapability(MachineCapabilityBase, table=True):
    """
    MachineCapability table model.

    Represents which operations a machine can perform and the associated times.
    """

    __tablename__ = "machine_capabilities"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    machine: "Machine" = Relationship(back_populates="capabilities")


class MachineRequiredSkillBase(SQLModel):
    """Base machine required skill fields."""

    machine_id: int = Field(foreign_key="machines.id")
    skill_id: int = Field(foreign_key="skills.id")
    minimum_level: SkillLevel = Field(description="Minimum skill level required")


class MachineRequiredSkill(MachineRequiredSkillBase, table=True):
    """
    MachineRequiredSkill table model.

    Represents skills required to operate a machine.
    """

    __tablename__ = "machine_required_skills"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    machine: "Machine" = Relationship(back_populates="required_skills")


class MachineCreate(MachineBase):
    """Machine creation model."""

    pass


class MachineUpdate(SQLModel):
    """Machine update model."""

    machine_name: str | None = Field(default=None, max_length=100)
    automation_level: MachineAutomationLevel | None = Field(default=None)
    production_zone_id: int | None = Field(default=None)
    status: MachineStatus | None = Field(default=None)
    efficiency_factor: Decimal | None = Field(
        default=None, ge=Decimal("0.1"), le=Decimal("2.0")
    )
    is_bottleneck: bool | None = Field(default=None)


class MachineRead(MachineBase):
    """Machine read model."""

    id: int
    created_at: datetime
    updated_at: datetime


class MachineReadWithCapabilities(MachineRead):
    """Machine read model with capabilities and required skills."""

    capabilities: list["MachineCapabilityRead"] = []
    required_skills: list["MachineRequiredSkillRead"] = []


class MachineCapabilityCreate(MachineCapabilityBase):
    """MachineCapability creation model."""

    pass


class MachineCapabilityRead(MachineCapabilityBase):
    """MachineCapability read model."""

    id: int
    created_at: datetime


class MachineRequiredSkillCreate(MachineRequiredSkillBase):
    """MachineRequiredSkill creation model."""

    pass


class MachineRequiredSkillRead(MachineRequiredSkillBase):
    """MachineRequiredSkill read model."""

    id: int
    created_at: datetime


# Fix forward references - will be resolved by SQLModel
Task = "Task"
