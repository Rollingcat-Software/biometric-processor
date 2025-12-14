"""Welcome Page - Landing page for Biometric Processor Demo.

This page provides an overview of the demo application and
quick navigation to all feature categories.

Features Demonstrated:
    - System overview and capabilities
    - Health check status
    - Quick stats (enrollments, sessions, etc.)
    - Feature navigation cards
    - API connectivity test
"""

from __future__ import annotations

import streamlit as st

from components.header import render_header
from components.metrics import MetricData, render_metrics_row
from utils.container import get_container


def render_welcome_page() -> None:
    """Render the welcome/landing page."""
    container = get_container()
    settings = container.settings

    # Header
    render_header(
        title="Biometric Processor Demo",
        description=f"Version {settings.app_version} | Professional Biometric API Demonstration",
        icon="🔐",
    )

    # API Status Section
    _render_api_status()

    st.divider()

    # Feature Categories
    st.subheader("🎯 Feature Categories")
    _render_feature_categories()

    st.divider()

    # Quick Statistics
    st.subheader("📊 Quick Statistics")
    _render_statistics()

    # Footer
    st.divider()
    st.caption(
        "🎓 Developed by FIVUCSAS Team | "
        "Marmara University - Computer Engineering | "
        "Engineering Project 2025"
    )


def _render_api_status() -> None:
    """Render API connection status."""
    container = get_container()

    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            is_healthy = container.api_client.health_check()
            if is_healthy:
                st.success("✅ API Online")
            else:
                st.warning("⚠️ API Unhealthy")
        except Exception:
            st.error("❌ API Offline")
            st.info("💡 Start the API with: `uvicorn app.main:app --port 8001`")

    with col2:
        st.info(f"🌐 {container.settings.api_base_url}")

    with col3:
        st.info("📊 46+ Endpoints Available")


def _render_feature_categories() -> None:
    """Render feature category cards."""
    col1, col2 = st.columns(2)

    with col1:
        # Core Biometrics Card
        with st.container(border=True):
            st.markdown("### 🔐 Core Biometrics")
            st.markdown("""
            Essential face recognition operations:
            - **Face Enrollment** - Register face embeddings with quality assessment
            - **Face Verification** - 1:1 matching against enrolled users
            - **Face Search** - 1:N identification across database
            - **Liveness Detection** - Passive + Active anti-spoofing
            - **Batch Processing** - Bulk enrollment and verification
            """)
            if st.button("Start Core Demo →", key="core_demo"):
                st.switch_page("pages/02_Face_Enrollment.py")

        # Advanced Analysis Card
        with st.container(border=True):
            st.markdown("### 🔬 Advanced Analysis")
            st.markdown("""
            Detailed face analysis features:
            - **Quality Analysis** - Blur, lighting, pose scoring
            - **Demographics** - Age, gender, emotion estimation
            - **Facial Landmarks** - 468-point detection
            - **Face Comparison** - Direct 1:1 without enrollment
            - **Similarity Matrix** - NxN analysis with clustering
            """)
            if st.button("Start Analysis Demo →", key="analysis_demo"):
                st.switch_page("pages/06_Quality_Analysis.py")

    with col2:
        # Proctoring Card
        with st.container(border=True):
            st.markdown("### 👁️ Real-Time Proctoring")
            st.markdown("""
            Exam supervision capabilities:
            - **Session Management** - Full lifecycle control
            - **Gaze Tracking** - Eye position monitoring
            - **Object Detection** - Phone/book detection
            - **Incident Tracking** - Automatic violation alerts
            - **WebSocket Streaming** - Real-time frame analysis
            """)
            if st.button("Start Proctoring Demo →", key="proctoring_demo"):
                st.switch_page("pages/14_Proctoring_Session.py")

        # Administration Card
        with st.container(border=True):
            st.markdown("### ⚙️ Administration")
            st.markdown("""
            System management tools:
            - **Admin Dashboard** - Real-time monitoring
            - **Webhooks** - Event notifications with HMAC
            - **Configuration** - All 80+ settings
            - **API Explorer** - Interactive endpoint testing
            - **Embeddings I/O** - Export/Import backup
            """)
            if st.button("Start Admin Demo →", key="admin_demo"):
                st.switch_page("pages/16_Admin_Dashboard.py")


def _render_statistics() -> None:
    """Render quick statistics."""
    metrics = [
        MetricData("Total Features", "36+", help_text="Complete feature coverage"),
        MetricData("API Endpoints", "46+", help_text="RESTful + WebSocket endpoints"),
        MetricData("Demo Pages", "20", help_text="Interactive demonstrations"),
        MetricData("ML Models", "9+", help_text="Face recognition models"),
    ]

    render_metrics_row(metrics, columns=4)


# Page entry point - called by Streamlit when page is loaded
render_welcome_page()
