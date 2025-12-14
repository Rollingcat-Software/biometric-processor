"""Metrics display components.

This module provides reusable metric card components
for displaying KPIs and statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from components.base import BaseComponent


@dataclass
class MetricData:
    """Data class for metric display.

    Attributes:
        label: Metric label/name.
        value: Current metric value.
        delta: Optional change from previous value.
        delta_color: Color for delta ("normal", "inverse", "off").
        help_text: Optional tooltip text.
    """

    label: str
    value: str | int | float
    delta: str | int | float | None = None
    delta_color: str = "normal"
    help_text: str | None = None


class MetricsCard(BaseComponent):
    """Reusable metrics card component.

    Displays a single metric with optional delta and styling.

    Example:
        >>> card = MetricsCard(
        ...     label="Enrollments",
        ...     value=1247,
        ...     delta="+12.3%",
        ... )
        >>> card.render()
    """

    def __init__(
        self,
        label: str,
        value: str | int | float,
        delta: str | int | float | None = None,
        delta_color: str = "normal",
        help_text: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize metrics card.

        Args:
            label: Metric label/name.
            value: Current metric value.
            delta: Optional change from previous value.
            delta_color: Color for delta ("normal", "inverse", "off").
            help_text: Optional tooltip text.
            **kwargs: Additional arguments for BaseComponent.
        """
        super().__init__(**kwargs)
        self.data = MetricData(
            label=label,
            value=value,
            delta=delta,
            delta_color=delta_color,
            help_text=help_text,
        )

    def render(self) -> None:
        """Render the metrics card."""
        st.metric(
            label=self.data.label,
            value=self.data.value,
            delta=self.data.delta,
            delta_color=self.data.delta_color,
            help=self.data.help_text,
        )

    def get_state(self) -> dict[str, Any]:
        """Get current component state."""
        return {
            "label": self.data.label,
            "value": self.data.value,
            "delta": self.data.delta,
        }


def render_metrics_row(metrics: list[MetricData], columns: int = 4) -> None:
    """Render a row of metrics cards.

    Args:
        metrics: List of MetricData objects to display.
        columns: Number of columns in the row.

    Example:
        >>> render_metrics_row([
        ...     MetricData("Enrollments", 1247, "+12.3%"),
        ...     MetricData("Verifications", 8542, "+8.7%"),
        ...     MetricData("Sessions", 156, "-2.1%"),
        ... ])
    """
    cols = st.columns(columns)

    for i, metric in enumerate(metrics):
        with cols[i % columns]:
            st.metric(
                label=metric.label,
                value=metric.value,
                delta=metric.delta,
                delta_color=metric.delta_color,
                help=metric.help_text,
            )


def render_status_indicator(
    label: str,
    is_healthy: bool,
    details: str | None = None,
) -> None:
    """Render a status indicator.

    Args:
        label: Status label.
        is_healthy: Whether status is healthy/OK.
        details: Optional details text.
    """
    col1, col2 = st.columns([1, 3])

    with col1:
        if is_healthy:
            st.success("✅")
        else:
            st.error("❌")

    with col2:
        st.markdown(f"**{label}**")
        if details:
            st.caption(details)


def render_progress_metric(
    label: str,
    current: int,
    total: int,
    show_percentage: bool = True,
) -> None:
    """Render a progress metric with bar.

    Args:
        label: Progress label.
        current: Current progress value.
        total: Total/target value.
        show_percentage: Whether to show percentage.
    """
    progress = current / total if total > 0 else 0

    st.markdown(f"**{label}**")

    if show_percentage:
        st.progress(progress, text=f"{current}/{total} ({progress:.1%})")
    else:
        st.progress(progress, text=f"{current}/{total}")
