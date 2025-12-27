"""File resolution strategies for static file serving.

Implements the Strategy pattern for flexible file resolution.
This allows adding new resolution strategies without modifying existing code (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class FileResolutionStrategy(ABC):
    """Abstract strategy for resolving file paths.

    Strategy Pattern: Defines the interface for all file resolution algorithms.
    Each concrete strategy implements a different approach to finding files.
    """

    @abstractmethod
    def resolve(self, static_dir: Path, path: str) -> Optional[Path]:
        """Resolve path to file.

        Args:
            static_dir: Base directory for static files
            path: User-provided path to resolve

        Returns:
            Resolved Path if file found, None otherwise
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name for logging."""
        pass


class ExactFileStrategy(FileResolutionStrategy):
    """Strategy: Try exact file match.

    Example:
        Path "settings/profile" -> static_dir/settings/profile (if exists)
    """

    def resolve(self, static_dir: Path, path: str) -> Optional[Path]:
        """Resolve to exact file path."""
        file_path = static_dir / path
        return file_path if file_path.is_file() else None

    def get_name(self) -> str:
        return "exact_file"


class HtmlExtensionStrategy(FileResolutionStrategy):
    """Strategy: Try adding .html extension.

    Supports Next.js static export pattern.

    Example:
        Path "settings/profile" -> static_dir/settings/profile.html (if exists)
    """

    def resolve(self, static_dir: Path, path: str) -> Optional[Path]:
        """Resolve with .html extension."""
        html_path = static_dir / f"{path}.html"
        return html_path if html_path.is_file() else None

    def get_name(self) -> str:
        return "html_extension"


class DirectoryIndexStrategy(FileResolutionStrategy):
    """Strategy: Try directory index.html.

    Example:
        Path "settings" -> static_dir/settings/index.html (if exists)
    """

    def resolve(self, static_dir: Path, path: str) -> Optional[Path]:
        """Resolve to directory index."""
        file_path = static_dir / path
        if file_path.is_dir():
            index_path = file_path / "index.html"
            return index_path if index_path.is_file() else None
        return None

    def get_name(self) -> str:
        return "directory_index"


class SpaFallbackStrategy(FileResolutionStrategy):
    """Strategy: Fallback to root index.html for SPA routing.

    This should be the last strategy in the chain.
    Supports client-side routing in Single Page Applications.

    Example:
        Path "any/unknown/path" -> static_dir/index.html (always, if exists)
    """

    def resolve(self, static_dir: Path, path: str) -> Optional[Path]:
        """Resolve to root index.html."""
        index_html = static_dir / "index.html"
        return index_html if index_html.is_file() else None

    def get_name(self) -> str:
        return "spa_fallback"


class FileResolver:
    """Resolves files using a chain of strategies.

    Chain of Responsibility pattern combined with Strategy pattern.
    Tries each strategy in order until one succeeds.

    Example:
        resolver = FileResolver([
            ExactFileStrategy(),
            HtmlExtensionStrategy(),
            DirectoryIndexStrategy(),
            SpaFallbackStrategy(),
        ])

        file_path = resolver.resolve(static_dir, "settings/profile")
        # Tries: settings/profile, settings/profile.html, settings/profile/index.html, index.html
    """

    def __init__(self, strategies: list[FileResolutionStrategy]):
        """Initialize resolver with strategies.

        Args:
            strategies: List of strategies to try in order
        """
        self.strategies = strategies

    def resolve(self, static_dir: Path, path: str) -> tuple[Optional[Path], Optional[str]]:
        """Resolve file using chain of strategies.

        Args:
            static_dir: Base directory for static files
            path: User-provided path to resolve

        Returns:
            Tuple of (resolved_path, strategy_name) or (None, None) if not found
        """
        for strategy in self.strategies:
            resolved = strategy.resolve(static_dir, path)
            if resolved:
                return resolved, strategy.get_name()
        return None, None

    def add_strategy(self, strategy: FileResolutionStrategy, position: Optional[int] = None):
        """Add a new strategy dynamically.

        Demonstrates Open/Closed Principle: Can extend behavior without modifying existing code.

        Args:
            strategy: Strategy to add
            position: Position to insert (None = append to end)
        """
        if position is None:
            self.strategies.append(strategy)
        else:
            self.strategies.insert(position, strategy)


def create_default_resolver() -> FileResolver:
    """Create default file resolver with standard Next.js strategies.

    Factory function for creating the default resolver.

    Returns:
        FileResolver with default strategies
    """
    return FileResolver([
        ExactFileStrategy(),
        HtmlExtensionStrategy(),
        DirectoryIndexStrategy(),
        SpaFallbackStrategy(),
    ])
