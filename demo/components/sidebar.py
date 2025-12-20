"""Sidebar navigation component.

This module provides the navigation sidebar for the demo application.
Includes feature categorization, API status, and settings.
"""

from __future__ import annotations

import streamlit as st

from utils.container import get_container


def render_sidebar() -> None:
    """Render the navigation sidebar.

    Displays:
        - Logo and branding
        - API connection status
        - Feature category navigation
        - Settings panel
    """
    with st.sidebar:
        # Logo and branding
        st.markdown(
            """
            <div style="text-align: center; padding: 1rem 0;">
                <h2 style="margin: 0;">🔐 Biometric Demo</h2>
                <p style="color: #666; font-size: 0.8rem;">v1.0.0</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # API Status
        _render_api_status()

        st.divider()

        # Navigation sections
        _render_navigation()

        st.divider()

        # Settings
        _render_settings()


def _render_api_status() -> None:
    """Render API connection status indicator."""
    container = get_container()

    with st.container():
        st.markdown("**API Status**")

        try:
            is_healthy = container.api_client.health_check()
            if is_healthy:
                st.success("✅ Connected", icon="🟢")
            else:
                st.warning("⚠️ Unhealthy", icon="🟡")
        except Exception:
            st.error("❌ Disconnected", icon="🔴")

        st.caption(f"URL: {container.settings.api_base_url}")


def _render_navigation() -> None:
    """Render navigation links grouped by category."""
    st.markdown("**Features**")

    # Core Biometrics
    with st.expander("🔐 Core Biometrics", expanded=True):
        st.page_link("pages/01_Welcome.py", label="Welcome", icon="🏠")
        st.page_link("pages/02_Face_Enrollment.py", label="Face Enrollment", icon="📝")
        st.page_link("pages/03_Face_Verification.py", label="Face Verification", icon="✅")
        st.page_link("pages/04_Face_Search.py", label="Face Search", icon="🔍")
        st.page_link("pages/05_Liveness_Detection.py", label="Liveness Detection", icon="👁️")

    # Advanced Analysis
    with st.expander("🔬 Advanced Analysis", expanded=False):
        st.page_link("pages/06_Quality_Analysis.py", label="Quality Analysis", icon="📊")
        st.page_link("pages/07_Demographics.py", label="Demographics", icon="👤")
        st.page_link("pages/08_Facial_Landmarks.py", label="Facial Landmarks", icon="📍")
        st.page_link("pages/09_Face_Comparison.py", label="Face Comparison", icon="⚖️")
        st.page_link("pages/10_Similarity_Matrix.py", label="Similarity Matrix", icon="🔢")
        st.page_link("pages/11_Multi_Face_Detection.py", label="Multi-Face Detection", icon="👥")
        st.page_link("pages/12_Card_Type_Detection.py", label="Card Detection", icon="💳")

    # Batch & Proctoring
    with st.expander("⚡ Batch & Proctoring", expanded=False):
        st.page_link("pages/13_Batch_Processing.py", label="Batch Processing", icon="📦")
        st.page_link("pages/14_Proctoring_Session.py", label="Proctoring Session", icon="🎥")
        st.page_link("pages/15_Proctoring_Realtime.py", label="Real-time Proctoring", icon="📡")

    # Administration
    with st.expander("⚙️ Administration", expanded=False):
        st.page_link("pages/16_Admin_Dashboard.py", label="Admin Dashboard", icon="📈")
        st.page_link("pages/17_Webhooks.py", label="Webhooks", icon="🔗")
        st.page_link("pages/18_Configuration.py", label="Configuration", icon="⚙️")
        st.page_link("pages/19_API_Explorer.py", label="API Explorer", icon="🔧")
        st.page_link("pages/20_Embeddings_Management.py", label="Embeddings", icon="💾")


def _render_settings() -> None:
    """Render settings panel."""
    st.markdown("**Settings**")

    container = get_container()

    # Theme toggle (visual only - Streamlit handles actual theme)
    theme = st.selectbox(
        "Theme",
        options=["Auto", "Light", "Dark"],
        index=0,
        key="sidebar_theme",
    )

    # Debug mode toggle
    debug = st.checkbox(
        "Debug Mode",
        value=container.settings.debug,
        key="sidebar_debug",
    )

    if debug:
        st.info("Debug mode enabled - verbose logging active")
