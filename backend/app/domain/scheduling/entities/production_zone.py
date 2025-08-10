"""ProductionZone entity for WIP management."""

from uuid import UUID

from pydantic import Field, validator

from ...shared.base import BusinessRuleViolation, DomainEvent, Entity


class WipLimitExceeded(BusinessRuleViolation):
    """Raised when WIP limit would be exceeded."""

    def __init__(self, zone_code: str, current_wip: int, limit: int):
        super().__init__(
            "WIP_LIMIT_EXCEEDED",
            f"Zone {zone_code} would exceed WIP limit: {current_wip + 1} > {limit}",
        )


class WipChanged(DomainEvent):
    """Event raised when WIP changes in a zone."""

    zone_id: UUID
    zone_code: str
    old_wip: int
    new_wip: int
    job_id: UUID | None = None
    reason: str


class ProductionZone(Entity):
    """
    Production zone entity responsible for managing Work-In-Progress (WIP) limits.

    A production zone represents a physical or logical area where work is performed,
    with constraints on how many jobs can be in the zone simultaneously to ensure
    smooth flow and prevent bottlenecks.
    """

    zone_code: str = Field(min_length=1, max_length=20)
    zone_name: str = Field(min_length=1, max_length=100)
    wip_limit: int = Field(ge=1, description="Maximum number of jobs allowed in zone")
    current_wip: int = Field(
        ge=0, default=0, description="Current number of jobs in zone"
    )
    description: str | None = None

    # Business configuration
    is_active: bool = Field(default=True)

    @validator("zone_code")
    def validate_zone_code(cls, v):
        """Zone code should be uppercase alphanumeric."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Zone code must be alphanumeric with underscores")
        return v.upper()

    @validator("current_wip")
    def current_wip_within_limit(cls, v, values):
        """Current WIP should not exceed limit."""
        if "wip_limit" in values and v > values["wip_limit"]:
            raise ValueError("Current WIP cannot exceed WIP limit")
        return v

    def is_valid(self) -> bool:
        """Validate business rules."""
        return (
            self.wip_limit > 0
            and self.current_wip >= 0
            and self.current_wip <= self.wip_limit
            and bool(self.zone_code)
            and bool(self.zone_name)
        )

    @property
    def available_capacity(self) -> int:
        """Get available capacity in the zone."""
        return self.wip_limit - self.current_wip

    @property
    def utilization_percentage(self) -> float:
        """Get current utilization as a percentage."""
        return (self.current_wip / self.wip_limit) * 100

    @property
    def is_at_capacity(self) -> bool:
        """Check if zone is at capacity."""
        return self.current_wip >= self.wip_limit

    @property
    def is_near_capacity(self, threshold: float = 0.9) -> bool:
        """Check if zone is near capacity (default 90%)."""
        return self.utilization_percentage >= (threshold * 100)

    def can_accept_job(self) -> bool:
        """Check if zone can accept another job."""
        return self.is_active and not self.is_at_capacity

    def add_job(self, job_id: UUID) -> None:
        """
        Add a job to the zone's WIP count.

        Args:
            job_id: ID of the job being added

        Raises:
            WipLimitExceeded: If adding would exceed WIP limit
            BusinessRuleViolation: If zone is not active
        """
        if not self.is_active:
            raise BusinessRuleViolation(
                "ZONE_NOT_ACTIVE", f"Cannot add job to inactive zone {self.zone_code}"
            )

        if self.is_at_capacity:
            raise WipLimitExceeded(self.zone_code, self.current_wip, self.wip_limit)

        old_wip = self.current_wip
        self.current_wip += 1
        self.mark_updated()

        # Raise domain event
        self.add_domain_event(
            WipChanged(
                aggregate_id=self.id,
                zone_id=self.id,
                zone_code=self.zone_code,
                old_wip=old_wip,
                new_wip=self.current_wip,
                job_id=job_id,
                reason="job_added",
            )
        )

    def remove_job(self, job_id: UUID) -> None:
        """
        Remove a job from the zone's WIP count.

        Args:
            job_id: ID of the job being removed

        Raises:
            BusinessRuleViolation: If WIP count would become negative
        """
        if self.current_wip <= 0:
            raise BusinessRuleViolation(
                "WIP_UNDERFLOW",
                f"Cannot remove job from zone {self.zone_code} - WIP is already 0",
            )

        old_wip = self.current_wip
        self.current_wip -= 1
        self.mark_updated()

        # Raise domain event
        self.add_domain_event(
            WipChanged(
                aggregate_id=self.id,
                zone_id=self.id,
                zone_code=self.zone_code,
                old_wip=old_wip,
                new_wip=self.current_wip,
                job_id=job_id,
                reason="job_removed",
            )
        )

    def adjust_wip_limit(self, new_limit: int) -> None:
        """
        Adjust the WIP limit for this zone.

        Args:
            new_limit: New WIP limit

        Raises:
            BusinessRuleViolation: If new limit is less than current WIP
        """
        if new_limit < 1:
            raise BusinessRuleViolation(
                "INVALID_WIP_LIMIT", f"WIP limit must be positive, got: {new_limit}"
            )

        if new_limit < self.current_wip:
            raise BusinessRuleViolation(
                "WIP_LIMIT_TOO_LOW",
                f"Cannot set WIP limit to {new_limit} - current WIP is {self.current_wip}",
            )

        old_limit = self.wip_limit
        self.wip_limit = new_limit
        self.mark_updated()

        # Raise domain event
        self.add_domain_event(
            WipChanged(
                aggregate_id=self.id,
                zone_id=self.id,
                zone_code=self.zone_code,
                old_wip=old_limit,
                new_wip=new_limit,
                reason="limit_adjusted",
            )
        )

    def deactivate(self) -> None:
        """
        Deactivate the zone.

        Raises:
            BusinessRuleViolation: If zone still has jobs
        """
        if self.current_wip > 0:
            raise BusinessRuleViolation(
                "ZONE_HAS_JOBS",
                f"Cannot deactivate zone {self.zone_code} - still has {self.current_wip} jobs",
            )

        self.is_active = False
        self.mark_updated()

    def reactivate(self) -> None:
        """Reactivate the zone."""
        self.is_active = True
        self.mark_updated()

    def get_status_summary(self) -> dict:
        """Get a summary of zone status."""
        return {
            "zone_code": self.zone_code,
            "zone_name": self.zone_name,
            "current_wip": self.current_wip,
            "wip_limit": self.wip_limit,
            "available_capacity": self.available_capacity,
            "utilization_percentage": round(self.utilization_percentage, 1),
            "is_active": self.is_active,
            "is_at_capacity": self.is_at_capacity,
            "is_near_capacity": self.is_near_capacity,
        }

    @staticmethod
    def create(
        zone_code: str, zone_name: str, wip_limit: int, description: str | None = None
    ) -> "ProductionZone":
        """
        Factory method to create a new ProductionZone.

        Args:
            zone_code: Unique code for the zone
            zone_name: Human-readable name
            wip_limit: Maximum WIP allowed
            description: Optional description

        Returns:
            New ProductionZone instance
        """
        zone = ProductionZone(
            zone_code=zone_code,
            zone_name=zone_name,
            wip_limit=wip_limit,
            description=description,
        )
        zone.validate()
        return zone
