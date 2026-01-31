"""MessageBus for routing and processing messages through middleware.

This module provides a middleware-based message processing pipeline that routes
InboundMessage and OutboundMessage through a chain of middleware components
(deduplication, rate limiting, audit logging, etc.) before reaching adapters.

Design Principles:
- Middleware chain: Composable processing stages
- Fail-fast: Stop processing on errors
- Adapter routing: Route messages to appropriate channel adapters
- Observability: Track message flow through the pipeline
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from agentos.communicationos.models import InboundMessage, OutboundMessage
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Status of message processing through the pipeline.

    Attributes:
        CONTINUE: Continue to next middleware
        STOP: Stop processing (message handled)
        REJECT: Reject message (duplicate, rate limited, etc.)
        ERROR: Error occurred during processing
    """
    CONTINUE = "continue"
    STOP = "stop"
    REJECT = "reject"
    ERROR = "error"


@dataclass
class ProcessingContext:
    """Context passed through the middleware chain.

    Attributes:
        message_id: Unique message identifier
        channel_id: Channel identifier
        metadata: Additional metadata accumulated during processing
        status: Current processing status
        error: Error message if status is ERROR
    """
    message_id: str
    channel_id: str
    metadata: Dict[str, Any]
    status: ProcessingStatus = ProcessingStatus.CONTINUE
    error: Optional[str] = None


