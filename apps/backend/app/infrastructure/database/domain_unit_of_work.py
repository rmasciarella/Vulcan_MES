"""
Domain-aware Unit of Work implementation.

This module extends the basic Unit of Work pattern with domain event handling,
ensuring that domain events are properly collected and published when transactions
are committed.
"""

from contextlib import contextmanager
from typing import Any

from app.domain.scheduling.events.domain_events import DomainEvent
from app.infrastructure.events.domain_event_publisher import DomainEventPublisher

from .unit_of_work import SqlModelUnitOfWork, UnitOfWorkInterface


class DomainUnitOfWork(SqlModelUnitOfWork):
    """
    Unit of Work implementation with domain event support.

    Extends the base SqlModelUnitOfWork to collect domain events during
    the transaction and publish them after successful commit.
    """

    def __init__(self, session_factory: Any | None = None):
        """
        Initialize the domain-aware unit of work.

        Args:
            session_factory: Optional session factory for database connections
        """
        super().__init__(session_factory)
        self._domain_events: list[DomainEvent] = []
        self._domain_event_publisher: DomainEventPublisher | None = None

    def __enter__(self):
        """Enter the runtime context and initialize domain event handling."""
        result = super().__enter__()
        from app.infrastructure.events.domain_event_publisher import get_domain_event_publisher
        self._domain_event_publisher = get_domain_event_publisher()
        return result

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context and handle domain events appropriately."""
        try:
            # If no exception occurred, publish domain events after successful commit
            if exc_type is None:
                # Call parent __exit__ first to handle commit/rollback
                super().__exit__(exc_type, exc_val, exc_tb)
                # Publish domain events only after successful commit
                self._publish_domain_events()
            else:
                # Exception occurred, just call parent to handle rollback
                super().__exit__(exc_type, exc_val, exc_tb)
                # Clear domain events on rollback
                self._domain_events.clear()
        except Exception:
            # If commit failed, clear domain events and re-raise
            self._domain_events.clear()
            raise
        finally:
            # Cleanup
            self._domain_event_publisher = None

    def commit(self) -> None:
        """Commit the transaction and publish domain events."""
        # First commit the database transaction
        super().commit()
        
        # Only publish events after successful database commit
        self._publish_domain_events()

    def rollback(self) -> None:
        """Rollback the transaction and clear domain events."""
        super().rollback()
        self._domain_events.clear()

    def add_domain_event(self, event: DomainEvent) -> None:
        """
        Add a domain event to be published after successful transaction commit.

        Args:
            event: Domain event to publish
        """
        self._domain_events.append(event)

    def add_domain_events(self, events: list[DomainEvent]) -> None:
        """
        Add multiple domain events to be published after successful commit.

        Args:
            events: List of domain events to publish
        """
        self._domain_events.extend(events)

    def get_pending_events(self) -> list[DomainEvent]:
        """
        Get the list of pending domain events.

        Returns:
            List of domain events waiting to be published
        """
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Clear all pending domain events without publishing them."""
        self._domain_events.clear()

    def _publish_domain_events(self) -> None:
        """Publish all collected domain events."""
        if not self._domain_events or not self._domain_event_publisher:
            return

        try:
            # Publish all domain events
            self._domain_event_publisher.publish_batch(self._domain_events)
        except Exception as e:
            # Log the error but don't fail the transaction
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to publish domain events: {str(e)}")
        finally:
            # Clear events after publishing (successful or not)
            self._domain_events.clear()


class DomainUnitOfWorkManager:
    """Manager for creating domain-aware Unit of Work instances."""

    def __init__(self, session_factory: Any | None = None):
        """
        Initialize the domain unit of work manager.

        Args:
            session_factory: Optional session factory for database connections
        """
        self._session_factory = session_factory

    def create_unit_of_work(self) -> DomainUnitOfWork:
        """
        Create a new domain-aware Unit of Work instance.

        Returns:
            New domain Unit of Work instance
        """
        return DomainUnitOfWork(self._session_factory)

    @contextmanager
    def transaction(self):
        """
        Context manager for executing code within a domain-aware transaction.

        Usage:
            with domain_uow_manager.transaction() as uow:
                job = uow.jobs.find_by_id(job_id)
                job.update_status(new_status)
                
                # Add domain events
                uow.add_domain_event(JobStatusChanged(
                    job_id=job.id,
                    job_number=job.job_number,
                    old_status="planned",
                    new_status="released"
                ))

        Yields:
            Domain Unit of Work instance
        """
        uow = self.create_unit_of_work()
        with uow:
            yield uow


# Global domain unit of work manager instance
_domain_uow_manager: DomainUnitOfWorkManager | None = None


def get_domain_unit_of_work_manager() -> DomainUnitOfWorkManager:
    """
    Get the global domain Unit of Work manager instance.

    Returns:
        Domain Unit of Work manager instance
    """
    global _domain_uow_manager
    if _domain_uow_manager is None:
        _domain_uow_manager = DomainUnitOfWorkManager()
    return _domain_uow_manager


def configure_domain_unit_of_work(session_factory: Any | None = None) -> None:
    """
    Configure the global domain Unit of Work manager.

    Args:
        session_factory: Session factory for database connections
    """
    global _domain_uow_manager
    _domain_uow_manager = DomainUnitOfWorkManager(session_factory)


@contextmanager
def domain_transaction():
    """
    Convenience context manager for domain-aware database transactions.

    Usage:
        from app.infrastructure.database.domain_unit_of_work import domain_transaction

        with domain_transaction() as uow:
            job = uow.jobs.find_by_id(job_id)
            job.update_status(new_status)
            
            # Domain events are automatically collected and published
            uow.add_domain_event(JobStatusChanged(...))

    Yields:
        Domain Unit of Work instance
    """
    uow_manager = get_domain_unit_of_work_manager()
    with uow_manager.transaction() as uow:
        yield uow