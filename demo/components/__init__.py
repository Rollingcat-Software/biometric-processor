"""Reusable UI components for the Demo Application.

This package contains shared UI components following the Open/Closed Principle:
    - BaseComponent: Abstract base class for all components
    - Sidebar: Navigation sidebar component
    - Header: Page header component
    - MetricsCard: Metric display card
    - ResultDisplay: API result visualization
    - ImageUploader: Enhanced image upload component
"""

from components.base import BaseComponent, BasePage
from components.sidebar import render_sidebar
from components.header import render_header
from components.metrics import MetricsCard, render_metrics_row, render_metric
from components.result_display import ResultDisplay, render_result
from components.image_uploader import ImageUploader, render_image_uploader

__all__ = [
    "BaseComponent",
    "BasePage",
    "render_sidebar",
    "render_header",
    "MetricsCard",
    "render_metrics_row",
    "render_metric",
    "ResultDisplay",
    "render_result",
    "ImageUploader",
    "render_image_uploader",
]