class ChannelAdapter(Protocol):
    """Protocol for channel adapters that send/receive messages.

    Channel adapters must implement these methods to integrate with MessageBus.
    """

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through the channel.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        ...

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string (e.g., "whatsapp_business_001")
        """
        ...


class Middleware(ABC):
    """Abstract base class for middleware components.

    Middleware components process messages in a chain, each performing
    specific functions like deduplication, rate limiting, or logging.
    """

    @abstractmethod
    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process an inbound message.

        Args:
            message: InboundMessage to process
            context: Processing context

        Returns:
            Updated ProcessingContext
        """
        pass

    @abstractmethod
    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process an outbound message.

        Args:
            message: OutboundMessage to process
            context: Processing context

        Returns:
            Updated ProcessingContext
        """
        pass


class MessageBus:
    """Central message bus for routing and processing messages.

    The MessageBus routes messages through a middleware chain and then
    to the appropriate channel adapter. It supports both inbound (from
    external channels) and outbound (to external channels) message flows.

    Architecture:
        External Channel -> Adapter -> [Middleware Chain] -> Business Logic
        Business Logic -> [Middleware Chain] -> Adapter -> External Channel

    Example:
        >>> bus = MessageBus()
        >>> bus.add_middleware(DedupeMiddleware(store))
        >>> bus.add_middleware(RateLimitMiddleware(limiter))
        >>> bus.add_middleware(AuditMiddleware(logger))
        >>> bus.register_adapter("whatsapp_001", whatsapp_adapter)
        >>>
        >>> # Process inbound message
        >>> result = await bus.process_inbound(inbound_msg)
        >>>
        >>> # Send outbound message
        >>> success = await bus.send_outbound(outbound_msg)
    """

    def __init__(self):
        """Initialize the MessageBus."""
        self._middleware: List[Middleware] = []
        self._adapters: Dict[str, ChannelAdapter] = {}
        self._inbound_handlers: List[Callable[[InboundMessage], None]] = []

    def add_middleware(self, middleware: Middleware) -> None:
        """Add a middleware component to the processing chain.

        Middleware is executed in the order it's added.

        Args:
            middleware: Middleware component to add
        """
        self._middleware.append(middleware)
        logger.info(f"Added middleware: {middleware.__class__.__name__}")

    def register_adapter(self, channel_id: str, adapter: ChannelAdapter) -> None:
        """Register a channel adapter for routing messages.

        Args:
            channel_id: Unique channel identifier
            adapter: ChannelAdapter implementation
        """
        self._adapters[channel_id] = adapter
        logger.info(f"Registered adapter for channel: {channel_id}")

    def unregister_adapter(self, channel_id: str) -> None:
        """Unregister a channel adapter.

        Args:
            channel_id: Channel identifier to unregister
        """
        if channel_id in self._adapters:
            del self._adapters[channel_id]
            logger.info(f"Unregistered adapter for channel: {channel_id}")

    def add_inbound_handler(
        self,
        handler: Callable[[InboundMessage], None]
    ) -> None:
        """Add a handler for successfully processed inbound messages.

        Handlers are called after the message passes through all middleware.

        Args:
            handler: Callback function that receives InboundMessage
        """
        self._inbound_handlers.append(handler)

    async def process_inbound(
        self,
        message: InboundMessage
    ) -> ProcessingContext:
        """Process an inbound message through the middleware chain.

        The message flows through each middleware in order. If any middleware
        returns STOP or REJECT status, processing stops immediately.

        Args:
            message: InboundMessage from external channel

        Returns:
            ProcessingContext with final status
        """
        context = ProcessingContext(
            message_id=message.message_id,
            channel_id=message.channel_id,
            metadata={}
        )

        logger.debug(
            f"Processing inbound message: {message.message_id} "
            f"from channel: {message.channel_id}"
        )

        # Run through middleware chain
        for middleware in self._middleware:
            try:
                context = await middleware.process_inbound(message, context)

                # Stop processing if middleware signals to stop or reject
                if context.status in [ProcessingStatus.STOP, ProcessingStatus.REJECT]:
                    logger.info(
                        f"Message {message.message_id} {context.status.value} "
                        f"by {middleware.__class__.__name__}"
                    )
                    return context

                # Stop processing on error
                if context.status == ProcessingStatus.ERROR:
                    logger.error(
                        f"Error processing message {message.message_id} "
                        f"in {middleware.__class__.__name__}: {context.error}"
                    )
                    return context

            except Exception as e:
                logger.exception(
                    f"Exception in middleware {middleware.__class__.__name__} "
                    f"for message {message.message_id}"
                )
                context.status = ProcessingStatus.ERROR
                context.error = str(e)
                return context

        # All middleware passed, deliver to handlers
        for handler in self._inbound_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.exception(
                    f"Exception in inbound handler for message {message.message_id}"
                )

        logger.debug(f"Successfully processed inbound message: {message.message_id}")
        return context

    async def send_outbound(
        self,
        message: OutboundMessage
    ) -> ProcessingContext:
        """Send an outbound message through middleware and adapter.

        The message flows through each middleware before being sent to the
        appropriate channel adapter.

        Args:
            message: OutboundMessage to send

        Returns:
            ProcessingContext with final status
        """
        context = ProcessingContext(
            message_id=f"out_{message.channel_id}_{int(utc_now().timestamp())}",
            channel_id=message.channel_id,
            metadata={}
        )

        logger.debug(
            f"Sending outbound message to channel: {message.channel_id}"
        )

        # Run through middleware chain
        for middleware in self._middleware:
            try:
                context = await middleware.process_outbound(message, context)

                # Stop processing if middleware signals to stop or reject
                if context.status in [ProcessingStatus.STOP, ProcessingStatus.REJECT]:
                    logger.info(
                        f"Outbound message {context.message_id} {context.status.value} "
                        f"by {middleware.__class__.__name__}"
                    )
                    return context

                # Stop processing on error
                if context.status == ProcessingStatus.ERROR:
                    logger.error(
                        f"Error processing outbound message {context.message_id} "
                        f"in {middleware.__class__.__name__}: {context.error}"
                    )
                    return context

            except Exception as e:
                logger.exception(
                    f"Exception in middleware {middleware.__class__.__name__} "
                    f"for outbound message {context.message_id}"
                )
                context.status = ProcessingStatus.ERROR
                context.error = str(e)
                return context

        # All middleware passed, send through adapter
        adapter = self._adapters.get(message.channel_id)
        if not adapter:
            logger.error(f"No adapter registered for channel: {message.channel_id}")
            context.status = ProcessingStatus.ERROR
            context.error = f"No adapter for channel: {message.channel_id}"
            return context

        try:
            success = adapter.send_message(message)
            if not success:
                context.status = ProcessingStatus.ERROR
                context.error = "Adapter failed to send message"
            else:
                logger.debug(
                    f"Successfully sent outbound message via channel: {message.channel_id}"
                )
        except Exception as e:
            logger.exception(
                f"Exception sending message via adapter for channel: {message.channel_id}"
            )
            context.status = ProcessingStatus.ERROR
            context.error = str(e)

        return context
