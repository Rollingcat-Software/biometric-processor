"""Base classes for Command pattern implementation.

This module provides the foundational abstractions for implementing CQRS:
- Command: Represents an action that changes system state
- CommandHandler: Processes commands and executes business logic
- CommandBus: Routes commands to their handlers

Design Patterns Used:
- Command Pattern: Encapsulates requests as objects
- Strategy Pattern: Different handlers for different commands
- Mediator Pattern: CommandBus mediates between commands and handlers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, Optional, Type, TypeVar

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Command(ABC):
    """Base class for all commands.

    Commands are immutable objects that represent an action to be performed.
    They contain all the data needed to execute the action.

    Design Principles:
    - Immutable (frozen dataclass): Commands should not change once created
    - Self-documenting: Command name describes the action
    - Data-only: No business logic, just data and metadata

    Example:
        @dataclass(frozen=True)
        class EnrollFaceCommand(Command):
            user_id: str
            image_path: str
            tenant_id: Optional[str] = None
    """

    def get_command_name(self) -> str:
        """Get the name of this command.

        Returns:
            Command class name
        """
        return self.__class__.__name__


TCommand = TypeVar('TCommand', bound=Command)
TResult = TypeVar('TResult')


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Base class for command handlers.

    Command handlers contain the business logic for executing a command.
    They orchestrate the use of domain services and repositories.

    Design Principles:
    - Single Responsibility: One handler per command type
    - Dependency Inversion: Depends on abstractions (interfaces)
    - Open/Closed: Extend by adding new handlers, not modifying existing ones

    Example:
        class EnrollFaceCommandHandler(CommandHandler[EnrollFaceCommand, FaceEmbedding]):
            def __init__(
                self,
                detector: IFaceDetector,
                extractor: IEmbeddingExtractor,
                repository: IEmbeddingRepository,
            ):
                self._detector = detector
                self._extractor = extractor
                self._repository = repository

            async def handle(self, command: EnrollFaceCommand) -> FaceEmbedding:
                # Execute business logic
                ...
    """

    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle the command and return the result.

        Args:
            command: The command to handle

        Returns:
            Result of the command execution

        Raises:
            DomainException: When business rules are violated
            InfrastructureException: When infrastructure fails
        """
        pass


class CommandBus:
    """Command bus for routing commands to handlers.

    The command bus acts as a mediator between the API layer and command handlers.
    It decouples the caller from knowing which handler to use.

    Design Patterns:
    - Mediator Pattern: Centralizes command routing
    - Registry Pattern: Maps commands to handlers
    - Dependency Injection: Handlers are injected

    Benefits:
    - Loose coupling: Caller doesn't know about handlers
    - Easy testing: Can swap handlers for testing
    - Middleware support: Can add cross-cutting concerns (logging, validation, etc.)

    Example:
        # Register handlers
        command_bus = CommandBus()
        command_bus.register(EnrollFaceCommand, enroll_handler)

        # Execute command
        command = EnrollFaceCommand(user_id="123", image_path="/path/to/image.jpg")
        result = await command_bus.execute(command)
    """

    def __init__(self):
        """Initialize command bus with empty handler registry."""
        self._handlers: Dict[Type[Command], CommandHandler] = {}
        logger.info("CommandBus initialized")

    def register(
        self,
        command_type: Type[TCommand],
        handler: CommandHandler[TCommand, Any]
    ) -> None:
        """Register a command handler.

        Args:
            command_type: The command class to register
            handler: The handler for this command type

        Raises:
            ValueError: If command type is already registered
        """
        if command_type in self._handlers:
            raise ValueError(
                f"Handler for command {command_type.__name__} is already registered"
            )

        self._handlers[command_type] = handler
        logger.info(f"Registered handler for command: {command_type.__name__}")

    async def execute(self, command: TCommand) -> Any:
        """Execute a command by routing it to the appropriate handler.

        Args:
            command: The command to execute

        Returns:
            Result from the command handler

        Raises:
            ValueError: If no handler is registered for the command
            DomainException: When business rules are violated
            InfrastructureException: When infrastructure fails
        """
        command_type = type(command)
        handler = self._handlers.get(command_type)

        if handler is None:
            raise ValueError(
                f"No handler registered for command: {command_type.__name__}"
            )

        logger.debug(f"Executing command: {command.get_command_name()}")

        try:
            result = await handler.handle(command)
            logger.debug(f"Command executed successfully: {command.get_command_name()}")
            return result
        except Exception as e:
            logger.error(
                f"Command execution failed: {command.get_command_name()}, error: {str(e)}",
                exc_info=True
            )
            raise

    def has_handler(self, command_type: Type[Command]) -> bool:
        """Check if a handler is registered for a command type.

        Args:
            command_type: The command class to check

        Returns:
            True if handler is registered, False otherwise
        """
        return command_type in self._handlers

    def get_registered_commands(self) -> list[str]:
        """Get list of registered command names.

        Returns:
            List of command class names
        """
        return [cmd.__name__ for cmd in self._handlers.keys()]
