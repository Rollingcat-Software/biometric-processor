"""Face Search Demo Page.

This page demonstrates 1:N face identification:
    - Search across all enrollments
    - Top-N results with similarity ranking
    - Threshold filtering
    - Result visualization with similarity bars
    - Multi-tenant search support

API Endpoints Used:
    - POST /api/v1/search - Main search
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from components.base import BasePage
from components.image_uploader import ImageUploader
from components.metrics import render_metric
from utils.config import get_settings, get_thresholds
from utils.exceptions import APIConnectionError, APIResponseError, DemoAppError


class FaceSearchPage(BasePage):
    """Face Search demo page.

    Demonstrates 1:N face identification with configurable
    search parameters and result visualization.

    Attributes:
        _uploader: Image uploader component.
        _search_result: Latest search result.
    """

    def __init__(self) -> None:
        """Initialize the search page."""
        super().__init__()
        self._search_result: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        """Page title."""
        return "Face Search"

    @property
    def description(self) -> str:
        """Page description."""
        return """
        Perform 1:N face identification by searching through all enrolled faces.
        Upload an image to find matching identities ranked by similarity.
        """

    @property
    def icon(self) -> str:
        """Page icon."""
        return "🔍"

    def _render_sidebar_options(self) -> None:
        """Render sidebar search options."""
        with st.sidebar:
            st.header("Search Settings")

            # Max results
            st.slider(
                "Maximum Results",
                min_value=1,
                max_value=50,
                value=10,
                key="max_results",
                help="Maximum number of matches to return",
            )

            st.divider()

            # Minimum threshold
            thresholds = get_thresholds()
            st.slider(
                "Minimum Similarity",
                min_value=0.3,
                max_value=0.9,
                value=thresholds.LOW_CONFIDENCE_THRESHOLD,
                step=0.05,
                key="min_similarity",
                help="Minimum similarity score to include in results",
            )

            st.divider()

            # Tenant selection
            st.selectbox(
                "Search Tenant",
                options=["All Tenants", "default", "tenant_a", "tenant_b", "demo"],
                key="search_tenant",
                help="Limit search to specific tenant",
            )

            st.divider()

            # Display options
            st.subheader("Display Options")

            st.checkbox(
                "Show Similarity Distribution",
                value=True,
                key="show_distribution",
            )

            st.checkbox(
                "Show Thumbnails",
                value=True,
                key="show_thumbnails",
            )

            st.selectbox(
                "Sort Order",
                options=["Similarity (High to Low)", "Similarity (Low to High)", "User ID"],
                key="sort_order",
            )

    def _render_main_content(self) -> None:
        """Render main search content."""
        col_upload, col_settings = st.columns([1, 1])

        with col_upload:
            st.subheader("Search Image")
            self._uploader = ImageUploader(
                key="search_image",
                label="Upload Face to Search",
                show_preview=True,
            )
            self._uploader.render()

        with col_settings:
            st.subheader("Search Configuration")

            # Show current settings
            max_results = st.session_state.get("max_results", 10)
            min_sim = st.session_state.get("min_similarity", 0.5)
            tenant = st.session_state.get("search_tenant", "All Tenants")

            st.info(f"""
            **Current Search Parameters:**
            - Max Results: `{max_results}`
            - Min Similarity: `{min_sim:.0%}`
            - Tenant Scope: `{tenant}`
            """)

            # Quick actions
            st.markdown("**Quick Actions**")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Reset Settings", use_container_width=True):
                    st.session_state["max_results"] = 10
                    st.session_state["min_similarity"] = 0.5
                    st.session_state["search_tenant"] = "All Tenants"
                    st.rerun()

            with col2:
                if st.button("High Precision", use_container_width=True):
                    st.session_state["min_similarity"] = 0.7
                    st.session_state["max_results"] = 5
                    st.rerun()

        # Search button
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            can_search = hasattr(self, "_uploader") and self._uploader.has_image

            if st.button(
                "Search Database",
                type="primary",
                use_container_width=True,
                disabled=not can_search,
            ):
                self._perform_search()

        # Results section
        st.divider()
        self._render_search_results()

    def _perform_search(self) -> None:
        """Execute face search."""
        image_bytes = self._uploader.get_image_bytes()
        max_results = st.session_state.get("max_results", 10)
        min_similarity = st.session_state.get("min_similarity", 0.5)
        tenant = st.session_state.get("search_tenant", "All Tenants")

        if tenant == "All Tenants":
            tenant = None

        with st.spinner("Searching database..."):
            try:
                self._search_result = asyncio.run(
                    self._search_faces(
                        image_bytes=image_bytes,
                        max_results=max_results,
                        min_similarity=min_similarity,
                        tenant=tenant,
                    )
                )
                matches = len(self._search_result.get("matches", []))
                st.success(f"Search complete! Found {matches} match(es).")
            except APIConnectionError as e:
                st.error(e.to_user_message())
            except APIResponseError as e:
                st.error(e.to_user_message())
            except DemoAppError as e:
                st.error(e.to_user_message())
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    async def _search_faces(
        self,
        image_bytes: bytes,
        max_results: int,
        min_similarity: float,
        tenant: str | None,
    ) -> dict[str, Any]:
        """Search for matching faces in the database.

        Args:
            image_bytes: Probe image data.
            max_results: Maximum results to return.
            min_similarity: Minimum similarity threshold.
            tenant: Optional tenant filter.

        Returns:
            Search result with matches.
        """
        api_client = self.container.api_client
        settings = get_settings()

        data = {
            "max_results": max_results,
            "threshold": min_similarity,
        }

        if tenant:
            data["tenant_id"] = tenant

        result = await api_client.post(
            f"{settings.api_version}/search",
            data=data,
            files={"image": image_bytes},
        )
        return result

    def _render_search_results(self) -> None:
        """Render search results section."""
        st.subheader("Search Results")

        if not self._search_result:
            st.info("Upload an image and click 'Search Database' to see results.")
            return

        matches = self._search_result.get("matches", [])

        if not matches:
            st.warning("No matches found above the similarity threshold.")
            return

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            render_metric(label="Total Matches", value=str(len(matches)))

        with col2:
            top_similarity = matches[0].get("similarity", 0) if matches else 0
            render_metric(
                label="Top Match",
                value=f"{top_similarity*100:.1f}%",
            )

        with col3:
            avg_similarity = sum(m.get("similarity", 0) for m in matches) / len(matches)
            render_metric(
                label="Avg Similarity",
                value=f"{avg_similarity*100:.1f}%",
            )

        with col4:
            processing_time = self._search_result.get("processing_time_ms", 0)
            render_metric(
                label="Search Time",
                value=f"{processing_time:.0f}ms",
            )

        # Results tabs
        tabs = st.tabs(["Results Table", "Similarity Chart", "Details"])

        with tabs[0]:
            self._render_results_table(matches)

        with tabs[1]:
            self._render_similarity_chart(matches)

        with tabs[2]:
            self._render_match_details(matches)

    def _render_results_table(self, matches: list[dict[str, Any]]) -> None:
        """Render results as a table.

        Args:
            matches: List of match results.
        """
        # Sort matches based on user preference
        sort_order = st.session_state.get("sort_order", "Similarity (High to Low)")

        if sort_order == "Similarity (High to Low)":
            matches = sorted(matches, key=lambda x: x.get("similarity", 0), reverse=True)
        elif sort_order == "Similarity (Low to High)":
            matches = sorted(matches, key=lambda x: x.get("similarity", 0))
        elif sort_order == "User ID":
            matches = sorted(matches, key=lambda x: x.get("user_id", ""))

        # Create DataFrame for display
        data = []
        for idx, match in enumerate(matches, 1):
            similarity = match.get("similarity", 0)
            data.append({
                "Rank": idx,
                "User ID": match.get("user_id", "N/A"),
                "Similarity": f"{similarity*100:.1f}%",
                "Similarity Bar": similarity,
                "Tenant": match.get("tenant_id", "default"),
                "Enrolled": match.get("created_at", "N/A")[:10] if match.get("created_at") else "N/A",
            })

        df = pd.DataFrame(data)

        # Display with custom formatting
        st.dataframe(
            df,
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "User ID": st.column_config.TextColumn("User ID", width="medium"),
                "Similarity": st.column_config.TextColumn("Similarity", width="small"),
                "Similarity Bar": st.column_config.ProgressColumn(
                    "Match Score",
                    min_value=0,
                    max_value=1,
                    format="%.0f%%",
                ),
                "Tenant": st.column_config.TextColumn("Tenant", width="small"),
                "Enrolled": st.column_config.TextColumn("Enrolled", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )

    def _render_similarity_chart(self, matches: list[dict[str, Any]]) -> None:
        """Render similarity distribution chart.

        Args:
            matches: List of match results.
        """
        if not st.session_state.get("show_distribution", True):
            st.info("Enable 'Show Similarity Distribution' in sidebar to view chart.")
            return

        # Horizontal bar chart
        user_ids = [m.get("user_id", f"User {i}") for i, m in enumerate(matches, 1)]
        similarities = [m.get("similarity", 0) * 100 for m in matches]

        # Color based on similarity level
        colors = []
        for sim in similarities:
            if sim >= 80:
                colors.append("green")
            elif sim >= 60:
                colors.append("orange")
            else:
                colors.append("red")

        fig = go.Figure(go.Bar(
            x=similarities,
            y=user_ids,
            orientation='h',
            marker_color=colors,
            text=[f"{s:.1f}%" for s in similarities],
            textposition="auto",
        ))

        # Add threshold line
        threshold = st.session_state.get("min_similarity", 0.5) * 100
        fig.add_vline(
            x=threshold,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"Threshold ({threshold:.0f}%)",
        )

        fig.update_layout(
            title="Similarity Score Distribution",
            xaxis_title="Similarity (%)",
            yaxis_title="User ID",
            height=max(300, len(matches) * 40),
            yaxis={'categoryorder': 'total ascending'},
        )

        st.plotly_chart(fig, use_container_width=True)

        # Histogram of similarity distribution
        st.markdown("**Score Distribution Histogram**")

        fig_hist = px.histogram(
            x=similarities,
            nbins=10,
            labels={"x": "Similarity (%)"},
            title="Distribution of Match Scores",
        )
        fig_hist.update_layout(height=250)
        st.plotly_chart(fig_hist, use_container_width=True)

    def _render_match_details(self, matches: list[dict[str, Any]]) -> None:
        """Render detailed match information.

        Args:
            matches: List of match results.
        """
        st.markdown("**Match Details**")

        # Select match to view details
        user_ids = [m.get("user_id", f"Unknown {i}") for i, m in enumerate(matches, 1)]

        selected = st.selectbox(
            "Select match to view details",
            options=range(len(matches)),
            format_func=lambda x: f"#{x+1}: {user_ids[x]} ({matches[x].get('similarity', 0)*100:.1f}%)",
        )

        if selected is not None:
            match = matches[selected]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Identity Information**")
                st.json({
                    "user_id": match.get("user_id"),
                    "tenant_id": match.get("tenant_id"),
                    "enrollment_id": match.get("enrollment_id"),
                    "created_at": match.get("created_at"),
                })

            with col2:
                st.markdown("**Match Metrics**")
                st.json({
                    "similarity": match.get("similarity"),
                    "distance": match.get("distance"),
                    "rank": selected + 1,
                })

            # Metadata if available
            if match.get("metadata"):
                st.markdown("**Stored Metadata**")
                st.json(match.get("metadata"))

        # Raw response
        with st.expander("View Raw API Response"):
            st.json(self._search_result)


# Page entry point - called by Streamlit when page is loaded
page = FaceSearchPage()
page.render()
