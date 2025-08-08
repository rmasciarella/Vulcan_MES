"""
Domain event publisher implementation.

This module provides the infrastructure for publishing domain events from
domain entities and aggregates to the event bus.
"""

import logging
from abc import ABC, abstractmethod

from app.domain.shared.base import AggregateRoot, DomainEvent

from .event_bus import EventBusInterface, InMemoryEventBus

logger = logging.getLogger(__name__)


class EventPublisherInterface(ABC):
    """
    Abstract interface for domain event publishers.

    Defines the contract for publishing domain events from aggregates
    and managing event publishing lifecycle.
    """

    @abstractmethod
    def publish_events(self, aggregate: AggregateRoot) -> None:
        """
        Publish all pending domain events from an aggregate.

        Args:
            aggregate: Aggregate root with pending events to publish
        """
        pass

    @abstractmethod
    async def publish_events_async(self, aggregate: AggregateRoot) -> None:
        """
        Asynchronously publish all pending domain events from an aggregate.

        Args:
            aggregate: Aggregate root with pending events to publish
        """
        pass

    @abstractmethod
    def publish_event(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.

        Args:
            event: Domain event to publish
        """
        pass

    @abstractmethod
    async def publish_event_async(self, event: DomainEvent) -> None:
        """
        Asynchronously publish a single domain event.

        Args:
            event: Domain event to publish
        """
        pass


class DomainEventPublisher(EventPublisherInterface):
    """
    Domain event publisher that publishes events to an event bus.

    Handles the publishing of domain events from aggregates and provides
    both synchronous and asynchronous publishing capabilities.
    """

    def __init__(self, event_bus: EventBusInterface | None = None):
        """
        Initialize the domain event publisher.

        Args:
            event_bus: Event bus to publish events to. If None, uses default.
        """
        self._event_bus = event_bus or InMemoryEventBus()

    def publish_events(self, aggregate: AggregateRoot) -> None:
        """
        Publish all pending domain events from an aggregate synchronously.

        Args:
            aggregate: Aggregate root with pending events to publish
        """
        events = aggregate.get_domain_events()
        if not events:
            return

        logger.info(
            f"Publishing {len(events)} domain events from aggregate {type(aggregate).__name__}"
        )

        for event in events:
            try:
                self._event_bus.publish(event)
                logger.debug(f"Published event {type(event).__name__}")
            except Exception as e:
                logger.error(
                    f"Failed to publish event {type(event).__name__}: {str(e)}"
                )
                # Continue publishing other events even if one fails

        # Clear events after publishing
        aggregate.clear_domain_events()

    async def publish_events_async(self, aggregate: AggregateRoot) -> None:
        """
        Asynchronously publish all pending domain events from an aggregate.

        Args:
            aggregate: Aggregate root with pending events to publish
        """
        events = aggregate.get_domain_events()
        if not events:
            return

        logger.info(
            f"Async publishing {len(events)} domain events from aggregate {type(aggregate).__name__}"
        )

        for event in events:
            try:
                await self._event_bus.publish_async(event)
                logger.debug(f"Published event {type(event).__name__} async")
            except Exception as e:
                logger.error(
                    f"Failed to async publish event {type(event).__name__}: {str(e)}"
                )
                # Continue publishing other events even if one fails

        # Clear events after publishing
        aggregate.clear_domain_events()

    def publish_event(self, event: DomainEvent) -> None:
        """
        Publish a single domain event synchronously.

        Args:
            event: Domain event to publish
        """
        try:
            self._event_bus.publish(event)
            logger.debug(f"Published single event {type(event).__name__}")
        except Exception as e:
            logger.error(
                f"Failed to publish single event {type(event).__name__}: {str(e)}"
            )
            raise

    async def publish_event_async(self, event: DomainEvent) -> None:
        """
        Asynchronously publish a single domain event.

        Args:
            event: Domain event to publish
        """
        try:
            await self._event_bus.publish_async(event)
            logger.debug(f"Published single event {type(event).__name__} async")
        except Exception as e:
            logger.error(
                f"Failed to async publish single event {type(event).__name__}: {str(e)}"
            )
            raise

    def publish_multiple_events(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events synchronously.

        Args:
            events: List of domain events to publish
        """
        if not events:
            return

        logger.info(f"Publishing {len(events)} individual domain events")

        for event in events:
            try:
                self._event_bus.publish(event)
                logger.debug(f"Published event {type(event).__name__}")
            except Exception as e:
                logger.error(
                    f"Failed to publish event {type(event).__name__}: {str(e)}"
                )
                # Continue publishing other events even if one fails

    async def publish_multiple_events_async(self, events: list[DomainEvent]) -> None:
        """
        Asynchronously publish multiple domain events.

        Args:
            events: List of domain events to publish
        """
        if not events:
            return

        logger.info(f"Async publishing {len(events)} individual domain events")

        for event in events:
            try:
                await self._event_bus.publish_async(event)
                logger.debug(f"Published event {type(event).__name__} async")
            except Exception as e:
                logger.error(
                    f"Failed to async publish event {type(event).__name__}: {str(e)}"
                )
                # Continue publishing other events even if one fails

    def publish_aggregates_events(self, aggregates: list[AggregateRoot]) -> None:
        """
        Publish events from multiple aggregates synchronously.

        Args:
            aggregates: List of aggregates with events to publish
        """
        if not aggregates:
            return

        total_events = sum(len(agg.get_domain_events()) for agg in aggregates)
        if total_events == 0:
            return

        logger.info(
            f"Publishing events from {len(aggregates)} aggregates ({total_events} total events)"
        )

        for aggregate in aggregates:
            self.publish_events(aggregate)

    async def publish_aggregates_events_async(
        self, aggregates: list[AggregateRoot]
    ) -> None:
        """
        Asynchronously publish events from multiple aggregates.

        Args:
            aggregates: List of aggregates with events to publish
        """
        if not aggregates:
            return

        total_events = sum(len(agg.get_domain_events()) for agg in aggregates)
        if total_events == 0:
            return

        logger.info(
            f"Async publishing events from {len(aggregates)} aggregates ({total_events} total events)"
        )

        for aggregate in aggregates:
            await self.publish_events_async(aggregate)

    @property
    def event_bus(self) -> EventBusInterface:
        """
        Get the underlying event bus.

        Returns:
            Event bus instance
        """
        return self._event_bus


# Global event publisher instance
_event_publisher: DomainEventPublisher | None = None


def get_event_publisher() -> DomainEventPublisher:
    """
    Get the global event publisher instance.

    Returns:
        Domain event publisher instance
    """
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = DomainEventPublisher()
    return _event_publisher


def configure_event_publisher(event_bus: EventBusInterface | None = None) -> None:
    """
    Configure the global event publisher.

    Args:
        event_bus: Event bus to use for publishing events
    """
    global _event_publisher
    _event_publisher = DomainEventPublisher(event_bus)


# Convenience alias
EventPublisher = get_event_publisher
