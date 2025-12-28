"""Liveness Detection Demo Page.

This page demonstrates anti-spoofing capabilities:
    - Passive liveness (texture analysis)
    - Active liveness (facial landmark analysis)
    - Combined mode
    - Spoof detection visualization

API Endpoints Used:
    - POST /api/v1/liveness - Main liveness check
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from components.base import BasePage
from components.image_uploader import ImageUploader
from components.metrics import render_metric
from utils.config import get_settings, get_thresholds
from utils.exceptions import APIConnectionError, APIResponseError, DemoAppError


class LivenessDetectionPage(BasePage):
    """Liveness Detection demo page.

    Demonstrates anti-spoofing capabilities with multiple
    detection modes and detailed analysis visualization.

    Attributes:
        _uploader: Image uploader component.
        _liveness_result: Latest liveness detection result.
    """

    def __init__(self) -> None:
        """Initialize the liveness page."""
        super().__init__()
        self._liveness_result: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        """Page title."""
        return "Liveness Detection"

    @property
    def description(self) -> str:
        """Page description."""
        return """
        Test anti-spoofing capabilities with passive texture analysis,
        active challenge-response, or combined detection modes.
        """

    @property
    def icon(self) -> str:
        """Page icon."""
        return "👁️"

    def _render_sidebar_options(self) -> None:
        """Render sidebar liveness options."""
        with st.sidebar:
            st.header("Detection Settings")

            # Detection mode
            st.radio(
                "Detection Mode",
                options=["Combined", "Passive (Texture)", "Active (Challenge)"],
                key="liveness_mode",
                help="""
                - **Combined**: Uses both texture analysis and behavioral patterns
                - **Passive**: Analyzes image texture for spoofing artifacts
                - **Active**: Requires user to perform actions (blink, smile)
                """,
            )

            st.divider()

            # Liveness threshold
            thresholds = get_thresholds()
            st.slider(
                "Liveness Threshold",
                min_value=50.0,
                max_value=95.0,
                value=thresholds.LIVENESS_SCORE_MIN,
                step=5.0,
                key="liveness_threshold",
                help="Minimum liveness score to pass detection",
            )

            st.divider()

            # Active challenge options
            if st.session_state.get("liveness_mode") == "Active (Challenge)":
                st.subheader("Challenge Settings")

                st.selectbox(
                    "Challenge Type",
                    options=["blink", "smile", "head_turn", "random"],
                    key="challenge_type",
                    help="Type of action to request from user",
                )

                st.slider(
                    "Challenge Timeout (sec)",
                    min_value=5,
                    max_value=30,
                    value=15,
                    key="challenge_timeout",
                )

            st.divider()

            # Display options
            st.subheader("Analysis Options")

            st.checkbox(
                "Show Texture Analysis",
                value=True,
                key="show_texture_analysis",
            )

            st.checkbox(
                "Show Detection Regions",
                value=True,
                key="show_regions",
            )

            st.checkbox(
                "Show Confidence Breakdown",
                value=True,
                key="show_breakdown",
            )

    def _render_main_content(self) -> None:
        """Render main liveness detection content."""
        mode = st.session_state.get("liveness_mode", "Combined")

        # Mode explanation
        mode_descriptions = {
            "Combined": "Analyzes both texture patterns and behavioral cues for comprehensive spoof detection.",
            "Passive (Texture)": "Analyzes image texture to detect print attacks, screen displays, and masks.",
            "Active (Challenge)": "Requests the user to perform specific actions to prove liveness.",
        }

        st.info(f"**{mode} Mode:** {mode_descriptions[mode]}")

        # Main content based on mode
        col_upload, col_info = st.columns([1, 1])

        with col_upload:
            st.subheader("Image Input")

            # Tab for upload vs webcam simulation
            tab_upload, tab_test = st.tabs(["Upload Image", "Test Samples"])

            with tab_upload:
                self._uploader = ImageUploader(
                    key="liveness_image",
                    label="Upload Face Image",
                    show_preview=True,
                )
                self._uploader.render()

            with tab_test:
                self._render_test_samples()

        with col_info:
            st.subheader("What We Detect")

            st.markdown("""
            **Spoof Types Detected:**
            - 📸 **Print Attacks** - Photos of faces
            - 📱 **Screen Replay** - Face displayed on device
            - 🎭 **3D Masks** - Physical face masks
            - 🖼️ **Cutout Attacks** - Face cutouts
            - 🎨 **Deepfakes** - AI-generated faces

            **Analysis Methods:**
            - Texture frequency analysis
            - Color histogram analysis
            - Moiré pattern detection
            - Reflection analysis
            - Depth estimation
            """)

        # Detect button
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            can_detect = hasattr(self, "_uploader") and self._uploader.has_image

            if st.button(
                "Detect Liveness",
                type="primary",
                use_container_width=True,
                disabled=not can_detect,
            ):
                self._perform_detection()

        # Results section
        st.divider()
        self._render_liveness_results()

    def _render_test_samples(self) -> None:
        """Render test sample selection."""
        st.markdown("**Test with Sample Images:**")

        samples = [
            {"name": "Real Face", "type": "live", "desc": "Genuine live face"},
            {"name": "Print Attack", "type": "spoof", "desc": "Printed photo"},
            {"name": "Screen Replay", "type": "spoof", "desc": "Face on screen"},
        ]

        for sample in samples:
            col1, col2 = st.columns([3, 1])
            with col1:
                icon = "✅" if sample["type"] == "live" else "❌"
                st.markdown(f"{icon} **{sample['name']}**\n\n{sample['desc']}")
            with col2:
                if st.button("Use", key=f"sample_{sample['name']}"):
                    st.session_state["test_sample"] = sample
                    st.info(f"Selected {sample['name']} (sample images not included)")

    def _perform_detection(self) -> None:
        """Execute liveness detection."""
        image_bytes = self._uploader.get_image_bytes()
        mode = st.session_state.get("liveness_mode", "Combined")
        threshold = st.session_state.get("liveness_threshold", 70.0)

        # Map UI mode to API challenge type
        challenge_map = {
            "Combined": "combined",
            "Passive (Texture)": "passive",
            "Active (Challenge)": st.session_state.get("challenge_type", "blink"),
        }

        with st.spinner("Analyzing liveness..."):
            try:
                self._liveness_result = asyncio.run(
                    self._detect_liveness(
                        image_bytes=image_bytes,
                        challenge=challenge_map[mode],
                        threshold=threshold,
                    )
                )

                is_live = self._liveness_result.get("is_live", False)
                if is_live:
                    st.success("Liveness verified! This appears to be a real person.")
                else:
                    st.error("Liveness check failed! Potential spoof detected.")

            except APIConnectionError as e:
                st.error(e.to_user_message())
            except APIResponseError as e:
                st.error(e.to_user_message())
            except DemoAppError as e:
                st.error(e.to_user_message())
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    async def _detect_liveness(
        self,
        image_bytes: bytes,
        challenge: str,
        threshold: float,
    ) -> dict[str, Any]:
        """Detect liveness in an image.

        Args:
            image_bytes: Image data to analyze.
            challenge: Type of liveness challenge.
            threshold: Minimum liveness score.

        Returns:
            Liveness detection result.
        """
        api_client = self.container.api_client
        settings = get_settings()

        result = await api_client.post(
            f"{settings.api_version}/liveness",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
        )
        return result

    def _render_liveness_results(self) -> None:
        """Render liveness detection results."""
        st.subheader("Detection Results")

        if not self._liveness_result:
            st.info("Upload an image and click 'Detect Liveness' to see results.")
            return

        result = self._liveness_result

        # Main result banner
        is_live = result.get("is_live", False)
        liveness_score = result.get("liveness_score", 0)
        threshold = st.session_state.get("liveness_threshold", 70.0)

        # Large status indicator
        if is_live:
            st.markdown(
                """
                <div style="padding: 20px; background-color: #d4edda; border-radius: 10px; text-align: center;">
                    <h2 style="color: #155724; margin: 0;">✅ LIVE PERSON DETECTED</h2>
                    <p style="color: #155724; margin: 10px 0 0 0;">
                        Liveness Score: <strong>{:.1f}%</strong> (Threshold: {:.1f}%)
                    </p>
                </div>
                """.format(liveness_score, threshold),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="padding: 20px; background-color: #f8d7da; border-radius: 10px; text-align: center;">
                    <h2 style="color: #721c24; margin: 0;">⚠️ SPOOF DETECTED</h2>
                    <p style="color: #721c24; margin: 10px 0 0 0;">
                        Liveness Score: <strong>{:.1f}%</strong> (Threshold: {:.1f}%)
                    </p>
                </div>
                """.format(liveness_score, threshold),
                unsafe_allow_html=True,
            )

        st.divider()

        # Score gauge
        self._render_liveness_gauge(liveness_score, threshold)

        # Detailed analysis tabs
        tabs = st.tabs(["Score Breakdown", "Texture Analysis", "Detection Details"])

        with tabs[0]:
            self._render_score_breakdown(result)

        with tabs[1]:
            self._render_texture_analysis(result)

        with tabs[2]:
            self._render_detection_details(result)

    def _render_liveness_gauge(self, score: float, threshold: float) -> None:
        """Render liveness score gauge.

        Args:
            score: Liveness score (0-100).
            threshold: Threshold value.
        """
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Liveness Score"},
            delta={'reference': threshold, 'suffix': '%'},
            gauge={
                'axis': {'range': [0, 100], 'ticksuffix': '%'},
                'bar': {'color': "green" if score >= threshold else "red"},
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
                    'value': threshold,
                },
            }
        ))

        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_score_breakdown(self, result: dict[str, Any]) -> None:
        """Render liveness score breakdown.

        Args:
            result: Liveness detection result.
        """
        if not st.session_state.get("show_breakdown", True):
            st.info("Enable 'Show Confidence Breakdown' in sidebar.")
            return

        st.markdown("**Score Components**")

        # Extract checks from response
        checks = result.get("checks", [])

        if not checks:
            st.info("No individual check results available.")
            return

        # Display metrics in columns (up to 4 per row)
        num_checks = len(checks)
        cols = st.columns(min(num_checks, 4))

        for i, check in enumerate(checks[:4]):
            with cols[i]:
                render_metric(
                    label=check.get("name", "Unknown").replace("_", " ").title(),
                    value=f"{check.get('score', 0):.1f}%",
                    delta="Pass" if check.get("passed", False) else "Fail",
                )

        # If more than 4 checks, show another row
        if num_checks > 4:
            cols2 = st.columns(min(num_checks - 4, 4))
            for i, check in enumerate(checks[4:8]):
                with cols2[i]:
                    render_metric(
                        label=check.get("name", "Unknown").replace("_", " ").title(),
                        value=f"{check.get('score', 0):.1f}%",
                        delta="Pass" if check.get("passed", False) else "Fail",
                    )

        # Radar chart with actual checks
        if checks:
            categories = [c.get("name", "").replace("_", " ").title() for c in checks]
            values = [c.get("score", 0) for c in checks]

            fig = go.Figure()

            fig.add_trace(go.Scatterpolar(
                r=values + [values[0]],  # Close the polygon
                theta=categories + [categories[0]],
                fill='toself',
                name='Liveness Scores',
                line_color='green' if result.get("is_live") else 'red',
            ))

            # Add threshold line
            threshold = st.session_state.get("liveness_threshold", 70.0)
            fig.add_trace(go.Scatterpolar(
                r=[threshold] * (len(categories) + 1),
                theta=categories + [categories[0]],
                name='Threshold',
                line_color='blue',
                line_dash='dash',
            ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True,
                height=350,
            )

            st.plotly_chart(fig, use_container_width=True)

    def _render_texture_analysis(self, result: dict[str, Any]) -> None:
        """Render texture analysis details.

        Args:
            result: Liveness detection result.
        """
        if not st.session_state.get("show_texture_analysis", True):
            st.info("Enable 'Show Texture Analysis' in sidebar.")
            return

        st.markdown("**Check Details**")

        checks = result.get("checks", [])

        if not checks:
            st.info("No check details available.")
            return

        # Group checks by type
        texture_checks = [c for c in checks if c.get("name") in ["texture", "color", "frequency", "moire"]]
        active_checks = [c for c in checks if c.get("name") in ["face_landmarks", "eyes_open", "natural_features"]]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Texture Analysis Checks**")
            if texture_checks:
                for check in texture_checks:
                    name = check.get("name", "").replace("_", " ").title()
                    passed = check.get("passed", False)
                    score = check.get("score", 0)
                    details = check.get("details", "")
                    icon = "✅" if passed else "❌"
                    st.markdown(f"{icon} **{name}**: {score:.1f}%")
                    st.caption(f"   {details}")
            else:
                st.info("No texture checks in this result.")

        with col2:
            st.markdown("**Active Analysis Checks**")
            if active_checks:
                for check in active_checks:
                    name = check.get("name", "").replace("_", " ").title()
                    passed = check.get("passed", False)
                    score = check.get("score", 0)
                    details = check.get("details", "")
                    icon = "✅" if passed else "❌"
                    st.markdown(f"{icon} **{name}**: {score:.1f}%")
                    st.caption(f"   {details}")
            else:
                st.info("No active checks in this result.")

    def _render_detection_details(self, result: dict[str, Any]) -> None:
        """Render detailed detection information.

        Args:
            result: Liveness detection result.
        """
        st.markdown("**Detection Details**")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Detection Summary**")
            st.json({
                "is_live": result.get("is_live"),
                "liveness_score": result.get("liveness_score"),
                "challenge": result.get("challenge"),
                "challenge_completed": result.get("challenge_completed"),
                "message": result.get("message"),
            })

        with col2:
            st.markdown("**Processing Info**")
            processing_time = result.get("processing_time_ms")
            st.json({
                "processing_time_ms": f"{processing_time:.2f}" if processing_time else "N/A",
                "spoof_type": result.get("spoof_type"),
                "num_checks": len(result.get("checks", [])),
            })

        # Spoof type display
        spoof_type = result.get("spoof_type")
        if spoof_type and not result.get("is_live"):
            st.markdown("**Detected Spoof Type**")

            spoof_descriptions = {
                "screen_replay": "📱 Screen Replay - Face displayed on a screen/monitor",
                "printed_photo": "📸 Printed Photo - Physical printout of a face",
                "digital_manipulation": "🎨 Digital Manipulation - Artificially altered image",
                "static_image": "🖼️ Static Image - No natural facial features detected",
                "suspected_spoof": "⚠️ Suspected Spoof - General anomaly detected",
            }

            description = spoof_descriptions.get(
                spoof_type,
                f"⚠️ {spoof_type.replace('_', ' ').title()}"
            )

            st.warning(description)

        # Raw response
        with st.expander("View Raw API Response"):
            st.json(result)


# Page entry point - called by Streamlit when page is loaded
page = LivenessDetectionPage()
page.render()
