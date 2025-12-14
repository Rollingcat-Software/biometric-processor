"""Face Enrollment Demo Page.

This page demonstrates the face registration workflow:
    - Single face enrollment with quality validation
    - Embedding extraction visualization
    - Duplicate detection
    - Multi-tenant support
    - Metadata attachment

API Endpoints Used:
    - POST /api/v1/enroll - Main enrollment
    - POST /api/v1/quality/analyze - Pre-validation
    - POST /api/v1/faces/detect-all - Face detection preview
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from components.base import BasePage
from components.image_uploader import ImageUploader
from components.metrics import MetricsCard, render_metric
from components.result_display import render_result
from utils.config import get_settings, get_thresholds
from utils.exceptions import APIConnectionError, APIResponseError, DemoAppError


class FaceEnrollmentPage(BasePage):
    """Face Enrollment demo page.

    Demonstrates the complete face registration workflow including
    quality validation, duplicate detection, and embedding visualization.

    Attributes:
        _uploader: Image uploader component.
        _enrollment_result: Latest enrollment result.
        _quality_result: Latest quality analysis result.
    """

    def __init__(self) -> None:
        """Initialize the enrollment page."""
        super().__init__()
        self._enrollment_result: dict[str, Any] | None = None
        self._quality_result: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        """Page title."""
        return "Face Enrollment"

    @property
    def description(self) -> str:
        """Page description."""
        return """
        Register face embeddings with quality assessment and duplicate detection.
        Upload an image or use sample faces to test the enrollment workflow.
        """

    @property
    def icon(self) -> str:
        """Page icon."""
        return "📝"

    def _render_sidebar_options(self) -> None:
        """Render sidebar enrollment options."""
        with st.sidebar:
            st.header("Enrollment Settings")

            # User ID input
            st.session_state.setdefault("enrollment_user_id", "")
            st.text_input(
                "User ID",
                key="enrollment_user_id_input",
                value=st.session_state.get("enrollment_user_id", ""),
                help="Unique identifier for the user being enrolled",
                placeholder="e.g., john_doe_123",
                on_change=lambda: st.session_state.update(
                    {"enrollment_user_id": st.session_state.enrollment_user_id_input}
                ),
            )

            st.divider()

            # Tenant selection
            st.selectbox(
                "Tenant",
                options=["default", "tenant_a", "tenant_b", "demo"],
                key="enrollment_tenant",
                help="Multi-tenant isolation for enrollments",
            )

            st.divider()

            # Validation options
            st.subheader("Validation Options")

            st.checkbox(
                "Validate Quality First",
                value=True,
                key="validate_quality",
                help="Run quality analysis before enrollment",
            )

            st.checkbox(
                "Check for Duplicates",
                value=True,
                key="check_duplicates",
                help="Search for existing similar faces",
            )

            st.checkbox(
                "Skip if Exists",
                value=False,
                key="skip_if_exists",
                help="Skip enrollment if user already exists",
            )

            st.divider()

            # Metadata input
            st.subheader("Metadata (Optional)")
            st.text_area(
                "JSON Metadata",
                value='{"department": "demo", "source": "web_app"}',
                key="enrollment_metadata",
                height=100,
                help="Additional metadata to store with enrollment",
            )

    def _render_main_content(self) -> None:
        """Render main enrollment content."""
        # Create two columns: image upload and results
        col_upload, col_settings = st.columns([1, 1])

        with col_upload:
            st.subheader("Image Input")

            # Tabs for different input methods
            tab_upload, tab_samples = st.tabs(["Upload Image", "Sample Images"])

            with tab_upload:
                self._uploader = ImageUploader(
                    key="enrollment_image",
                    label="Upload Face Image",
                    show_preview=True,
                )
                self._uploader.render()

            with tab_samples:
                self._render_sample_images()

        with col_settings:
            st.subheader("Quick Settings")

            # Show current settings summary
            user_id = st.session_state.get("enrollment_user_id_input", "")
            tenant = st.session_state.get("enrollment_tenant", "default")

            st.info(f"""
            **Current Configuration:**
            - User ID: `{user_id or '(not set)'}`
            - Tenant: `{tenant}`
            - Quality Check: {'Yes' if st.session_state.get('validate_quality', True) else 'No'}
            - Duplicate Check: {'Yes' if st.session_state.get('check_duplicates', True) else 'No'}
            """)

            # Enroll button
            if st.button(
                "Enroll Face",
                type="primary",
                use_container_width=True,
                disabled=not self._can_enroll(),
            ):
                self._perform_enrollment()

        # Results section
        st.divider()
        self._render_enrollment_results()

    def _render_sample_images(self) -> None:
        """Render sample image selection."""
        st.markdown("Select a sample face image for testing:")

        # Sample images grid (using placeholder for now)
        sample_cols = st.columns(3)

        sample_faces = [
            {"name": "Person 1", "desc": "Male, frontal"},
            {"name": "Person 2", "desc": "Female, frontal"},
            {"name": "Person 3", "desc": "Male, slight angle"},
        ]

        for idx, (col, sample) in enumerate(zip(sample_cols, sample_faces)):
            with col:
                st.markdown(f"**{sample['name']}**")
                st.caption(sample['desc'])
                if st.button(f"Use", key=f"sample_{idx}"):
                    st.session_state["selected_sample"] = idx
                    st.info(f"Selected {sample['name']} (sample images would be loaded from assets)")

    def _can_enroll(self) -> bool:
        """Check if enrollment can proceed.

        Returns:
            True if all requirements met for enrollment.
        """
        # Check if image is available
        has_image = (
            hasattr(self, "_uploader") and self._uploader.has_image
        ) or st.session_state.get("selected_sample") is not None

        # Check if user ID is set
        has_user_id = bool(st.session_state.get("enrollment_user_id_input", "").strip())

        return has_image and has_user_id

    def _perform_enrollment(self) -> None:
        """Execute the enrollment workflow."""
        user_id = st.session_state.get("enrollment_user_id_input", "").strip()
        tenant = st.session_state.get("enrollment_tenant", "default")
        validate_quality = st.session_state.get("validate_quality", True)
        check_duplicates = st.session_state.get("check_duplicates", True)

        # Parse metadata
        try:
            metadata_str = st.session_state.get("enrollment_metadata", "{}")
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            st.error("Invalid JSON in metadata field. Using empty metadata.")
            metadata = {}

        # Get image bytes
        if hasattr(self, "_uploader") and self._uploader.has_image:
            image_bytes = self._uploader.get_image_bytes()
        else:
            st.warning("Please upload an image or select a sample.")
            return

        # Run enrollment workflow
        with st.spinner("Processing enrollment..."):
            try:
                # Step 1: Quality validation (if enabled)
                if validate_quality:
                    self._quality_result = asyncio.run(
                        self._analyze_quality(image_bytes)
                    )

                    if not self._quality_result.get("is_acceptable", False):
                        st.warning("Image quality is below acceptable threshold.")
                        return

                # Step 2: Check duplicates (if enabled)
                if check_duplicates:
                    duplicates = asyncio.run(
                        self._check_duplicates(image_bytes, tenant)
                    )
                    if duplicates.get("matches"):
                        st.warning(
                            f"Potential duplicate found: {duplicates['matches'][0].get('user_id', 'unknown')}"
                        )
                        if not st.session_state.get("skip_if_exists", False):
                            return

                # Step 3: Perform enrollment
                self._enrollment_result = asyncio.run(
                    self._enroll_face(
                        image_bytes=image_bytes,
                        user_id=user_id,
                        tenant=tenant,
                        metadata=metadata,
                    )
                )

                st.success("Face enrolled successfully!")

            except APIConnectionError as e:
                st.error(e.to_user_message())
            except APIResponseError as e:
                st.error(e.to_user_message())
            except DemoAppError as e:
                st.error(e.to_user_message())
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    async def _analyze_quality(self, image_bytes: bytes) -> dict[str, Any]:
        """Analyze image quality.

        Args:
            image_bytes: Image data to analyze.

        Returns:
            Quality analysis result.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/quality/analyze",
            files={"image": image_bytes},
        )
        return result

    async def _check_duplicates(
        self,
        image_bytes: bytes,
        tenant: str,
    ) -> dict[str, Any]:
        """Check for duplicate faces.

        Args:
            image_bytes: Image data to check.
            tenant: Tenant to search within.

        Returns:
            Search result with potential matches.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/search",
            data={"tenant_id": tenant, "max_results": 1},
            files={"image": image_bytes},
        )
        return result

    async def _enroll_face(
        self,
        image_bytes: bytes,
        user_id: str,
        tenant: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Enroll a face in the system.

        Args:
            image_bytes: Image data containing face.
            user_id: Unique identifier for the user.
            tenant: Tenant ID for multi-tenant isolation.
            metadata: Additional metadata to store.

        Returns:
            Enrollment result including embedding ID.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/enroll",
            data={
                "user_id": user_id,
                "tenant_id": tenant,
                "metadata": json.dumps(metadata),
            },
            files={"image": image_bytes},
        )
        return result

    def _render_enrollment_results(self) -> None:
        """Render enrollment results section."""
        st.subheader("Results")

        if not self._enrollment_result and not self._quality_result:
            st.info("Upload an image and click 'Enroll Face' to see results.")
            return

        # Create tabs for different result views
        tabs = st.tabs(["Enrollment Details", "Quality Analysis", "Embedding Visualization"])

        with tabs[0]:
            self._render_enrollment_details()

        with tabs[1]:
            self._render_quality_details()

        with tabs[2]:
            self._render_embedding_visualization()

    def _render_enrollment_details(self) -> None:
        """Render enrollment details."""
        if not self._enrollment_result:
            st.info("No enrollment performed yet.")
            return

        result = self._enrollment_result

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            render_metric(
                label="Enrollment ID",
                value=result.get("enrollment_id", "N/A")[:12] + "...",
            )

        with col2:
            quality_score = result.get("quality_score", 0) * 100
            render_metric(
                label="Quality Score",
                value=f"{quality_score:.1f}%",
                delta="Good" if quality_score > 70 else "Low",
            )

        with col3:
            confidence = result.get("face_confidence", 0) * 100
            render_metric(
                label="Face Confidence",
                value=f"{confidence:.1f}%",
            )

        with col4:
            render_metric(
                label="User ID",
                value=result.get("user_id", "N/A"),
            )

        # Full details expander
        with st.expander("View Full Response"):
            st.json(result)

    def _render_quality_details(self) -> None:
        """Render quality analysis details."""
        if not self._quality_result:
            st.info("No quality analysis performed.")
            return

        result = self._quality_result

        # Overall score gauge
        overall_score = result.get("overall_score", 0)
        thresholds = get_thresholds()

        # Quality metrics
        metrics = result.get("metrics", {})

        if metrics:
            st.markdown("**Quality Metrics**")

            # Create metrics chart
            metric_names = list(metrics.keys())
            metric_values = list(metrics.values())

            fig = go.Figure(go.Bar(
                x=metric_values,
                y=metric_names,
                orientation='h',
                marker_color=['green' if v > 70 else 'orange' if v > 50 else 'red' for v in metric_values],
            ))

            fig.update_layout(
                title="Quality Metrics Breakdown",
                xaxis_title="Score",
                yaxis_title="Metric",
                height=300,
            )

            st.plotly_chart(fig, use_container_width=True)

        # Issues and recommendations
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Issues**")
            issues = result.get("issues", [])
            if issues:
                for issue in issues:
                    st.warning(issue)
            else:
                st.success("No issues detected")

        with col2:
            st.markdown("**Recommendations**")
            recommendations = result.get("recommendations", [])
            if recommendations:
                for rec in recommendations:
                    st.info(rec)
            else:
                st.info("Image meets all quality requirements")

    def _render_embedding_visualization(self) -> None:
        """Render embedding vector visualization."""
        if not self._enrollment_result:
            st.info("No embedding available.")
            return

        # Get embedding from result (if available)
        embedding = self._enrollment_result.get("embedding")

        if not embedding:
            st.info("Embedding vector not included in response. Enable 'return_embedding' for visualization.")

            # Show placeholder visualization
            st.markdown("**Example Embedding Visualization (128-D Vector)**")

            # Generate sample embedding for demo
            import random
            sample_embedding = [random.uniform(-1, 1) for _ in range(128)]
            self._plot_embedding(sample_embedding, is_sample=True)
            return

        self._plot_embedding(embedding, is_sample=False)

    def _plot_embedding(self, embedding: list[float], is_sample: bool = False) -> None:
        """Plot embedding vector visualization.

        Args:
            embedding: List of embedding values.
            is_sample: Whether this is sample data.
        """
        # Bar chart
        fig_bar = px.bar(
            x=list(range(len(embedding))),
            y=embedding,
            labels={"x": "Dimension", "y": "Value"},
            title=f"Embedding Vector {'(Sample)' if is_sample else ''}",
        )
        fig_bar.update_layout(height=300)
        st.plotly_chart(fig_bar, use_container_width=True)

        # Heatmap representation
        import numpy as np

        # Reshape to 2D for heatmap (assuming 128-D can be 8x16)
        embed_array = np.array(embedding)
        rows = 8
        cols = len(embedding) // rows

        if len(embedding) % rows == 0:
            embed_2d = embed_array.reshape(rows, cols)

            fig_heat = px.imshow(
                embed_2d,
                title=f"Embedding Heatmap {'(Sample)' if is_sample else ''}",
                color_continuous_scale="RdBu",
                aspect="auto",
            )
            fig_heat.update_layout(height=250)
            st.plotly_chart(fig_heat, use_container_width=True)


# Page entry point - called by Streamlit when page is loaded
page = FaceEnrollmentPage()
page.render()
