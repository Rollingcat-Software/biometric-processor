"""Command pattern implementation for CQRS.

This module provides base classes and infrastructure for implementing
the Command pattern, which is a key part of CQRS (Command Query Responsibility Segregation).

Commands represent actions that change state in the system.
Queries represent actions that read state without changing it.

Following hexagonal architecture principles:
- Commands are part of the Application layer
- They orchestrate domain logic without containing it
- They depend on domain interfaces (ports)
- Infrastructure adapters implement these interfaces
"""

from .base import Command, CommandHandler, CommandBus

__all__ = [
    "Command",
    "CommandHandler",
    "CommandBus",
]
