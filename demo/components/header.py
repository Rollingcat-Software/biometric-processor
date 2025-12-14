"""Page header component.

This module provides reusable header components for pages.
"""

from __future__ import annotations

import streamlit as st


def render_header(
    title: str,
    description: str | None = None,
    icon: str = "📄",
    show_divider: bool = True,
) -> None:
    """Render a page header.

    Args:
        title: Page title text.
        description: Optional description below title.
        icon: Emoji icon for the page.
        show_divider: Whether to show divider after header.

    Example:
        >>> render_header(
        ...     title="Face Enrollment",
        ...     description="Register face embeddings with quality assessment",
        ...     icon="📝"
        ... )
    """
    st.title(f"{icon} {title}")

    if description:
        st.markdown(description)

    if show_divider:
        st.divider()


def render_subheader(
    title: str,
    description: str | None = None,
    icon: str | None = None,
) -> None:
    """Render a section subheader.

    Args:
        title: Section title text.
        description: Optional description.
        icon: Optional emoji icon.
    """
    if icon:
        st.subheader(f"{icon} {title}")
    else:
        st.subheader(title)

    if description:
        st.caption(description)


def render_breadcrumb(items: list[tuple[str, str | None]]) -> None:
    """Render a breadcrumb navigation.

    Args:
        items: List of (label, url) tuples. If url is None, item is current page.

    Example:
        >>> render_breadcrumb([
        ...     ("Home", "pages/01_Welcome.py"),
        ...     ("Core", None),
        ...     ("Enrollment", None),
        ... ])
    """
    breadcrumb_html = []

    for i, (label, url) in enumerate(items):
        if url:
            breadcrumb_html.append(f'<a href="{url}" style="color: #666;">{label}</a>')
        else:
            breadcrumb_html.append(f'<span style="color: #333;">{label}</span>')

        if i < len(items) - 1:
            breadcrumb_html.append('<span style="color: #999;"> / </span>')

    st.markdown(
        f'<div style="font-size: 0.9rem; margin-bottom: 1rem;">{"".join(breadcrumb_html)}</div>',
        unsafe_allow_html=True,
    )
