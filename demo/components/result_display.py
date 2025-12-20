"""Result display components.

This module provides components for displaying API results
with proper formatting and visualization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import streamlit as st

from components.base import BaseComponent


@dataclass
class ResultData:
    """Data class for result display.

    Attributes:
        success: Whether operation was successful.
        message: Result message.
        data: Result data dictionary.
        processing_time_ms: Optional processing time in milliseconds.
    """

    success: bool
    message: str
    data: dict[str, Any]
    processing_time_ms: float | None = None


class ResultDisplay(BaseComponent):
    """Reusable result display component.

    Displays API operation results with proper formatting,
    success/error indicators, and expandable JSON view.

    Example:
        >>> result = ResultDisplay(
        ...     success=True,
        ...     message="Face enrolled successfully",
        ...     data={"enrollment_id": "abc-123", "quality_score": 0.94}
        ... )
        >>> result.render()
    """

    def __init__(
        self,
        success: bool,
        message: str,
        data: dict[str, Any],
        processing_time_ms: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize result display.

        Args:
            success: Whether operation was successful.
            message: Result message.
            data: Result data dictionary.
            processing_time_ms: Optional processing time.
            **kwargs: Additional arguments for BaseComponent.
        """
        super().__init__(**kwargs)
        self.result = ResultData(
            success=success,
            message=message,
            data=data,
            processing_time_ms=processing_time_ms,
        )

    def render(self) -> None:
        """Render the result display."""
        # Status indicator
        if self.result.success:
            st.success(f"✅ {self.result.message}")
        else:
            st.error(f"❌ {self.result.message}")

        # Processing time
        if self.result.processing_time_ms:
            st.caption(f"⏱️ Processing time: {self.result.processing_time_ms:.1f}ms")

        # Key metrics in columns
        self._render_key_metrics()

        # Expandable JSON view
        with st.expander("📋 View Raw Response", expanded=False):
            st.json(self.result.data)

    def _render_key_metrics(self) -> None:
        """Render key metrics from result data."""
        # Extract common metric fields
        metric_fields = [
            ("confidence", "Confidence", "{:.1%}"),
            ("similarity", "Similarity", "{:.1%}"),
            ("quality_score", "Quality", "{:.1%}"),
            ("liveness_score", "Liveness", "{:.1f}"),
            ("distance", "Distance", "{:.4f}"),
            ("face_count", "Faces", "{}"),
        ]

        metrics_found = []
        for field, label, fmt in metric_fields:
            if field in self.result.data:
                value = self.result.data[field]
                if isinstance(value, (int, float)):
                    metrics_found.append((label, fmt.format(value)))

        if metrics_found:
            cols = st.columns(len(metrics_found))
            for i, (label, value) in enumerate(metrics_found):
                with cols[i]:
                    st.metric(label, value)

    def get_state(self) -> dict[str, Any]:
        """Get current component state."""
        return {
            "success": self.result.success,
            "message": self.result.message,
            "data_keys": list(self.result.data.keys()),
        }


def render_result(data: dict[str, Any] | None) -> None:
    """Render a result dictionary with auto-detection of format.

    Args:
        data: Result dictionary from API call.
    """
    if not data:
        st.info("No results to display")
        return

    # Detect success/failure
    success = data.get("success", True)
    if "error" in data or "detail" in data:
        success = False

    # Get message
    message = data.get("message", "Operation completed")
    if not success:
        message = data.get("error") or data.get("detail") or "Operation failed"

    # Create and render display
    display = ResultDisplay(
        success=success,
        message=message,
        data=data,
        processing_time_ms=data.get("processing_time_ms"),
    )
    display.render()


def render_json_viewer(
    data: dict[str, Any],
    title: str = "Response",
    expanded: bool = False,
) -> None:
    """Render a JSON viewer with syntax highlighting.

    Args:
        data: Dictionary to display.
        title: Viewer title.
        expanded: Whether viewer is initially expanded.
    """
    with st.expander(f"📋 {title}", expanded=expanded):
        st.json(data)


def render_comparison_result(
    is_match: bool,
    similarity: float,
    threshold: float,
    face1_data: dict[str, Any] | None = None,
    face2_data: dict[str, Any] | None = None,
) -> None:
    """Render a face comparison result.

    Args:
        is_match: Whether faces match.
        similarity: Similarity score (0-1).
        threshold: Match threshold used.
        face1_data: Optional data for first face.
        face2_data: Optional data for second face.
    """
    # Match indicator
    if is_match:
        st.success("✅ **MATCH** - Same Person")
    else:
        st.warning("❌ **NO MATCH** - Different People")

    # Similarity gauge
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Similarity", f"{similarity:.1%}")

    with col2:
        st.metric("Threshold", f"{threshold:.1%}")

    with col3:
        confidence = "High" if similarity > 0.8 else "Medium" if similarity > threshold else "Low"
        st.metric("Confidence", confidence)

    # Visual similarity bar
    st.progress(similarity, text=f"Similarity: {similarity:.1%}")

    # Face details
    if face1_data or face2_data:
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Face 1**")
            if face1_data:
                st.json(face1_data)

        with col2:
            st.markdown("**Face 2**")
            if face2_data:
                st.json(face2_data)
