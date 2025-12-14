"""Base component classes following Open/Closed Principle.

This module provides abstract base classes for UI components,
enabling extension without modification (OCP from SOLID).

Classes:
    BaseComponent: Abstract base for all reusable components.
    BasePage: Abstract base for all demo pages with template method pattern.

Example:
    >>> class EnrollmentPage(BasePage):
    ...     @property
    ...     def title(self) -> str:
    ...         return "Face Enrollment"
    ...
    ...     def _render_main_content(self) -> None:
    ...         st.write("Upload face image...")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from utils.container import DependencyContainer


class BaseComponent(ABC):
    """Abstract base class for all UI components.

    Provides a consistent interface for reusable components,
    enabling extension without modification (Open/Closed Principle).

    Subclasses must implement:
        - render(): Render the component to the page
        - get_state(): Return current component state

    Attributes:
        _container: Dependency injection container.
        _key: Unique Streamlit key for the component.

    Example:
        >>> class MetricsCard(BaseComponent):
        ...     def render(self) -> None:
        ...         st.metric(self.label, self.value)
    """

    def __init__(
        self,
        container: DependencyContainer | None = None,
        key: str | None = None,
    ) -> None:
        """Initialize base component.

        Args:
            container: Optional dependency container. If None, uses global.
            key: Unique Streamlit key for this component instance.
        """
        if container is None:
            from utils.container import get_container
            container = get_container()

        self._container = container
        self._key = key or self.__class__.__name__

    @property
    def container(self) -> DependencyContainer:
        """Get the dependency container."""
        return self._container

    @property
    def key(self) -> str:
        """Get the component's unique key."""
        return self._key

    @abstractmethod
    def render(self) -> None:
        """Render the component to the Streamlit page.

        Subclasses must implement this method to define
        the component's visual representation.
        """
        pass

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Get current component state.

        Returns:
            Dictionary containing component state values.
        """
        pass

    def __repr__(self) -> str:
        """Return string representation."""
        return f"{self.__class__.__name__}(key={self._key!r})"


class BasePage(ABC):
    """Abstract base class for all demo pages.

    Implements the Template Method pattern for consistent page structure:
        1. Render header
        2. Render sidebar options (optional)
        3. Render main content (abstract - subclasses implement)
        4. Render results (optional)
        5. Render footer

    Subclasses must implement:
        - title: Page title property
        - description: Page description property
        - _render_main_content(): Main page content

    Example:
        >>> class EnrollmentPage(BasePage):
        ...     @property
        ...     def title(self) -> str:
        ...         return "Face Enrollment"
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return "Register face embeddings with quality assessment"
        ...
        ...     def _render_main_content(self) -> None:
        ...         uploaded_file = st.file_uploader("Upload face image")
        ...         # Handle upload...
    """

    def __init__(
        self,
        container: DependencyContainer | None = None,
    ) -> None:
        """Initialize base page.

        Args:
            container: Optional dependency container. If None, uses global.
        """
        if container is None:
            from utils.container import get_container
            container = get_container()

        self._container = container
        self._results: dict[str, Any] | None = None

    @property
    def container(self) -> DependencyContainer:
        """Get the dependency container."""
        return self._container

    @property
    @abstractmethod
    def title(self) -> str:
        """Page title displayed in header."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Page description displayed below title."""
        pass

    @property
    def icon(self) -> str:
        """Page icon emoji. Override in subclass."""
        return "📄"

    def render(self) -> None:
        """Template method defining page rendering workflow.

        This method orchestrates the page rendering process.
        Subclasses should NOT override this method; instead,
        override the hook methods (_render_*).
        """
        self._render_header()
        self._render_sidebar_options()
        self._render_main_content()

        if self._results:
            self._render_results()

        self._render_footer()

    def _render_header(self) -> None:
        """Render page header with title and description."""
        import streamlit as st

        st.title(f"{self.icon} {self.title}")
        st.markdown(self.description)
        st.divider()

    def _render_sidebar_options(self) -> None:
        """Render sidebar options. Override in subclass if needed."""
        pass

    @abstractmethod
    def _render_main_content(self) -> None:
        """Render main page content.

        Subclasses MUST implement this method to define
        the page's primary content and interactions.
        """
        pass

    def _render_results(self) -> None:
        """Render results section. Called when self._results is set."""
        import streamlit as st

        st.divider()
        st.subheader("Results")

        from components.result_display import render_result
        render_result(self._results)

    def _render_footer(self) -> None:
        """Render page footer."""
        import streamlit as st

        st.divider()
        st.caption("Biometric Processor Demo v1.0.0 | FIVUCSAS Team")

    def set_results(self, results: dict[str, Any]) -> None:
        """Set results to be displayed.

        Args:
            results: Dictionary containing operation results.
        """
        self._results = results

    def clear_results(self) -> None:
        """Clear displayed results."""
        self._results = None
