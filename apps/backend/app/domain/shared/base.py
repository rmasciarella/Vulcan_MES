"""Base classes for domain entities and value objects."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ValueObject(BaseModel):
    """Base class for value objects (immutable, defined by their values)."""

    class Config:
        frozen = True  # Makes the value object immutable
        arbitrary_types_allowed = True

    def __eq__(self, other: Any) -> bool:
        """Value objects are equal if all their attributes are equal."""
        if not isinstance(other, self.__class__):
            return False
        return self.dict() == other.dict()

    def __hash__(self) -> int:
        """Value objects with same values have same hash."""
        return hash(tuple(sorted(self.dict().items())))


class Entity(BaseModel, ABC):
    """Base class for entities (have identity, can change over time)."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

    def __eq__(self, other: Any) -> bool:
        """Entities are equal if they have the same ID and type."""
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity ID."""
        return hash(self.id)

    def mark_updated(self) -> None:
        """Mark the entity as updated."""
        self.updated_at = datetime.utcnow()

    @abstractmethod
    def is_valid(self) -> bool:
        """Validate business rules for this entity."""
        pass

    def validate(self) -> None:
        """Validate the entity and raise exception if invalid."""
        if not self.is_valid():
            raise ValueError(
                f"Entity {self.__class__.__name__} with ID {self.id} is invalid"
            )


class AggregateRoot(Entity, ABC):
    """Base class for aggregate roots (entities that control consistency boundaries)."""

    def __init__(self, **data):
        super().__init__(**data)
        self._domain_events: list[DomainEvent] = []

    def add_domain_event(self, event: "DomainEvent") -> None:
        """Add a domain event to be published."""
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        """Clear all domain events (typically after publishing)."""
        self._domain_events.clear()

    def get_domain_events(self) -> list["DomainEvent"]:
        """Get all pending domain events."""
        return self._domain_events.copy()


class DomainEvent(BaseModel):
    """Base class for domain events."""

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    aggregate_id: UUID
    event_version: int = 1

    class Config:
        arbitrary_types_allowed = True


EntityT = TypeVar("EntityT", bound=Entity)


class Repository(ABC):
    """Base repository interface for persistence."""

    @abstractmethod
    async def save(self, entity: EntityT) -> EntityT:
        """Save an entity."""
        pass

    @abstractmethod
    async def find_by_id(self, entity_id: UUID) -> EntityT | None:
        """Find an entity by its ID."""
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity by its ID."""
        pass


class DomainService(ABC):
    """Base class for domain services (business logic that doesn't belong to a single entity)."""

    pass


class DomainException(Exception):
    """Base exception for domain-specific errors."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message


class BusinessRuleViolation(DomainException):
    """Exception raised when a business rule is violated."""

    def __init__(self, rule_name: str, message: str):
        super().__init__(
            f"Business rule '{rule_name}' violated: {message}",
            code="BUSINESS_RULE_VIOLATION",
        )
        self.rule_name = rule_name
