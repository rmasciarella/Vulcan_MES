"""
Event bus implementation for domain event publishing and subscription.

The event bus provides a central mechanism for publishing domain events
and routing them to registered event handlers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.domain.shared.base import DomainEvent

logger = logging.getLogger(__name__)


class EventBusInterface(ABC):
    """
    Abstract interface for event bus implementations.

    Defines the contract for publishing events and subscribing to event types.
    """

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to all registered handlers.

        Args:
            event: Domain event to publish
        """
        pass

    @abstractmethod
    async def publish_async(self, event: DomainEvent) -> None:
        """
        Asynchronously publish a domain event to all registered handlers.

        Args:
            event: Domain event to publish
        """
        pass

    @abstractmethod
    def subscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Subscribe a handler to a specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call when event is published
        """
        pass

    @abstractmethod
    def unsubscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Unsubscribe a handler from a specific event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        pass

    @abstractmethod
    def clear_handlers(self, event_type: type[DomainEvent] | None = None) -> None:
        """
        Clear event handlers.

        Args:
            event_type: Optional event type to clear handlers for. If None, clears all.
        """
        pass


class InMemoryEventBus(EventBusInterface):
    """
    In-memory implementation of event bus.

    Provides synchronous and asynchronous event publishing with support for
    multiple handlers per event type. Events are processed in the order they
    are published.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize the event bus.

        Args:
            max_workers: Maximum number of worker threads for async processing
        """
        self._handlers: dict[type[DomainEvent], list[Callable]] = defaultdict(list)
        self._async_handlers: dict[type[DomainEvent], list[Callable]] = defaultdict(
            list
        )
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._event_history: list[DomainEvent] = []
        self._max_history_size = 1000

    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event synchronously to all registered handlers.

        Args:
            event: Domain event to publish
        """
        self._add_to_history(event)

        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug(
                f"No handlers registered for event type: {event_type.__name__}"
            )
            return

        logger.info(
            f"Publishing event {event_type.__name__} to {len(handlers)} handlers"
        )

        for handler in handlers:
            try:
                handler(event)
                logger.debug(
                    f"Successfully handled event {event_type.__name__} with {handler}"
                )
            except Exception as e:
                logger.error(
                    f"Error handling event {event_type.__name__} with {handler}: {str(e)}"
                )
                # Continue with other handlers even if one fails

    async def publish_async(self, event: DomainEvent) -> None:
        """
        Asynchronously publish a domain event to all registered handlers.

        Args:
            event: Domain event to publish
        """
        self._add_to_history(event)

        event_type = type(event)
        sync_handlers = self._handlers.get(event_type, [])
        async_handlers = self._async_handlers.get(event_type, [])

        if not sync_handlers and not async_handlers:
            logger.debug(
                f"No handlers registered for event type: {event_type.__name__}"
            )
            return

        logger.info(
            f"Publishing event {event_type.__name__} to {len(sync_handlers + async_handlers)} handlers"
        )

        # Execute synchronous handlers in thread pool
        if sync_handlers:
            loop = asyncio.get_event_loop()
            sync_tasks = [
                loop.run_in_executor(
                    self._executor, self._safe_handle_sync, handler, event
                )
                for handler in sync_handlers
            ]
            await asyncio.gather(*sync_tasks, return_exceptions=True)

        # Execute asynchronous handlers directly
        if async_handlers:
            async_tasks = [
                self._safe_handle_async(handler, event) for handler in async_handlers
            ]
            await asyncio.gather(*async_tasks, return_exceptions=True)

    def subscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Subscribe a synchronous handler to a specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call when event is published
        """
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.info(
                f"Subscribed handler {handler} to event type {event_type.__name__}"
            )
        else:
            logger.warning(
                f"Handler {handler} already subscribed to event type {event_type.__name__}"
            )

    def subscribe_async(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], Any]
    ) -> None:
        """
        Subscribe an asynchronous handler to a specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async handler function to call when event is published
        """
        if handler not in self._async_handlers[event_type]:
            self._async_handlers[event_type].append(handler)
            logger.info(
                f"Subscribed async handler {handler} to event type {event_type.__name__}"
            )
        else:
            logger.warning(
                f"Async handler {handler} already subscribed to event type {event_type.__name__}"
            )

    def unsubscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Unsubscribe a handler from a specific event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.info(
                f"Unsubscribed handler {handler} from event type {event_type.__name__}"
            )
        elif handler in self._async_handlers[event_type]:
            self._async_handlers[event_type].remove(handler)
            logger.info(
                f"Unsubscribed async handler {handler} from event type {event_type.__name__}"
            )
        else:
            logger.warning(
                f"Handler {handler} not found for event type {event_type.__name__}"
            )

    def clear_handlers(self, event_type: type[DomainEvent] | None = None) -> None:
        """
        Clear event handlers.

        Args:
            event_type: Optional event type to clear handlers for. If None, clears all.
        """
        if event_type:
            if event_type in self._handlers:
                del self._handlers[event_type]
            if event_type in self._async_handlers:
                del self._async_handlers[event_type]
            logger.info(f"Cleared handlers for event type {event_type.__name__}")
        else:
            self._handlers.clear()
            self._async_handlers.clear()
            logger.info("Cleared all event handlers")

    def get_handler_count(self, event_type: type[DomainEvent]) -> int:
        """
        Get the number of handlers registered for an event type.

        Args:
            event_type: Event type to check

        Returns:
            Total number of handlers (sync + async)
        """
        sync_count = len(self._handlers.get(event_type, []))
        async_count = len(self._async_handlers.get(event_type, []))
        return sync_count + async_count

    def get_event_history(
        self, event_type: type[DomainEvent] | None = None
    ) -> list[DomainEvent]:
        """
        Get history of published events.

        Args:
            event_type: Optional event type to filter by

        Returns:
            List of published events
        """
        if event_type:
            return [event for event in self._event_history if type(event) == event_type]
        return self._event_history.copy()

    def clear_event_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()
        logger.info("Cleared event history")

    def _add_to_history(self, event: DomainEvent) -> None:
        """Add event to history, maintaining size limit."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)  # Remove oldest event

    def _safe_handle_sync(self, handler: Callable, event: DomainEvent) -> None:
        """Safely execute a synchronous handler."""
        try:
            handler(event)
            logger.debug(
                f"Successfully handled event {type(event).__name__} with {handler}"
            )
        except Exception as e:
            logger.error(
                f"Error handling event {type(event).__name__} with {handler}: {str(e)}"
            )

    async def _safe_handle_async(self, handler: Callable, event: DomainEvent) -> None:
        """Safely execute an asynchronous handler."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
            logger.debug(
                f"Successfully handled event {type(event).__name__} with {handler}"
            )
        except Exception as e:
            logger.error(
                f"Error handling event {type(event).__name__} with {handler}: {str(e)}"
            )

    def __del__(self):
        """Cleanup resources when the event bus is destroyed."""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)


# Global event bus instance
EventBus = InMemoryEventBus
