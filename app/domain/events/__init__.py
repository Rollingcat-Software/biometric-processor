"""Domain events for event-driven architecture.

Domain events represent something that has happened in the domain
that domain experts care about. They are immutable facts about the past.

In hexagonal architecture:
- Domain events are part of the domain layer (core business logic)
- They enable loose coupling between different parts of the system
- They support event sourcing and CQRS patterns
- They facilitate integration with external systems via event bus

Key Principles:
- Events are immutable (frozen dataclasses)
- Events are named in past tense (something that happened)
- Events contain all data needed to understand what happened
- Events should not contain behavior, only data
"""

from .base import DomainEvent, DomainEventPublisher, DomainEventHandler

__all__ = [
    "DomainEvent",
    "DomainEventPublisher",
    "DomainEventHandler",
]
