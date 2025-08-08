"""
Base repository implementation providing generic CRUD operations.

This module provides a generic base repository class that implements common
database operations using SQLModel and SQLAlchemy. Concrete repository
implementations can extend this class to provide domain-specific operations.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, SQLModel, select

from app.shared.base import DomainException

# Type variables for generic repository
EntityType = TypeVar("EntityType", bound=SQLModel)
CreateType = TypeVar("CreateType", bound=SQLModel)
UpdateType = TypeVar("UpdateType", bound=SQLModel)


class RepositoryException(DomainException):
    """Base exception for repository layer errors."""

    pass


class EntityNotFoundError(RepositoryException):
    """Raised when an entity cannot be found."""

    pass


class EntityAlreadyExistsError(RepositoryException):
    """Raised when attempting to create an entity that already exists."""

    pass


class DatabaseError(RepositoryException):
    """Raised when a database operation fails."""

    pass


class BaseRepository(Generic[EntityType, CreateType, UpdateType], ABC):
    """
    Base repository class providing generic CRUD operations.

    This abstract class defines the common interface and implementation
    for repository operations. Concrete repositories should inherit from
    this class and provide the entity_class property.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLModel database session
        """
        self.session = session

    @property
    @abstractmethod
    def entity_class(self) -> type[EntityType]:
        """Return the SQLModel entity class managed by this repository."""
        pass

    def create(self, entity_data: CreateType) -> EntityType:
        """
        Create a new entity.

        Args:
            entity_data: Data for creating the entity

        Returns:
            Created entity

        Raises:
            EntityAlreadyExistsError: If entity already exists
            DatabaseError: If database operation fails
        """
        try:
            # Convert create data to entity if needed
            if isinstance(entity_data, dict):
                entity = self.entity_class(**entity_data)
            elif isinstance(entity_data, self.entity_class):
                entity = entity_data
            else:
                # Assume it's a Pydantic model with compatible fields
                entity = self.entity_class(**entity_data.dict())

            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity

        except IntegrityError as e:
            self.session.rollback()
            raise EntityAlreadyExistsError(f"Entity already exists: {str(e)}") from e
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during create: {str(e)}") from e

    def get_by_id(self, entity_id: UUID) -> EntityType | None:
        """
        Get entity by ID.

        Args:
            entity_id: UUID of the entity

        Returns:
            Entity if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(self.entity_class).where(
                self.entity_class.id == entity_id
            )
            return self.session.exec(statement).first()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database error during get_by_id: {str(e)}") from e

    def get_by_id_required(self, entity_id: UUID) -> EntityType:
        """
        Get entity by ID, raising exception if not found.

        Args:
            entity_id: UUID of the entity

        Returns:
            Entity

        Raises:
            EntityNotFoundError: If entity not found
            DatabaseError: If database operation fails
        """
        entity = self.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError(
                f"{self.entity_class.__name__} with ID {entity_id} not found"
            )
        return entity

    def get_all(self, limit: int | None = None, offset: int = 0) -> list[EntityType]:
        """
        Get all entities with optional pagination.

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of entities

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(self.entity_class).offset(offset)
            if limit:
                statement = statement.limit(limit)
            return list(self.session.exec(statement).all())
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database error during get_all: {str(e)}") from e

    def count(self) -> int:
        """
        Get total count of entities.

        Returns:
            Total number of entities

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(self.entity_class)
            return len(list(self.session.exec(statement).all()))
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database error during count: {str(e)}") from e

    def update(self, entity_id: UUID, update_data: UpdateType) -> EntityType:
        """
        Update an existing entity.

        Args:
            entity_id: UUID of the entity to update
            update_data: Data to update

        Returns:
            Updated entity

        Raises:
            EntityNotFoundError: If entity not found
            DatabaseError: If database operation fails
        """
        try:
            entity = self.get_by_id_required(entity_id)

            # Update entity with new data
            update_dict = (
                update_data.dict(exclude_unset=True)
                if hasattr(update_data, "dict")
                else update_data
            )
            for field, value in update_dict.items():
                if hasattr(entity, field):
                    setattr(entity, field, value)

            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity

        except EntityNotFoundError:
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during update: {str(e)}") from e

    def delete(self, entity_id: UUID) -> bool:
        """
        Delete an entity by ID.

        Args:
            entity_id: UUID of the entity to delete

        Returns:
            True if entity was deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            entity = self.get_by_id(entity_id)
            if not entity:
                return False

            self.session.delete(entity)
            self.session.commit()
            return True

        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during delete: {str(e)}") from e

    def exists(self, entity_id: UUID) -> bool:
        """
        Check if entity exists by ID.

        Args:
            entity_id: UUID of the entity

        Returns:
            True if entity exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        return self.get_by_id(entity_id) is not None

    def save(self, entity: EntityType) -> EntityType:
        """
        Save or update an entity.

        Args:
            entity: Entity to save

        Returns:
            Saved entity

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during save: {str(e)}") from e

    def bulk_create(self, entities: list[CreateType]) -> list[EntityType]:
        """
        Create multiple entities in a single transaction.

        Args:
            entities: List of entity data to create

        Returns:
            List of created entities

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            created_entities = []
            for entity_data in entities:
                if isinstance(entity_data, dict):
                    entity = self.entity_class(**entity_data)
                elif isinstance(entity_data, self.entity_class):
                    entity = entity_data
                else:
                    entity = self.entity_class(**entity_data.dict())

                self.session.add(entity)
                created_entities.append(entity)

            self.session.commit()

            # Refresh all entities
            for entity in created_entities:
                self.session.refresh(entity)

            return created_entities

        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during bulk_create: {str(e)}") from e

    def bulk_delete(self, entity_ids: list[UUID]) -> int:
        """
        Delete multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs to delete

        Returns:
            Number of entities deleted

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(self.entity_class).where(
                self.entity_class.id.in_(entity_ids)
            )
            entities = list(self.session.exec(statement).all())

            deleted_count = len(entities)
            for entity in entities:
                self.session.delete(entity)

            self.session.commit()
            return deleted_count

        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseError(f"Database error during bulk_delete: {str(e)}") from e
