"""ProductionZone SQLModel for WIP management."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ProductionZoneBase(SQLModel):
    """Base production zone fields."""

    zone_code: str = Field(max_length=20, unique=True, index=True)
    zone_name: str = Field(max_length=100)
    wip_limit: int = Field(gt=0, description="Work in progress limit")
    current_wip: int = Field(
        default=0, ge=0, description="Current work in progress count"
    )
    description: str | None = Field(default=None)


class ProductionZone(ProductionZoneBase, table=True):
    """
    ProductionZone table model.

    Represents production zones with WIP limits for lean manufacturing.
    """

    __tablename__ = "production_zones"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Note: Validation logic will be implemented in business layer


class ProductionZoneCreate(ProductionZoneBase):
    """ProductionZone creation model."""

    pass


class ProductionZoneUpdate(SQLModel):
    """ProductionZone update model."""

    zone_name: str | None = Field(default=None, max_length=100)
    wip_limit: int | None = Field(default=None, gt=0)
    current_wip: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None)


class ProductionZoneRead(ProductionZoneBase):
    """ProductionZone read model."""

    id: int
    created_at: datetime
    updated_at: datetime
