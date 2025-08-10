"""
Domain Event Publisher Implementation.

This module provides the concrete implementation for publishing domain events
from the scheduling domain to the infrastructure event bus.
"""

import asyncio
import logging
from typing import Any

from app.domain.scheduling.events.domain_events import DomainEvent, DomainEventDispatcher
from app.infrastructure.events.event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)


class DomainEventPublisher:
    """
    Publisher for domain events that bridges domain and infrastructure.

    This publisher takes domain events from the scheduling domain and publishes
    them through the infrastructure event bus system for broader application
    consumption.
    """

    def __init__(self, event_bus: InMemoryEventBus):
        """
        Initialize the domain event publisher.

        Args:
            event_bus: Infrastructure event bus for publishing events
        """
        self._event_bus = event_bus
        self._domain_dispatcher = DomainEventDispatcher()
        self._setup_domain_handlers()

    def _setup_domain_handlers(self) -> None:
        """Setup handlers to bridge domain events to infrastructure event bus."""
        # Register a handler that forwards all domain events to the infrastructure bus
        self._domain_dispatcher.register_handler(InfrastructureBridgeHandler(self._event_bus))

    def publish_domain_event(self, event: DomainEvent) -> None:
        """
        Publish a domain event synchronously.

        Args:
            event: Domain event to publish
        """
        try:
            # Dispatch through domain dispatcher first (for domain-specific handlers)
            self._domain_dispatcher.dispatch(event)
            
            logger.debug(f"Published domain event: {type(event).__name__}")
        except Exception as e:
            logger.error(f"Error publishing domain event {type(event).__name__}: {str(e)}")
            raise

    async def publish_domain_event_async(self, event: DomainEvent) -> None:
        """
        Publish a domain event asynchronously.

        Args:
            event: Domain event to publish
        """
        try:
            # Dispatch through domain dispatcher first (for domain-specific handlers)
            self._domain_dispatcher.dispatch(event)
            
            # Also publish through infrastructure event bus asynchronously
            await self._event_bus.publish_async(event)
            
            logger.debug(f"Published domain event async: {type(event).__name__}")
        except Exception as e:
            logger.error(f"Error publishing domain event async {type(event).__name__}: {str(e)}")
            raise

    def publish_batch(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events as a batch.

        Args:
            events: List of domain events to publish
        """
        try:
            for event in events:
                self.publish_domain_event(event)
            logger.debug(f"Published batch of {len(events)} domain events")
        except Exception as e:
            logger.error(f"Error publishing batch of domain events: {str(e)}")
            raise

    async def publish_batch_async(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events asynchronously as a batch.

        Args:
            events: List of domain events to publish
        """
        try:
            tasks = [self.publish_domain_event_async(event) for event in events]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Published batch of {len(events)} domain events async")
        except Exception as e:
            logger.error(f"Error publishing batch of domain events async: {str(e)}")
            raise

    def register_domain_handler(self, handler: Any) -> None:
        """
        Register a handler for domain events.

        Args:
            handler: Domain event handler to register
        """
        self._domain_dispatcher.register_handler(handler)

    def register_infrastructure_handler(
        self, event_type: type[DomainEvent], handler: Any
    ) -> None:
        """
        Register a handler for events in the infrastructure event bus.

        Args:
            event_type: Type of event to handle
            handler: Handler function or coroutine
        """
        if asyncio.iscoroutinefunction(handler):
            self._event_bus.subscribe_async(event_type, handler)
        else:
            self._event_bus.subscribe(event_type, handler)

    def get_event_history(self, event_type: type[DomainEvent] | None = None) -> list[DomainEvent]:
        """
        Get history of published events from infrastructure bus.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of published events
        """
        return self._event_bus.get_event_history(event_type)


class InfrastructureBridgeHandler:
    """Handler that bridges domain events to infrastructure event bus."""

    def __init__(self, event_bus: InMemoryEventBus):
        """Initialize with event bus."""
        self._event_bus = event_bus

    def can_handle(self, event: DomainEvent) -> bool:
        """Can handle any domain event."""
        return True

    def handle(self, event: DomainEvent) -> None:
        """Forward domain event to infrastructure event bus."""
        try:
            self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"Error forwarding domain event to infrastructure: {str(e)}")


# Global domain event publisher instance
_domain_event_publisher: DomainEventPublisher | None = None


def get_domain_event_publisher() -> DomainEventPublisher:
    """
    Get the global domain event publisher instance.

    Returns:
        Domain event publisher singleton
    """
    global _domain_event_publisher
    if _domain_event_publisher is None:
        from app.infrastructure.events.event_bus import EventBus
        _domain_event_publisher = DomainEventPublisher(EventBus())
    return _domain_event_publisher


def publish_domain_event(event: DomainEvent) -> None:
    """
    Convenience function to publish a domain event.

    Args:
        event: Domain event to publish
    """
    publisher = get_domain_event_publisher()
    publisher.publish_domain_event(event)


async def publish_domain_event_async(event: DomainEvent) -> None:
    """
    Convenience function to publish a domain event asynchronously.

    Args:
        event: Domain event to publish
    """
    publisher = get_domain_event_publisher()
    await publisher.publish_domain_event_async(event)


def publish_domain_events(events: list[DomainEvent]) -> None:
    """
    Convenience function to publish multiple domain events.

    Args:
        events: List of domain events to publish
    """
    publisher = get_domain_event_publisher()
    publisher.publish_batch(events)


async def publish_domain_events_async(events: list[DomainEvent]) -> None:
    """
    Convenience function to publish multiple domain events asynchronously.

    Args:
        events: List of domain events to publish
    """
    publisher = get_domain_event_publisher()
    await publisher.publish_batch_async(events)