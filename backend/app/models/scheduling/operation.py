"""Operation SQLModel for standard manufacturing operations."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class OperationBase(SQLModel):
    """Base operation fields."""

    operation_code: str = Field(max_length=20, unique=True, index=True)
    operation_name: str = Field(max_length=100)
    sequence_number: int = Field(ge=1, le=100, description="Operation sequence (1-100)")
    production_zone_id: int | None = Field(
        default=None, foreign_key="production_zones.id"
    )
    is_critical: bool = Field(default=False, description="Part of critical sequence")
    standard_duration_minutes: int = Field(gt=0, description="Standard processing time")
    setup_duration_minutes: int = Field(default=0, ge=0, description="Setup time")
    description: str | None = Field(default=None)


class Operation(OperationBase, table=True):
    """
    Operation table model.

    Represents standard manufacturing operations in the 100-step sequence.
    """

    __tablename__ = "operations"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Note: Validation logic will be implemented in business layer


class OperationCreate(OperationBase):
    """Operation creation model."""

    pass


class OperationUpdate(SQLModel):
    """Operation update model."""

    operation_name: str | None = Field(default=None, max_length=100)
    production_zone_id: int | None = Field(default=None)
    is_critical: bool | None = Field(default=None)
    standard_duration_minutes: int | None = Field(default=None, gt=0)
    setup_duration_minutes: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None)


class OperationRead(OperationBase):
    """Operation read model."""

    id: int
    created_at: datetime
    updated_at: datetime
