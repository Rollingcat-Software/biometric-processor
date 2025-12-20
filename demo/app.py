"""Biometric Processor Demo Application.

Main entry point for the Streamlit demo application.
This application demonstrates all features of the Biometric Processor v1.0.0.

Usage:
    streamlit run app.py

Features:
    - 20 interactive demo pages
    - Real-time API integration
    - Professional enterprise UI
    - WebSocket proctoring support

Author: FIVUCSAS Team
Version: 1.0.0
"""

from __future__ import annotations

import streamlit as st

from utils.config import get_settings


def configure_page() -> None:
    """Configure Streamlit page settings."""
    settings = get_settings()

    st.set_page_config(
        page_title=settings.app_name,
        page_icon="🔐",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": "https://github.com/FIVUCSAS/biometric-processor",
            "Report a bug": "https://github.com/FIVUCSAS/biometric-processor/issues",
            "About": f"""
            # {settings.app_name}

            **Version:** {settings.app_version}

            Professional demo application for the Biometric Processor API.

            ---

            **Features:**
            - Face Enrollment, Verification & Search
            - Liveness Detection (Passive + Active)
            - Quality Analysis & Demographics
            - Real-time Proctoring with WebSocket
            - Admin Dashboard & Webhooks

            ---

            *Developed by FIVUCSAS Team*
            *Marmara University - Computer Engineering*
            """,
        },
    )


def load_custom_css() -> None:
    """Load custom CSS styles."""
    st.markdown(
        """
        <style>
        /* Main container */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        /* Button styling - primary buttons */
        .stButton > button[kind="primary"] {
            background-color: #2563EB;
            color: white !important;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            border: none;
        }

        .stButton > button[kind="primary"]:hover {
            background-color: #1D4ED8;
        }

        /* Progress bar */
        .stProgress > div > div {
            background-color: #2563EB;
        }

        /* Bordered containers - ensure readable text */
        [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px;
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #F1F5F9;
        }

        ::-webkit-scrollbar-thumb {
            background: #94A3B8;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #64748B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_welcome_page() -> None:
    """Render the main welcome/landing page."""
    settings = get_settings()

    # Header
    st.title("🔐 Biometric Processor Demo")
    st.markdown(f"**Version {settings.app_version}** | Professional Biometric API Demonstration")

    st.divider()

    # API Status
    from utils.container import get_container
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

    with col2:
        st.info(f"🌐 {settings.api_base_url}")

    with col3:
        st.info("📊 46+ Endpoints")

    st.divider()

    # Feature Categories
    st.subheader("🎯 Feature Categories")

    col1, col2 = st.columns(2)

    with col1:
        # Core Biometrics Card
        with st.container(border=True):
            st.markdown("### 🔐 Core Biometrics")
            st.markdown("""
            - **Face Enrollment** - Register face embeddings
            - **Face Verification** - 1:1 matching
            - **Face Search** - 1:N identification
            - **Liveness Detection** - Anti-spoofing
            """)
            st.page_link("pages/02_Face_Enrollment.py", label="Face Enrollment →", icon="📝")
            st.page_link("pages/03_Face_Verification.py", label="Face Verification →", icon="🔐")
            st.page_link("pages/04_Face_Search.py", label="Face Search →", icon="🔍")
            st.page_link("pages/05_Liveness_Detection.py", label="Liveness Detection →", icon="👁️")

    with col2:
        # Demo Status Card
        with st.container(border=True):
            st.markdown("### 📋 Implementation Status")
            st.markdown("""
            **✅ Implemented (Phase 1-2):**
            - Face Enrollment
            - Face Verification
            - Face Search
            - Liveness Detection

            **🚧 Coming Soon (Phase 3+):**
            - Quality Analysis
            - Demographics
            - Real-time Proctoring
            - Admin Dashboard
            """)

    st.divider()

    # Quick Stats
    st.subheader("📊 Quick Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Features", "36+", help="Complete feature coverage")

    with col2:
        st.metric("API Endpoints", "46+", help="RESTful + WebSocket endpoints")

    with col3:
        st.metric("Demo Pages", "20", help="Interactive demonstrations")

    with col4:
        st.metric("ML Models", "9+", help="Face recognition models supported")

    # Footer
    st.divider()
    st.caption(
        "🎓 Developed by FIVUCSAS Team | "
        "Marmara University - Computer Engineering | "
        "Engineering Project 2025"
    )


def main() -> None:
    """Main application entry point."""
    # Configure page
    configure_page()

    # Load custom styles
    load_custom_css()

    # Render welcome page
    render_welcome_page()


if __name__ == "__main__":
    main()
