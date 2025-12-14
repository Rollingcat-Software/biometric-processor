"""Face Verification Demo Page.

This page demonstrates 1:1 face matching:
    - Verify against enrolled user
    - Direct image-to-image comparison
    - Adjustable similarity threshold
    - Confidence scoring with visualization
    - Side-by-side comparison view

API Endpoints Used:
    - POST /api/v1/verify - Against enrolled user
    - POST /api/v1/compare - Direct comparison
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st
import plotly.graph_objects as go

from components.base import BasePage
from components.image_uploader import ImageUploader
from components.metrics import render_metric
from utils.config import get_settings, get_thresholds
from utils.exceptions import APIConnectionError, APIResponseError, DemoAppError


class FaceVerificationPage(BasePage):
    """Face Verification demo page.

    Demonstrates 1:1 face matching with configurable thresholds
    and detailed match visualization.

    Attributes:
        _reference_uploader: Uploader for reference image.
        _probe_uploader: Uploader for probe image.
        _verification_result: Latest verification result.
    """

    def __init__(self) -> None:
        """Initialize the verification page."""
        super().__init__()
        self._verification_result: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        """Page title."""
        return "Face Verification"

    @property
    def description(self) -> str:
        """Page description."""
        return """
        Perform 1:1 face matching to verify identity. Compare a probe image
        against an enrolled user or directly compare two images.
        """

    @property
    def icon(self) -> str:
        """Page icon."""
        return "🔐"

    def _render_sidebar_options(self) -> None:
        """Render sidebar verification options."""
        with st.sidebar:
            st.header("Verification Settings")

            # Verification mode
            st.radio(
                "Verification Mode",
                options=["Direct Comparison", "Against Enrolled User"],
                key="verification_mode",
                help="Choose how to verify the face",
            )

            st.divider()

            # Threshold slider
            thresholds = get_thresholds()
            st.slider(
                "Similarity Threshold",
                min_value=0.3,
                max_value=0.9,
                value=thresholds.VERIFICATION_SIMILARITY,
                step=0.05,
                key="similarity_threshold",
                help="Minimum similarity score to consider a match",
            )

            st.divider()

            # Enrolled user selection (for enrolled mode)
            if st.session_state.get("verification_mode") == "Against Enrolled User":
                st.text_input(
                    "Enrolled User ID",
                    key="enrolled_user_id",
                    placeholder="e.g., john_doe_123",
                    help="User ID to verify against",
                )

                st.selectbox(
                    "Tenant",
                    options=["default", "tenant_a", "tenant_b", "demo"],
                    key="verification_tenant",
                    help="Tenant for the enrolled user",
                )

            st.divider()

            # Display options
            st.subheader("Display Options")

            st.checkbox(
                "Show Detailed Metrics",
                value=True,
                key="show_detailed_metrics",
            )

            st.checkbox(
                "Show Face Detection Boxes",
                value=True,
                key="show_face_boxes",
            )

    def _render_main_content(self) -> None:
        """Render main verification content."""
        mode = st.session_state.get("verification_mode", "Direct Comparison")

        # Mode indicator
        st.info(f"**Mode:** {mode}")

        if mode == "Direct Comparison":
            self._render_direct_comparison()
        else:
            self._render_enrolled_verification()

        # Results section
        st.divider()
        self._render_verification_results()

    def _render_direct_comparison(self) -> None:
        """Render direct image comparison interface."""
        col_ref, col_probe = st.columns(2)

        with col_ref:
            st.subheader("Reference Image")
            self._reference_uploader = ImageUploader(
                key="reference_image",
                label="Upload Reference Face",
                show_preview=True,
            )
            self._reference_uploader.render()

        with col_probe:
            st.subheader("Probe Image")
            self._probe_uploader = ImageUploader(
                key="probe_image",
                label="Upload Probe Face",
                show_preview=True,
            )
            self._probe_uploader.render()

        # Compare button
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            can_compare = (
                hasattr(self, "_reference_uploader")
                and hasattr(self, "_probe_uploader")
                and self._reference_uploader.has_image
                and self._probe_uploader.has_image
            )

            if st.button(
                "Compare Faces",
                type="primary",
                use_container_width=True,
                disabled=not can_compare,
            ):
                self._perform_direct_comparison()

    def _render_enrolled_verification(self) -> None:
        """Render verification against enrolled user."""
        col_input, col_settings = st.columns([1, 1])

        with col_input:
            st.subheader("Probe Image")
            self._probe_uploader = ImageUploader(
                key="verify_probe_image",
                label="Upload Face to Verify",
                show_preview=True,
            )
            self._probe_uploader.render()

        with col_settings:
            st.subheader("Enrolled User Info")

            user_id = st.session_state.get("enrolled_user_id", "")
            tenant = st.session_state.get("verification_tenant", "default")

            if user_id:
                st.success(f"""
                **Verifying Against:**
                - User ID: `{user_id}`
                - Tenant: `{tenant}`
                - Threshold: `{st.session_state.get('similarity_threshold', 0.6)}`
                """)
            else:
                st.warning("Enter an enrolled User ID in the sidebar to continue.")

        # Verify button
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            can_verify = (
                hasattr(self, "_probe_uploader")
                and self._probe_uploader.has_image
                and bool(st.session_state.get("enrolled_user_id", "").strip())
            )

            if st.button(
                "Verify Identity",
                type="primary",
                use_container_width=True,
                disabled=not can_verify,
            ):
                self._perform_enrolled_verification()

    def _perform_direct_comparison(self) -> None:
        """Execute direct face comparison."""
        reference_bytes = self._reference_uploader.get_image_bytes()
        probe_bytes = self._probe_uploader.get_image_bytes()
        threshold = st.session_state.get("similarity_threshold", 0.6)

        with st.spinner("Comparing faces..."):
            try:
                self._verification_result = asyncio.run(
                    self._compare_faces(reference_bytes, probe_bytes, threshold)
                )
                st.success("Comparison complete!")
            except APIConnectionError as e:
                st.error(e.to_user_message())
            except APIResponseError as e:
                st.error(e.to_user_message())
            except DemoAppError as e:
                st.error(e.to_user_message())
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    def _perform_enrolled_verification(self) -> None:
        """Execute verification against enrolled user."""
        probe_bytes = self._probe_uploader.get_image_bytes()
        user_id = st.session_state.get("enrolled_user_id", "").strip()
        tenant = st.session_state.get("verification_tenant", "default")
        threshold = st.session_state.get("similarity_threshold", 0.6)

        with st.spinner("Verifying identity..."):
            try:
                self._verification_result = asyncio.run(
                    self._verify_against_enrolled(
                        probe_bytes, user_id, tenant, threshold
                    )
                )
                st.success("Verification complete!")
            except APIConnectionError as e:
                st.error(e.to_user_message())
            except APIResponseError as e:
                st.error(e.to_user_message())
            except DemoAppError as e:
                st.error(e.to_user_message())
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    async def _compare_faces(
        self,
        reference_bytes: bytes,
        probe_bytes: bytes,
        threshold: float,
    ) -> dict[str, Any]:
        """Compare two face images directly.

        Args:
            reference_bytes: Reference image data.
            probe_bytes: Probe image data.
            threshold: Similarity threshold.

        Returns:
            Comparison result.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/compare",
            data={"threshold": threshold},
            files={
                "image1": reference_bytes,
                "image2": probe_bytes,
            },
        )
        return result

    async def _verify_against_enrolled(
        self,
        probe_bytes: bytes,
        user_id: str,
        tenant: str,
        threshold: float,
    ) -> dict[str, Any]:
        """Verify probe image against enrolled user.

        Args:
            probe_bytes: Probe image data.
            user_id: Enrolled user ID.
            tenant: Tenant ID.
            threshold: Similarity threshold.

        Returns:
            Verification result.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/verify",
            data={
                "user_id": user_id,
                "tenant_id": tenant,
                "threshold": threshold,
            },
            files={"image": probe_bytes},
        )
        return result

    def _render_verification_results(self) -> None:
        """Render verification results section."""
        st.subheader("Verification Result")

        if not self._verification_result:
            st.info("Upload images and click 'Compare Faces' or 'Verify Identity' to see results.")
            return

        result = self._verification_result

        # Main result banner
        verified = result.get("verified", False)
        similarity = result.get("similarity", result.get("confidence", 0))
        threshold = result.get("threshold", st.session_state.get("similarity_threshold", 0.6))

        # Result status banner
        if verified:
            st.success(
                f"**VERIFIED - SAME PERSON**\n\n"
                f"Confidence: HIGH ({similarity*100:.1f}% > {threshold*100:.1f}%)"
            )
        else:
            st.error(
                f"**NOT VERIFIED - DIFFERENT PERSON**\n\n"
                f"Similarity: LOW ({similarity*100:.1f}% < {threshold*100:.1f}%)"
            )

        # Similarity gauge
        self._render_similarity_gauge(similarity, threshold)

        # Detailed metrics
        if st.session_state.get("show_detailed_metrics", True):
            st.divider()
            self._render_detailed_metrics(result)

        # Raw response
        with st.expander("View Raw API Response"):
            st.json(result)

    def _render_similarity_gauge(self, similarity: float, threshold: float) -> None:
        """Render similarity score gauge chart.

        Args:
            similarity: Similarity score (0-1).
            threshold: Threshold value (0-1).
        """
        # Create gauge chart
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=similarity * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Similarity Score"},
            delta={'reference': threshold * 100, 'suffix': '%'},
            gauge={
                'axis': {'range': [0, 100], 'ticksuffix': '%'},
                'bar': {'color': "darkgreen" if similarity >= threshold else "darkred"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 50], 'color': 'lightcoral'},
                    {'range': [50, 70], 'color': 'lightyellow'},
                    {'range': [70, 100], 'color': 'lightgreen'},
                ],
                'threshold': {
                    'line': {'color': "blue", 'width': 4},
                    'thickness': 0.75,
                    'value': threshold * 100,
                },
            }
        ))

        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_detailed_metrics(self, result: dict[str, Any]) -> None:
        """Render detailed verification metrics.

        Args:
            result: Verification result dictionary.
        """
        st.markdown("**Detailed Metrics**")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            similarity = result.get("similarity", result.get("confidence", 0))
            render_metric(
                label="Similarity Score",
                value=f"{similarity:.4f}",
            )

        with col2:
            threshold = result.get("threshold", 0.6)
            render_metric(
                label="Threshold Used",
                value=f"{threshold:.2f}",
            )

        with col3:
            distance = result.get("distance", 1 - similarity)
            render_metric(
                label="Distance",
                value=f"{distance:.4f}",
            )

        with col4:
            processing_time = result.get("processing_time_ms", 0)
            render_metric(
                label="Processing Time",
                value=f"{processing_time:.0f}ms",
            )

        # Face detection confidence
        if "face_confidence" in result or "face_detection_confidence" in result:
            st.markdown("**Face Detection**")
            face_conf = result.get("face_confidence", result.get("face_detection_confidence", 0))

            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Reference Face Confidence",
                    f"{result.get('reference_face_confidence', face_conf)*100:.1f}%",
                )
            with col2:
                st.metric(
                    "Probe Face Confidence",
                    f"{result.get('probe_face_confidence', face_conf)*100:.1f}%",
                )


# Page entry point - called by Streamlit when page is loaded
page = FaceVerificationPage()
page.render()
